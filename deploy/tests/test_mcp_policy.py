"""App-owned central MCP preparation using existing v1 bundle/readiness primitives."""

import json
import tempfile
import unittest
from pathlib import Path

from test_production import ROOT, builder, environment, release


class MCPPolicyTests(unittest.TestCase):
    def test_shared_gateway_five_network_policy_preserves_companion_outages(self):
        policy = release.CONFIG["gateway"]
        self.assertEqual(
            set(policy["networks"]),
            {
                "notoli_backend_private",
                "notoli_default",
                "macromapper-ingress",
                "ynab_mcp_private",
                "mcp_auth_private",
            },
        )
        self.assertEqual(policy["addresses"]["notoli_backend_private"], "172.30.88.2")
        for network, subnet, address, companion in (
            ("ynab_mcp_private", "172.30.89.0/29", "172.30.89.2", "ynab-mcp-gateway-1"),
            ("mcp_auth_private", "172.30.92.0/29", "172.30.92.2", "mcp-auth-server"),
        ):
            self.assertEqual(policy["addresses"][network], address)
            self.assertEqual(
                policy["networks"][network],
                {
                    "internal": True,
                    "subnet": subnet,
                    "allowed": ["host-ingress-proxy", companion],
                    "required": ["host-ingress-proxy"],
                },
            )
        self.assertEqual(
            release.CONFIG["backend_networks"],
            ["macromapper-ingress", "macromapper_default"],
        )
        self.assertEqual(release.CONFIG["readiness"]["direct_status"], 401)

    def test_enabled_policy_requires_private_secret_and_pins_exact_proxy(self):
        self.assertEqual(
            release.CONFIG["environment"]["fixed"]["DJANGO_MCP_ENABLED"], "1"
        )
        self.assertIn("MACROMAPPER_MCP_INTROSPECTION_SECRET", builder.REQUIRED)
        self.assertNotIn("MACROMAPPER_MCP_INTROSPECTION_SECRET", builder.DEFAULTS)
        self.assertEqual(builder.FIXED["DJANGO_TRUSTED_PROXY_IPS"], "172.20.0.3")
        self.assertEqual(
            release.CONFIG["gateway"]["addresses"]["macromapper-ingress"], "172.20.0.3"
        )
        for invalid in (None, ""):
            with (
                self.subTest(secret=invalid),
                tempfile.TemporaryDirectory() as directory,
            ):
                missing = environment()
                missing.pop("MACROMAPPER_MCP_INTROSPECTION_SECRET", None)
                if invalid is not None:
                    missing["MACROMAPPER_MCP_INTROSPECTION_SECRET"] = invalid
                with self.assertRaises(ValueError):
                    builder.build(Path(directory) / "incoming", missing)
        for invalid in ("172.20.0.2", "172.20.0.4", "172.20.0.0/16", "*"):
            with self.subTest(peer=invalid), tempfile.TemporaryDirectory() as directory:
                wrong = environment() | {"DJANGO_TRUSTED_PROXY_IPS": invalid}
                with self.assertRaises(ValueError):
                    builder.build(Path(directory) / "incoming", wrong)
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

    def test_enabled_readiness_uses_exact_resource_issuer_and_challenge(self):
        probes = {rule["path"]: rule for rule in release.CONFIG["readiness"]["public"]}
        self.assertEqual(
            set(probes),
            {
                "/",
                "/api/notifications/",
                "/.well-known/oauth-protected-resource/mcp",
                "/mcp",
            },
        )
        metadata = probes["/.well-known/oauth-protected-resource/mcp"]
        challenge = probes["/mcp"]
        headers = {"Content-Type": "application/json"}
        body = json.dumps(
            {
                "resource": "https://macromapper.judeandrewalaba.com/mcp",
                "authorization_servers": ["https://auth.judeandrewalaba.com"],
            }
        ).encode()
        self.assertTrue(release.response_matches(metadata, headers, body))
        self.assertFalse(
            release.response_matches(metadata, {"Content-Type": "text/html"}, body)
        )
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

    def test_disabled_rollback_profile_keeps_topology_proxy_and_ordinary_health(self):
        delta = json.loads(
            (ROOT / "deploy/production/mcp-disabled-policy.json").read_text()
        )
        self.assertEqual(
            delta["environment_fixed_patch"],
            {"DJANGO_MCP_ENABLED": "0", "DJANGO_TRUSTED_PROXY_IPS": "172.20.0.3"},
        )
        self.assertEqual(
            delta["environment_required_remove"],
            ["MACROMAPPER_MCP_INTROSPECTION_SECRET"],
        )
        self.assertEqual(
            delta["environment_defaults_patch"],
            {"MACROMAPPER_MCP_INTROSPECTION_SECRET": ""},
        )
        retained = [
            rule
            for rule in release.CONFIG["readiness"]["public"]
            if rule["path"] not in delta["readiness_public_remove"]
        ]
        self.assertEqual(
            [rule["path"] for rule in retained], ["/", "/api/notifications/"]
        )
        self.assertNotIn("gateway", delta)
        self.assertNotIn("backend_networks", delta)
