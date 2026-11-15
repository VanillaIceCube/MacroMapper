"""Actual app-owned MCP HTTP discovery, tool calls and revocation."""

from unittest import skipUnless
from uuid import uuid4

from asgiref.sync import async_to_sync, sync_to_async
from django.conf import settings
from django.test import TransactionTestCase

from .. import operations
from ..permissions import ESTIMATE, READ, WRITE
from .helpers import MCPToolFixtures


@skipUnless(settings.MCP_ENABLED, "Run the enabled app-owned OAuth profile")
class MCPToolTransportTests(MCPToolFixtures, TransactionTestCase):
    def test_actual_factory_discovery_direct_execution_replay_and_revocation(self):
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
                    self.assertEqual(len(tools), 12)
                    self.assertNotIn("preview_change", tools)
                    self.assertNotIn("confirm_change", tools)
                    self.assertNotIn("connection_status", tools)
                    self.assertTrue(
                        tools["search_foods"]["annotations"]["readOnlyHint"]
                    )
                    self.assertTrue(
                        tools["execute_change"]["annotations"]["destructiveHint"]
                    )
                    self.assertFalse(
                        tools["execute_change"]["annotations"]["openWorldHint"]
                    )
                    self.assertTrue(
                        tools["execute_paid_change"]["annotations"]["openWorldHint"]
                    )
                    for name in ["execute_change"]:
                        self.assertEqual(
                            tools[name]["_meta"]["securitySchemes"],
                            [{"type": "oauth2", "scopes": [READ, WRITE]}],
                        )
                    for name in ["execute_paid_change"]:
                        self.assertEqual(
                            tools[name]["_meta"]["securitySchemes"],
                            [{"type": "oauth2", "scopes": [READ, WRITE, ESTIMATE]}],
                        )
                    self.assertEqual(
                        tools["search_foods"]["_meta"]["securitySchemes"],
                        [{"type": "oauth2", "scopes": [READ]}],
                    )
                    nonpaid_actions = set(
                        tools["execute_change"]["inputSchema"]["properties"]["action"][
                            "enum"
                        ]
                    )
                    paid_actions = set(
                        tools["execute_paid_change"]["inputSchema"]["properties"][
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
                        tools["execute_change"]["inputSchema"]["properties"]["action"][
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
                    applied = await tool("execute_change", changes)
                    self.assertTrue(applied["structuredContent"]["applied"])
                    self.assertEqual(
                        applied["structuredContent"]["status"], "completed"
                    )
                    self.assertTrue(
                        (await tool("execute_change", changes))["structuredContent"][
                            "replayed"
                        ]
                    )
                    schema = tools["execute_change"]["inputSchema"]
                    self.assertIn("request_id", schema["required"])
                    self.assertNotIn("confirmed", schema["properties"])
                    self.assertNotIn("confirmation_id", schema["properties"])
                    self.assertTrue(
                        tools["execute_change"]["annotations"]["idempotentHint"]
                    )
                    paid_arguments = {
                        "request_id": str(uuid4()),
                        "action": "proposal.estimate",
                        "changes": {"description": "Apple", "entry_date": "2026-10-30"},
                    }
                    self.assertTrue(
                        (await tool("execute_change", paid_arguments))["isError"]
                    )
                    self.assertTrue(
                        (await tool("execute_paid_change", changes))["isError"]
                    )
                    await sync_to_async(
                        type(self.token).objects.filter(pk=self.token.pk).update
                    )(scope=" ".join([READ, WRITE]))
                    denied = await tool("execute_paid_change", paid_arguments)
                    self.assertTrue(denied["isError"])
                    challenge = denied["_meta"]["mcp/www_authenticate"][0]
                    self.assertIn('error="insufficient_scope"', challenge)
                    self.assertIn(
                        'scope="macromapper:read macromapper:write macromapper:estimate"',
                        challenge,
                    )
                    self.assertTrue(
                        (await tool("execute_change", changes))["structuredContent"][
                            "replayed"
                        ]
                    )
                    await sync_to_async(
                        type(self.token).objects.filter(pk=self.token.pk).update
                    )(scope=" ".join([READ, WRITE, ESTIMATE]))
                    self.assertTrue(
                        (await tool("execute_paid_change", paid_arguments))[
                            "structuredContent"
                        ]["applied"]
                    )
                    self.assertTrue(
                        (await tool("execute_paid_change", paid_arguments))[
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
                                "execute_change",
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
                                "execute_change",
                                changes
                                | {"request_id": str(uuid4()), "target_id": True},
                            )
                        )["isError"]
                    )
                    await sync_to_async(
                        type(self.token).objects.filter(pk=self.token.pk).update
                    )(scope=READ)
                    self.assertTrue((await tool("execute_change", changes))["isError"])
                    await sync_to_async(self.token.delete)()
                    self.assertEqual((await rpc("tools/list")).status_code, 401)

        async_to_sync(exercise)()
