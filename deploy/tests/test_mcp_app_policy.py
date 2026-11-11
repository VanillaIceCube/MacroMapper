"""App-owned MCP activation keeps independent release and rollback boundaries."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "macromapper_app_bundle", ROOT / "deploy/production/build_bundle.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def ordinary_environment():
    return {
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_REPOSITORY_OWNER": "VanillaIceCube",
        "BACKEND_IMAGE": "ghcr.io/vanillaicecube/macromapper-backend@sha256:"
        + "b" * 64,
        "FRONTEND_IMAGE": "ghcr.io/vanillaicecube/macromapper-frontend@sha256:"
        + "c" * 64,
        "DJANGO_SECRET_KEY": "fixture-only-secret",
        "DJANGO_EMAIL_HOST_KEY": "fixture-only-mail",
        "DJANGO_EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "DJANGO_DEFAULT_FROM_EMAIL": "test@example.invalid",
        "MACROMAPPER_OPENAI_API_KEY": "fixture-only-ai",
    }


class AppOwnedMCPPolicyTests(unittest.TestCase):
    def test_ordinary_release_needs_no_shared_issuer_credential(self):
        with tempfile.TemporaryDirectory() as directory:
            incoming = Path(directory) / "incoming"
            identity = builder.build(incoming, ordinary_environment())
            bundle = incoming / identity
            environment = dict(
                line.split("=", 1)
                for line in (bundle / ".backend.env").read_text().splitlines()
            )
            self.assertEqual(environment["DJANGO_MCP_ENABLED"], "1")
            self.assertEqual(environment["DJANGO_TRUSTED_PROXY_IPS"], "172.20.0.3")
            self.assertEqual(
                environment["DJANGO_MCP_BASE_URL"],
                "https://macromapper.judeandrewalaba.com",
            )
            self.assertNotIn("MACROMAPPER_MCP_INTROSPECTION_SECRET", environment)
            self.assertNotIn("DJANGO_MCP_AUTH_MODE", environment)
            self.assertEqual(
                environment["MACROMAPPER_OPENAI_API_KEY"], "fixture-only-ai"
            )
            policy = json.loads((bundle / "app.json").read_text())
            self.assertEqual(
                set(policy["gateway"]["networks"]),
                {"notoli_backend_private", "notoli_default", "macromapper-ingress"},
            )
            self.assertEqual(
                policy["gateway"]["addresses"]["notoli_backend_private"],
                "172.30.88.2",
            )
            self.assertEqual(
                policy["gateway"]["addresses"]["macromapper-ingress"],
                "172.20.0.3",
            )
            # First activation checks the existing disabled backend too. Its
            # environment cannot be required to already contain new settings.
            self.assertEqual(policy["backend_required_env"], [])
            self.assertEqual(
                [probe["path"] for probe in policy["readiness"]["public"]],
                [
                    "/",
                    "/api/notifications/",
                    "/.well-known/oauth-authorization-server",
                    "/.well-known/oauth-protected-resource/mcp",
                    "/mcp",
                ],
            )

    def test_environment_cannot_override_reviewed_origin_or_trust_or_profile(self):
        for key, value in {
            "DJANGO_MCP_ENABLED": "0",
            "DJANGO_MCP_BASE_URL": "https://foreign.example",
            "DJANGO_TRUSTED_PROXY_IPS": "172.20.0.0/16",
        }.items():
            environment = ordinary_environment() | {key: value}
            with (
                self.subTest(key=key),
                tempfile.TemporaryDirectory() as directory,
                self.assertRaisesRegex(
                    ValueError, "Production setting mismatch: " + key
                ),
            ):
                builder.build(Path(directory) / "incoming", environment)

    def test_retained_disabled_controller_keeps_its_own_readiness_on_recovery(self):
        # Model two immutable controller directories, exactly as retained app
        # releases are packaged. Never edit the enabled candidate to recover.
        with tempfile.TemporaryDirectory() as directory:
            previous = Path(directory)
            config = json.loads((ROOT / "deploy/production/app.json").read_text())
            config["environment"]["fixed"]["DJANGO_MCP_ENABLED"] = "0"
            config["readiness"]["public"] = config["readiness"]["public"][:2]
            (previous / "app.json").write_text(json.dumps(config))
            (previous / "release.py").write_bytes(
                (ROOT / "deploy/production/release.py").read_bytes()
            )
            spec = importlib.util.spec_from_file_location(
                "macromapper_previous_disabled_release", previous / "release.py"
            )
            old = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(old)
            from unittest.mock import patch

            with (
                patch.object(old, "compose"),
                patch.object(old, "check_response") as public,
            ):
                old.readiness(previous)
            self.assertEqual(
                [call.args[0] for call in public.call_args_list],
                ["/", "/api/notifications/"],
            )
            # The enabled candidate still requires discovery/authentication.
            current = json.loads((ROOT / "deploy/production/app.json").read_text())
            self.assertEqual(len(current["readiness"]["public"]), 5)


if __name__ == "__main__":
    unittest.main()
