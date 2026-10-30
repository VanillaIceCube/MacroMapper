"""App-owned central MCP preparation using existing v1 bundle/readiness primitives."""

import json
import tempfile
import unittest
from pathlib import Path

from test_production import ROOT, builder, environment, release


class MCPPolicyTests(unittest.TestCase):
    def test_preparation_stays_disabled_and_uses_private_existing_bundle(self):
        self.assertEqual(
            release.CONFIG["environment"]["fixed"]["DJANGO_MCP_ENABLED"], "0"
        )
        self.assertNotIn("MACROMAPPER_MCP_INTROSPECTION_SECRET", builder.REQUIRED)
        fixture = environment()
        fixture["MACROMAPPER_MCP_INTROSPECTION_SECRET"] = 'synthetic-$#"credential'
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "incoming"
            identity = builder.build(destination, fixture)
            bundle = destination / identity
            self.assertIn(
                'MACROMAPPER_MCP_INTROSPECTION_SECRET=synthetic-$#"credential\n',
                (bundle / ".backend.env").read_text(),
            )
            self.assertEqual(
                set(json.loads((bundle / "manifest.json").read_text())), release.PAYLOAD
            )

    def test_unapplied_activation_delta_uses_exact_resource_issuer_and_challenge(self):
        delta = json.loads(
            (ROOT / "deploy/production/mcp-activation-policy.json").read_text()
        )
        self.assertEqual(delta["environment_fixed_patch"], {"DJANGO_MCP_ENABLED": "1"})
        self.assertEqual(
            delta["environment_required_add"], ["MACROMAPPER_MCP_INTROSPECTION_SECRET"]
        )
        metadata, challenge = delta["readiness_public_add"]
        headers = {"Content-Type": "application/json"}
        body = json.dumps(
            {
                "resource": "https://macromapper.judeandrewalaba.com/mcp",
                "authorization_servers": ["https://auth.judeandrewalaba.com"],
            }
        ).encode()
        self.assertTrue(release.response_matches(metadata, headers, body))
        self.assertFalse(
            release.response_matches(
                metadata, headers, body.replace(b"auth.", b"other.")
            )
        )
        self.assertFalse(
            release.response_matches(
                metadata, headers, body.replace(b"macromapper.", b"notoli.")
            )
        )
        self.assertEqual(challenge["status"], 401)
        self.assertEqual(challenge["path"], "/mcp")
        self.assertTrue(
            release.response_matches(
                challenge,
                {
                    "WWW-Authenticate": 'Bearer resource_metadata="https://macromapper.judeandrewalaba.com/.well-known/oauth-protected-resource/mcp"'
                },
                b"",
            )
        )
        self.assertFalse(release.response_matches(challenge, {}, b""))
