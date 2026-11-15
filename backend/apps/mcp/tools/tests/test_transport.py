"""Actual app-owned MCP HTTP discovery, tool calls and revocation."""

from unittest import skipUnless

from asgiref.sync import async_to_sync, sync_to_async
from django.conf import settings
from django.test import TransactionTestCase

from .. import services
from ..auth import ESTIMATE, READ, WRITE
from .helpers import MCPToolFixtures


@skipUnless(settings.MCP_ENABLED, "Run the enabled app-owned OAuth profile")
class MCPToolTransportTests(MCPToolFixtures, TransactionTestCase):
    def test_actual_factory_discovery_read_confirmation_and_revocation(self):
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
                    self.assertEqual(
                        (
                            await rpc(
                                "initialize",
                                {
                                    "protocolVersion": "2025-11-25",
                                    "capabilities": {},
                                    "clientInfo": {
                                        "name": "domain-test",
                                        "version": "1",
                                    },
                                },
                            )
                        ).status_code,
                        200,
                    )
                    listing = (await rpc("tools/list")).json()["result"]["tools"]
                    tools = {tool["name"]: tool for tool in listing}
                    self.assertEqual(len(tools), 18)
                    self.assertNotIn("connection_status", tools)
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
                    for name in ["preview_change", "confirm_change"]:
                        self.assertEqual(
                            tools[name]["_meta"]["securitySchemes"],
                            [{"type": "oauth2", "scopes": [READ, WRITE]}],
                        )
                    for name in ["preview_paid_change", "confirm_paid_change"]:
                        self.assertEqual(
                            tools[name]["_meta"]["securitySchemes"],
                            [{"type": "oauth2", "scopes": [READ, WRITE, ESTIMATE]}],
                        )
                    self.assertEqual(
                        tools["search_foods"]["_meta"]["securitySchemes"],
                        [{"type": "oauth2", "scopes": [READ]}],
                    )
                    nonpaid_actions = set(
                        tools["preview_change"]["inputSchema"]["properties"]["action"][
                            "enum"
                        ]
                    )
                    paid_actions = set(
                        tools["preview_paid_change"]["inputSchema"]["properties"][
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
                        nonpaid_actions | paid_actions, set(services.OPERATIONS)
                    )
                    self.assertIn(
                        "meal.delete",
                        tools["preview_change"]["inputSchema"]["properties"]["action"][
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
                    pending = await tool(
                        "preview_change",
                        {"action": "meal.create", "changes": self.meal_payload()},
                    )
                    confirmation = pending["structuredContent"]["confirmation_id"]
                    applied = await tool(
                        "confirm_change",
                        {"confirmation_id": confirmation, "confirmed": True},
                    )
                    self.assertTrue(applied["structuredContent"]["applied"])
                    paid_arguments = {
                        "action": "proposal.estimate",
                        "changes": {"description": "Apple", "entry_date": "2026-10-30"},
                    }
                    self.assertTrue(
                        (await tool("preview_change", paid_arguments))["isError"]
                    )
                    paid_preview = (await tool("preview_paid_change", paid_arguments))[
                        "structuredContent"
                    ]
                    paid_confirmation = {
                        "confirmation_id": paid_preview["confirmation_id"],
                        "confirmed": True,
                    }
                    self.assertIn("confirm_paid_change", paid_preview["instruction"])
                    self.assertTrue(
                        (await tool("confirm_change", paid_confirmation))["isError"]
                    )
                    nonpaid_preview = (
                        await tool(
                            "preview_change",
                            {"action": "meal.create", "changes": self.meal_payload()},
                        )
                    )["structuredContent"]
                    nonpaid_confirmation = {
                        "confirmation_id": nonpaid_preview["confirmation_id"],
                        "confirmed": True,
                    }
                    self.assertTrue(
                        (await tool("confirm_paid_change", nonpaid_confirmation))[
                            "isError"
                        ]
                    )
                    await sync_to_async(
                        type(self.token).objects.filter(pk=self.token.pk).update
                    )(scope=" ".join([READ, WRITE]))
                    self.assertTrue(
                        (await tool("preview_paid_change", paid_arguments))["isError"]
                    )
                    self.assertTrue(
                        (await tool("confirm_paid_change", paid_confirmation))[
                            "isError"
                        ]
                    )
                    self.assertTrue(
                        (await tool("confirm_change", nonpaid_confirmation))[
                            "structuredContent"
                        ]["applied"]
                    )
                    # Regrant the separate paid permission: the earlier mismatches
                    # and insufficient-scope calls must not have consumed approval.
                    await sync_to_async(
                        type(self.token).objects.filter(pk=self.token.pk).update
                    )(scope=" ".join([READ, WRITE, ESTIMATE]))
                    self.assertTrue(
                        (await tool("confirm_paid_change", paid_confirmation))[
                            "structuredContent"
                        ]["applied"]
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
                                "confirm_change",
                                {"confirmation_id": confirmation, "confirmed": True},
                            )
                        )["isError"]
                    )
                    self.assertTrue(
                        (
                            await tool(
                                "preview_change",
                                {
                                    "action": "meal.create",
                                    "changes": self.meal_payload(),
                                    "target_id": True,
                                },
                            )
                        )["isError"]
                    )
                    await sync_to_async(
                        type(self.token).objects.filter(pk=self.token.pk).update
                    )(scope=READ)
                    self.assertTrue(
                        (
                            await tool(
                                "preview_change",
                                {
                                    "action": "meal.create",
                                    "changes": self.meal_payload(),
                                },
                            )
                        )["isError"]
                    )
                    await sync_to_async(self.token.delete)()
                    self.assertEqual((await rpc("tools/list")).status_code, 401)

        async_to_sync(exercise)()
