import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "production_bundle", ROOT / "scripts/prepare-production-bundle.py"
)
BUNDLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUNDLE)
SHA = "a" * 40


def environment():
    return {
        "DJANGO_SECRET_KEY": "test-only-secret-$-with-'quotes'",
        "DJANGO_ALLOWED_HOSTS": BUNDLE.DOMAIN,
        "DJANGO_CORS_ALLOWED_ORIGINS": BUNDLE.ORIGIN,
        "DJANGO_CSRF_TRUSTED_ORIGINS": BUNDLE.ORIGIN,
        "DJANGO_FRONTEND_BASE_URL": BUNDLE.ORIGIN,
        "DJANGO_EMAIL_BACKEND": "authentication.email_backends.ResendApiEmailBackend",
        "DJANGO_EMAIL_HOST_KEY": "test-only-resend",
        "DJANGO_DEFAULT_FROM_EMAIL": "MacroMapper <sender@example.com>",
        "MACROMAPPER_OPENAI_API_KEY": "test-only-openai",
    }


class BundleTests(unittest.TestCase):
    def test_missing_credentials_and_wrong_routing_fail_before_staging(self):
        for key, value in (
            ("DJANGO_SECRET_KEY", ""),
            ("MACROMAPPER_OPENAI_API_KEY", ""),
            ("DJANGO_DEBUG", "1"),
            ("DJANGO_ALLOWED_HOSTS", "*"),
            ("DJANGO_SQLITE_PATH", "/somewhere/else.sqlite3"),
            ("DJANGO_FRONTEND_BASE_URL", "http://localhost:3000"),
            ("VITE_API_BASE_URL", "https://other.example.com"),
            ("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"),
            ("DJANGO_SECRET_KEY", "secret\nDJANGO_DEBUG=1"),
        ):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "bundle"
                with self.assertRaises(ValueError):
                    BUNDLE.prepare_bundle(
                        target,
                        {**environment(), key: value},
                        SHA,
                        "VanillaIceCube",
                        ROOT,
                    )
                self.assertFalse(target.exists())

    def test_bundle_uses_sha_images_raw_secrets_and_restricted_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "bundle"
            BUNDLE.prepare_bundle(target, environment(), SHA, "VanillaIceCube", ROOT)
            secret_file = target / ".backend.env.next"
            self.assertIn(
                "DJANGO_SECRET_KEY=test-only-secret-$-with-'quotes'\n",
                secret_file.read_text(),
            )
            release = (target / ".env.next").read_text()
            self.assertEqual(release.count(f":sha-{SHA}"), 2)
            self.assertNotIn("secret", release)
            self.assertNotIn("VITE_", secret_file.read_text())
            if os.name != "nt":
                self.assertEqual(secret_file.stat().st_mode & 0o777, 0o600)
                self.assertEqual(target.stat().st_mode & 0o777, 0o700)


@unittest.skipUnless(shutil.which("docker"), "Docker Compose is needed")
class ComposeTests(unittest.TestCase):
    def config(self, *files, cwd=None, extra_env=None):
        args = ["docker", "compose"]
        for file in files:
            args += ["-f", str(file)]
        result = subprocess.run(
            args + ["config", "--format", "json"],
            cwd=cwd,
            env={**os.environ, **(extra_env or {})},
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    def test_shared_stack_removes_ports_and_standalone_proxy_and_keeps_egress(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "bundle"
            BUNDLE.prepare_bundle(target, environment(), SHA, "VanillaIceCube", ROOT)
            shutil.copyfile(target / ".env.next", target / ".env")
            shutil.copyfile(target / ".backend.env.next", target / ".backend.env")
            config = self.config(
                target / "docker-compose.yml",
                target / "docker-compose.shared.yml",
                cwd=target,
            )
            self.assertEqual(
                set(config["services"]), {"macromapper-backend", "macromapper-frontend"}
            )
            for service in config["services"].values():
                self.assertFalse(service.get("ports"))
                self.assertIn("default", service["networks"])
                self.assertIn("ingress", service["networks"])
                self.assertIn(f":sha-{SHA}", service["image"])
            self.assertFalse(config["networks"]["default"].get("internal", False))
            self.assertTrue(config["networks"]["ingress"]["external"])
            backend = config["services"]["macromapper-backend"]
            self.assertIn("backend", backend["networks"]["default"]["aliases"])
            self.assertNotIn("backend", backend["networks"]["ingress"]["aliases"])
            self.assertEqual(
                set(config["services"]["macromapper-frontend"]["depends_on"]),
                {"macromapper-backend"},
            )
            # Compose escapes dollars in its rendered config for reuse as YAML.
            self.assertEqual(
                config["services"]["macromapper-backend"]["environment"][
                    "DJANGO_SECRET_KEY"
                ],
                environment()["DJANGO_SECRET_KEY"].replace("$", "$$"),
            )
            # Exercise raw parsing in a real container without touching app networks.
            raw_test = target / "raw-test.yml"
            raw_test.write_text(
                "services:\n  backend:\n    image: python:3.12-alpine\n    network_mode: none\n    env_file:\n      - path: .backend.env\n        format: raw\n"
            )
            raw = subprocess.run(
                [
                    "docker",
                    "compose",
                    "-p",
                    "launch-raw-" + uuid.uuid4().hex[:10],
                    "-f",
                    str(raw_test),
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    "backend",
                    "python",
                    "-c",
                    'import os; print(os.environ["DJANGO_SECRET_KEY"])',
                ],
                cwd=target,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(raw.stdout.strip(), environment()["DJANGO_SECRET_KEY"])

    def test_notoli_override_preserves_public_ports_private_ips_and_backend_network(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / ".env").touch()
            config = self.config(
                ROOT / "deploy/tests/fixtures/notoli-compose.yml",
                ROOT / "deploy/notoli.compose.override.yml",
                cwd=target,
                extra_env={"COMPOSE_PROJECT_NAME": "launch-test"},
            )
            proxy = config["services"]["proxy"]
            self.assertEqual(
                proxy["networks"]["backend_private"]["ipv4_address"], "172.30.88.2"
            )
            self.assertEqual(
                {port["published"] for port in proxy["ports"]}, {"80", "443"}
            )
            self.assertIn("default", proxy["networks"])
            self.assertIn("ingress", proxy["networks"])
            self.assertNotIn("ingress", config["services"]["backend"]["networks"])
            self.assertTrue(config["networks"]["backend_private"]["internal"])


@unittest.skipIf(os.name == "nt", "Deployment shell runs on the Linux Droplet")
class DeploymentScriptTests(unittest.TestCase):
    def run_deployment(
        self, database="existing", fail_migration=False, legacy=False, real_backup=False
    ):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        target = Path(self.directory.name) / "bundle"
        BUNDLE.prepare_bundle(target, environment(), SHA, "VanillaIceCube", ROOT)
        if database == "existing":
            with sqlite3.connect(target / "db.sqlite3") as db:
                db.execute("CREATE TABLE preserved (value TEXT)")
                db.execute("INSERT INTO preserved VALUES ('meal-history')")
        elif database == "directory":
            (target / "db.sqlite3").mkdir()
        (target / ".env").write_text("previous-release")
        (target / ".backend.env").write_text("previous-credentials")
        executable = target / "docker"
        executable.write_text(
            f"#!{sys.executable}\n"
            + """import json, os, sqlite3, subprocess, sys
from pathlib import Path
args = sys.argv[1:]
with open('commands.jsonl', 'a') as stream: stream.write(json.dumps(args) + '\\n')
if args[:2] == ['inspect', 'notoli-proxy']: print(str(Path.cwd() / 'nginx-shared.conf'))
if args[:2] == ['inspect', 'macromapper-backend']: print('backend' if os.getenv('LEGACY') == '1' else 'macromapper-backend')
if 'run' in args and args[-2:] == ['python', '-']:
    mount = args[args.index('-v') + 1].rsplit(':', 1)[0]
    if os.getenv('REAL_DOCKER'):
        command = [os.environ['REAL_DOCKER'], 'run', '--rm', '-i']
        if '--user' in args: command += ['--user', args[args.index('--user') + 1]]
        command += ['-v', str(Path.cwd() / 'db.sqlite3') + ':/backend/db.sqlite3:ro', '-v', mount + ':/recovery', 'python:3.12-alpine', 'python', '-']
        subprocess.run(command, input=sys.stdin.read(), text=True, check=True)
    else:
        with sqlite3.connect('db.sqlite3') as source:
            with sqlite3.connect(Path(mount) / 'db.sqlite3') as destination: source.backup(destination)
if 'migrate' in args and os.getenv('FAIL_MIGRATION') == '1': sys.exit(1)
"""
        )
        executable.chmod(0o700)
        result = subprocess.run(
            ["bash", "deploy-production.sh"],
            cwd=target,
            env={
                **os.environ,
                "PATH": str(target) + os.pathsep + os.environ["PATH"],
                "FAIL_MIGRATION": "1" if fail_migration else "0",
                "LEGACY": "1" if legacy else "0",
                "REAL_DOCKER": shutil.which("docker") if real_backup else "",
            },
            capture_output=True,
            text=True,
        )
        commands = (
            [
                json.loads(line)
                for line in (target / "commands.jsonl").read_text().splitlines()
            ]
            if (target / "commands.jsonl").exists()
            else []
        )
        return target, result, commands

    def test_existing_database_and_recovery_survive_deploy(self):
        target, result, commands = self.run_deployment()
        self.assertEqual(result.returncode, 0, result.stderr)
        recovery = next((target / "backups").iterdir())
        for path in (target / "db.sqlite3", recovery / "db.sqlite3"):
            with sqlite3.connect(path) as db:
                self.assertEqual(
                    db.execute("SELECT value FROM preserved").fetchone()[0],
                    "meal-history",
                )
        self.assertEqual((recovery / ".env").read_text(), "previous-release")
        self.assertEqual((recovery / ".backend.env").stat().st_mode & 0o777, 0o600)
        self.assertEqual((target / ".backend.env").stat().st_mode & 0o777, 0o600)
        self.assertFalse(
            any("prune" in args or "--remove-orphans" in args for args in commands)
        )
        self.assertTrue(
            any(
                args[-4:] == ["up", "-d", "macromapper-backend", "macromapper-frontend"]
                for args in commands
            )
        )
        self.assertFalse(any("--force-recreate" in args for args in commands))

    def test_missing_database_is_initialized_but_directory_is_rejected(self):
        target, result, _ = self.run_deployment(database="missing")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((target / "db.sqlite3").is_file())
        _, result, commands = self.run_deployment(database="directory")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(commands, [])

    def test_failed_migration_keeps_recovery_and_does_not_start_services(self):
        target, result, commands = self.run_deployment(fail_migration=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(list((target / "backups").glob("*/db.sqlite3")))
        self.assertFalse(any("up" in args for args in commands))

    def test_older_stack_is_rejected_before_database_or_service_changes(self):
        target, result, commands = self.run_deployment(legacy=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("retire the older MacroMapper stack", result.stdout)
        self.assertFalse((target / "backups").exists())
        self.assertFalse(any("compose" in args for args in commands))
        with sqlite3.connect(target / "db.sqlite3") as db:
            self.assertEqual(
                db.execute("SELECT value FROM preserved").fetchone()[0], "meal-history"
            )

    @unittest.skipUnless(
        shutil.which("docker"), "Docker is needed for the ownership regression"
    )
    def test_real_recovery_file_is_owned_by_nonroot_deployment_user(self):
        if os.geteuid() == 0:
            self.skipTest(
                "Run as a non-root Docker user to exercise the ownership boundary"
            )
        target, result, _ = self.run_deployment(real_backup=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        recovery = next((target / "backups").glob("*/db.sqlite3"))
        self.assertEqual(recovery.stat().st_uid, os.getuid())
        self.assertEqual(recovery.stat().st_gid, os.getgid())
        self.assertEqual(recovery.stat().st_mode & 0o777, 0o600)
        with sqlite3.connect(recovery) as db:
            self.assertEqual(
                db.execute("SELECT value FROM preserved").fetchone()[0], "meal-history"
            )


if __name__ == "__main__":
    unittest.main()
