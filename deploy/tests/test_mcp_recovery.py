"""App-owned policy staging and failed first-enabled-release recovery evidence."""

import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_production as common

preparer = common.module("prepare_mcp_recovery")


def load_tool(path):
    spec = importlib.util.spec_from_file_location(
        "disabled_mcp_release", path / "release.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MCPRecoveryTests(unittest.TestCase):
    def test_staged_tool_keeps_canonical_bytes_and_only_disabled_app_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            target = preparer.prepare(Path(directory) / "disabled-tool", "e" * 40)
            self.assertEqual(
                (target / "release.py").read_bytes(),
                (common.ROOT / "deploy/production/release.py").read_bytes(),
            )
            policy = json.loads((target / "app.json").read_text())
            self.assertEqual(policy["environment"]["fixed"]["DJANGO_MCP_ENABLED"], "0")
            self.assertEqual(
                policy["environment"]["fixed"]["DJANGO_TRUSTED_PROXY_IPS"], "172.20.0.3"
            )
            self.assertEqual(policy["gateway"], common.release.CONFIG["gateway"])
            self.assertEqual(
                [probe["path"] for probe in policy["readiness"]["public"]],
                ["/", "/api/notifications/"],
            )
            self.assertEqual(
                {path.name for path in target.iterdir()},
                {"release.py", "app.json", "manifest.json"},
            )
            manifest = json.loads((target / "manifest.json").read_text())
            self.assertEqual(manifest["source_revision"], "e" * 40)
            for name, digest in manifest["sha256"].items():
                self.assertEqual(
                    digest, hashlib.sha256((target / name).read_bytes()).hexdigest()
                )
            with self.assertRaises(FileExistsError):
                preparer.prepare(target, "e" * 40)

    @unittest.skipUnless(
        os.name == "posix", "Real transaction/permissions run on Linux"
    )
    def test_staged_disabled_tool_recovers_failed_first_enabled_release(self):
        original_readiness = common.release.readiness
        original_preflight = common.release.preflight
        fixture = common.TransactionTests(
            "test_success_full_private_recovery_and_commit_after_health"
        )
        fixture.setUp()
        adapter = patch.object(
            common.release,
            "compose",
            side_effect=lambda directory, *args, **kwargs: fixture.compose(
                directory, *args
            ),
        )
        adapter.start()
        fixture.addCleanup(adapter.stop)
        try:
            staged = preparer.prepare(fixture.root / "disabled-tool", "e" * 40)
            disabled = load_tool(staged)
            fixture.fail_readiness = True
            with self.assertRaises(common.release.ReleaseError):
                common.release.deploy(fixture.root, fixture.bundle)
            marker = fixture.root / "FAILED.json"
            self.assertTrue(marker.exists())
            with self.assertRaises(common.release.ReleaseError):
                original_preflight(fixture.root)  # A new disabled deploy is barred.

            def health(module):
                def check(path, expected, validator):
                    responses = {
                        "/": (200, {"Content-Type": "text/html"}, b"<html>app</html>"),
                        "/api/notifications/": (
                            401,
                            {"Content-Type": "application/json"},
                            b'{"detail":"Authentication required"}',
                        ),
                    }
                    actual, headers, body = responses.get(path, (404, {}, b"not found"))
                    if actual != expected or not validator(headers, body):
                        raise module.ReleaseError(
                            "Captured disabled backend has no MCP routes"
                        )

                return check

            def enabled_readiness(directory):
                with patch.object(
                    common.release.time, "monotonic", side_effect=[0, 91]
                ):
                    original_readiness(directory)

            with (
                patch.object(
                    common.release, "readiness", side_effect=enabled_readiness
                ),
                patch.object(
                    common.release, "check_response", side_effect=health(common.release)
                ),
                self.assertRaises(common.release.ReleaseError),
            ):
                common.release.rollback(fixture.root, fixture.identity, True)
            self.assertTrue(marker.exists())
            self.assertEqual(fixture.events[-1], ("stop-writers",))

            boundary_patches = [
                patch.object(disabled, name, getattr(common.release, name))
                for name in (
                    "compose",
                    "docker",
                    "stop_writers",
                    "stop_management",
                    "snapshot_writer",
                    "app_writers",
                )
            ]
            for item in boundary_patches:
                item.start()
            try:
                with patch.object(
                    disabled, "check_response", side_effect=health(disabled)
                ):
                    # No immutable failed/recovery bundle is edited. The separate
                    # tool selects ordinary health while using captured old state.
                    disabled.rollback(fixture.root, fixture.identity, True)
            finally:
                for item in reversed(boundary_patches):
                    item.stop()
            self.assertFalse(marker.exists())
            self.assertEqual(fixture.values(), ["original"])
            self.assertTrue(
                json.loads((fixture.root / "current.json").read_text())["healthy"]
            )
            self.assertEqual(
                (staged / "release.py").read_bytes(),
                (common.ROOT / "deploy/production/release.py").read_bytes(),
            )
        finally:
            fixture.doCleanups()
