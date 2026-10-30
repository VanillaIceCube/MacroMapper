"""Keep ordinary production releases independent of deferred MCP onboarding."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "macromapper_disabled_bundle", ROOT / "deploy/production/build_bundle.py"
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


class DisabledMCPPolicyTests(unittest.TestCase):
    def test_ordinary_release_needs_no_shared_issuer_credential(self):
        with tempfile.TemporaryDirectory() as directory:
            incoming = Path(directory) / "incoming"
            identity = builder.build(incoming, ordinary_environment())
            bundle = incoming / identity
            environment = dict(
                line.split("=", 1)
                for line in (bundle / ".backend.env").read_text().splitlines()
            )
            self.assertEqual(environment["DJANGO_MCP_ENABLED"], "0")
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
                [probe["path"] for probe in policy["readiness"]["public"]],
                ["/", "/api/notifications/"],
            )

    def test_environment_cannot_enable_a_deferred_production_connector(self):
        environment = ordinary_environment()
        environment["DJANGO_MCP_ENABLED"] = "1"
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaisesRegex(
                ValueError, "Production setting mismatch: DJANGO_MCP_ENABLED"
            ),
        ):
            builder.build(Path(directory) / "incoming", environment)


if __name__ == "__main__":
    unittest.main()
