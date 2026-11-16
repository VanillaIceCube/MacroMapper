"""Actual app-owned MCP HTTP discovery, tool calls and revocation."""

from unittest import skipUnless
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

from asgiref.sync import async_to_sync, sync_to_async
from django.conf import settings
from django.test import TransactionTestCase

from .. import operations
from ..permissions import ESTIMATE, READ, WRITE
from .helpers import MCPToolFixtures


@skipUnless(settings.MCP_ENABLED, "Run the enabled app-owned OAuth profile")
class MCPToolTransportTests(MCPToolFixtures, TransactionTestCase):
    def test_consent_discloses_delegated_access_and_refresh_cannot_escalate_it(self):
        from rest_framework_simplejwt.tokens import RefreshToken

        from apps.mcp.framework.tests.helpers import CHALLENGE, VERIFIER

        self.client.defaults.update(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(self.user).access_token}",
            HTTP_ACCEPT="application/json",
        )
        query = {
            "client_id": self.application.client_id,
            "response_type": "code",
            "redirect_uri": self.application.redirect_uris,
            "state": "client-state",
            "resource": settings.MCP_RESOURCE_URL,
            "code_challenge": CHALLENGE,
            "code_challenge_method": "S256",
        }
        scoped = self.client.get(
            "/auth/mcp/authorize/", query | {"scope": " ".join([READ, WRITE, ESTIMATE])}
        )
        self.assertEqual(scoped.status_code, 200, scoped.content)
        permissions = {
            item["scope"]: item["description"] for item in scoped.json()["permissions"]
        }
        self.assertEqual(set(permissions), {READ, WRITE, ESTIMATE})
        self.assertIn("permanent deletion", permissions[WRITE])
        self.assertIn("additions and edits directly", permissions[WRITE])
        self.assertIn("separate approval in MacroMapper", permissions[WRITE])
        self.assertIn("spend credits", permissions[ESTIMATE])
        self.assertIn("publish shared food definitions", permissions[ESTIMATE])
        self.assertIn("Run paid AI work directly", permissions[ESTIMATE])
        self.assertIn("no separate per-action app approval", permissions[ESTIMATE])

        default = self.client.get("/auth/mcp/authorize/", query)
        self.assertEqual(default.status_code, 200, default.content)
        self.assertEqual(
            [item["scope"] for item in default.json()["permissions"]], [READ]
        )
        allowed = self.client.post(
            "/auth/mcp/authorize/",
            {"ticket": default.json()["ticket"], "decision": "allow"},
        )
        self.assertEqual(allowed.status_code, 200, allowed.content)
        code = parse_qs(urlsplit(allowed.json()["redirect_url"]).query)["code"][0]
        issued = self.client.post(
            "/auth/mcp/token/",
            urlencode(
                {
                    "grant_type": "authorization_code",
                    "client_id": self.application.client_id,
                    "code": code,
                    "redirect_uri": self.application.redirect_uris,
                    "code_verifier": VERIFIER,
                    "resource": settings.MCP_RESOURCE_URL,
                }
            ),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(issued.status_code, 200, issued.content)
        self.assertEqual(issued.json()["scope"], READ)
        refresh = {
            "grant_type": "refresh_token",
            "client_id": self.application.client_id,
            "refresh_token": issued.json()["refresh_token"],
            "resource": settings.MCP_RESOURCE_URL,
        }
        escalated = self.client.post(
            "/auth/mcp/token/",
            urlencode(refresh | {"scope": " ".join([READ, WRITE, ESTIMATE])}),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(escalated.status_code, 400, escalated.content)
        self.assertEqual(escalated.json()["error"], "invalid_scope")
        refreshed = self.client.post(
            "/auth/mcp/token/",
            urlencode(refresh),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(refreshed.status_code, 200, refreshed.content)
        self.assertEqual(refreshed.json()["scope"], READ)

    def test_actual_factory_discovery_approved_execution_replay_and_revocation(self):
        import httpx2
        from django.core.asgi import get_asgi_application

        from apps.mcp.framework.asgi import create_application

        application = create_application(get_asgi_application())

        async def exercise():
            async with application.router.lifespan_context(application):
                async with httpx2.AsyncClient(
                    transport=httpx2.ASGITransport(app=application),
                    base_url=settings.MCP_BASE_URL,
                ) as client:
                    headers = {
                        "Accept": "application/json, text/event-stream",
                        "MCP-Protocol-Version": "2025-11-25",
                    }

                    async def rpc(method, params=None):
                        return await client.post(
                            "/mcp",
                            headers=headers,
                            json={
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": method,
                                "params": params or {},
                            },
                        )

                    self.assertEqual((await rpc("tools/list")).status_code, 401)
                    metadata = await client.get(
                        "/.well-known/oauth-protected-resource/mcp"
                    )
                    self.assertEqual(
                        metadata.json()["resource"], settings.MCP_RESOURCE_URL
                    )
                    headers["Authorization"] = f"Bearer {self.raw}"
                    initialized = await rpc(
                        "initialize",
                        {
                            "protocolVersion": "2025-11-25",
                            "capabilities": {},
                            "clientInfo": {"name": "domain-test", "version": "1"},
                        },
                    )
                    self.assertEqual(initialized.status_code, 200)
                    self.assertIn(
                        "Follow the host client's consent and safety controls",
                        initialized.json()["result"]["instructions"],
                    )
                    listing = (await rpc("tools/list")).json()["result"]["tools"]
                    tools = {tool["name"]: tool for tool in listing}
                    self.assertEqual(len(tools), 16)
                    self.assertNotIn("preview_change", tools)
                    self.assertIn("execute_change", tools)
                    self.assertIn("execute_paid_change", tools)
                    self.assertNotIn("connection_status", tools)
                    for name in ["confirm_change", "confirm_paid_change"]:
                        self.assertFalse(tools[name]["annotations"]["readOnlyHint"])
                        self.assertTrue(tools[name]["annotations"]["destructiveHint"])
                        self.assertIn(
                            "host client's consent and safety controls",
                            tools[name]["description"],
                        )
                    self.assertTrue(
                        tools["search_foods"]["annotations"]["readOnlyHint"]
                    )
                    self.assertTrue(
                        tools["confirm_change"]["annotations"]["destructiveHint"]
                    )
                    self.assertFalse(
                        tools["confirm_change"]["annotations"]["openWorldHint"]
                    )
                    self.assertTrue(
                        tools["confirm_paid_change"]["annotations"]["openWorldHint"]
                    )
                    for name in ["prepare_change", "confirm_change"]:
                        self.assertEqual(
                            tools[name]["_meta"]["securitySchemes"],
                            [{"type": "oauth2", "scopes": [READ, WRITE]}],
                        )
                    for name in ["prepare_paid_change", "confirm_paid_change"]:
                        self.assertEqual(
                            tools[name]["_meta"]["securitySchemes"],
                            [{"type": "oauth2", "scopes": [READ, WRITE, ESTIMATE]}],
                        )
                    self.assertEqual(
                        tools["search_foods"]["_meta"]["securitySchemes"],
                        [{"type": "oauth2", "scopes": [READ]}],
                    )
                    nonpaid_actions = set(
                        tools["prepare_change"]["inputSchema"]["properties"]["action"][
                            "enum"
                        ]
                    )
                    paid_actions = set(
                        tools["prepare_paid_change"]["inputSchema"]["properties"][
                            "action"
                        ]["enum"]
                    )
                    self.assertEqual(
                        paid_actions,
                        {
                            "proposal.estimate",
                            "proposal.follow_up",
                            "proposal.adjustment",
                            "meal.adjustment",
                        },
                    )
                    self.assertFalse(nonpaid_actions & paid_actions)
                    self.assertEqual(
                        nonpaid_actions | paid_actions, set(operations.OPERATIONS)
                    )
                    self.assertIn(
                        "meal.delete",
                        tools["prepare_change"]["inputSchema"]["properties"]["action"][
                            "enum"
                        ],
                    )

                    async def tool(name, arguments):
                        response = await rpc(
                            "tools/call", {"name": name, "arguments": arguments}
                        )
                        self.assertEqual(response.status_code, 200, response.text)
                        return response.json()["result"]

                    foods = await tool("search_foods", {"query": "Apple"})
                    self.assertEqual(
                        foods["structuredContent"]["data"][0]["id"], self.food.pk
                    )
                    changes = {
                        "request_id": str(uuid4()),
                        "action": "meal.create",
                        "changes": self.meal_payload(),
                    }
                    prepared = (await tool("prepare_change", changes))[
                        "structuredContent"
                    ]
                    confirm = {
                        "request_id": changes["request_id"],
                        "confirmation_id": prepared["result"]["data"][
                            "confirmation_id"
                        ],
                    }
                    unapproved = (await tool("confirm_change", confirm))[
                        "structuredContent"
                    ]
                    self.assertEqual(unapproved["status"], "prepared")
                    self.assertFalse(unapproved["applied"])
                    self.assertEqual(
                        (await tool("execute_change", changes))["structuredContent"][
                            "status"
                        ],
                        "prepared",
                    )
                    await sync_to_async(self.approve)(confirm["confirmation_id"])
                    applied = await tool("confirm_change", confirm)
                    self.assertTrue(applied["structuredContent"]["applied"])
                    self.assertEqual(
                        applied["structuredContent"]["status"], "completed"
                    )
                    self.assertTrue(
                        (await tool("prepare_change", changes))["structuredContent"][
                            "replayed"
                        ]
                    )
                    direct_arguments = {
                        "request_id": str(uuid4()),
                        "action": "meal.update",
                        "target_id": applied["structuredContent"]["result"]["data"][
                            "id"
                        ],
                        "changes": {"notes": "Direct routine edit"},
                    }
                    direct = (await tool("execute_change", direct_arguments))[
                        "structuredContent"
                    ]
                    self.assertEqual(direct["status"], "completed")
                    self.assertEqual(
                        direct["result"]["data"]["notes"], "Direct routine edit"
                    )
                    self.assertTrue(
                        (await tool("execute_change", direct_arguments))[
                            "structuredContent"
                        ]["replayed"]
                    )
                    schema = tools["prepare_change"]["inputSchema"]
                    self.assertIn("request_id", schema["required"])
                    self.assertNotIn("confirmed", schema["properties"])
                    self.assertNotIn("confirmation_id", schema["properties"])
                    self.assertTrue(
                        tools["prepare_change"]["annotations"]["idempotentHint"]
                    )
                    paid_arguments = {
                        "request_id": str(uuid4()),
                        "action": "proposal.estimate",
                        "changes": {"description": "Apple", "entry_date": "2026-10-30"},
                    }
                    self.assertTrue(
                        (await tool("prepare_change", paid_arguments))["isError"]
                    )
                    self.assertTrue(
                        (await tool("prepare_paid_change", changes))["isError"]
                    )
                    await sync_to_async(
                        type(self.token).objects.filter(pk=self.token.pk).update
                    )(scope=" ".join([READ, WRITE]))
                    denied = await tool("prepare_paid_change", paid_arguments)
                    self.assertTrue(denied["isError"])
                    challenge = denied["_meta"]["mcp/www_authenticate"][0]
                    self.assertIn('error="insufficient_scope"', challenge)
                    self.assertIn(
                        'scope="macromapper:read macromapper:write macromapper:estimate"',
                        challenge,
                    )
                    self.assertTrue(
                        (await tool("prepare_change", changes))["structuredContent"][
                            "replayed"
                        ]
                    )
                    await sync_to_async(
                        type(self.token).objects.filter(pk=self.token.pk).update
                    )(scope=" ".join([READ, WRITE, ESTIMATE]))
                    paid_prepared = (await tool("prepare_paid_change", paid_arguments))[
                        "structuredContent"
                    ]
                    self.assertFalse(paid_prepared["applied"])
                    self.assertEqual(
                        (await tool("execute_paid_change", paid_arguments))[
                            "structuredContent"
                        ]["status"],
                        "prepared",
                    )
                    paid_confirm = {
                        "request_id": paid_arguments["request_id"],
                        "confirmation_id": paid_prepared["result"]["data"][
                            "confirmation_id"
                        ],
                    }
                    await sync_to_async(self.approve)(paid_confirm["confirmation_id"])
                    self.assertTrue(
                        (await tool("confirm_paid_change", paid_confirm))[
                            "structuredContent"
                        ]["applied"]
                    )
                    self.assertTrue(
                        (await tool("prepare_paid_change", paid_arguments))[
                            "structuredContent"
                        ]["replayed"]
                    )
                    direct_paid = dict(paid_arguments, request_id=str(uuid4()))
                    with patch(
                        "apps.estimates.services.get_estimation_provider",
                        side_effect=AssertionError(
                            "Catalog wire fixture must not call a provider"
                        ),
                    ):
                        done = (await tool("execute_paid_change", direct_paid))[
                            "structuredContent"
                        ]
                        self.assertEqual(done["status"], "completed")
                        self.assertTrue(
                            (await tool("execute_paid_change", direct_paid))[
                                "structuredContent"
                            ]["replayed"]
                        )
                    proposals = (await tool("list_proposals", {}))["structuredContent"]
                    proposal_id = proposals["data"][0]["id"]
                    review = (
                        await tool(
                            "get_proposal",
                            {
                                "proposal_id": proposal_id,
                                "item_limit": 1,
                                "item_offset": 0,
                            },
                        )
                    )["structuredContent"]
                    self.assertEqual(review["data"]["id"], proposal_id)
                    self.assertEqual(review["data"]["item_count"], 1)
                    self.assertFalse(review["has_more"])
                    self.assertNotIn("revisions", review["data"])
                    self.assertTrue(
                        (
                            await tool(
                                "prepare_change",
                                changes
                                | {
                                    "changes": self.meal_payload()
                                    | {"name": "Different request"}
                                },
                            )
                        )["isError"]
                    )
                    self.assertTrue(
                        (
                            await tool(
                                "prepare_change",
                                changes
                                | {"request_id": str(uuid4()), "target_id": True},
                            )
                        )["isError"]
                    )
                    await sync_to_async(
                        type(self.token).objects.filter(pk=self.token.pk).update
                    )(scope=READ)
                    self.assertTrue((await tool("prepare_change", changes))["isError"])
                    await sync_to_async(self.token.delete)()
                    self.assertEqual((await rpc("tools/list")).status_code, 401)

        async_to_sync(exercise)()
