"""Disabled-profile imports and actionable errors without private exception text."""

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase

from .. import operations


class DisabledDiscoveryTests(SimpleTestCase):
    def test_domain_app_and_registry_import_do_not_require_enabled_oauth_models(self):
        from ..server import Action

        self.assertIn("meal.delete", Action.__args__)
        self.assertEqual(len(operations.OPERATIONS), 19)

    def test_failure_reference_correlates_without_private_exception_text(self):
        from .. import server

        def invalid_operation(raw):
            raise ValueError("private-provider-or-meal-text")

        with self.assertLogs(server.logger, level="WARNING") as logs:
            with self.assertRaises(server.ToolError) as failure:
                async_to_sync(server.call)(invalid_operation)
        message = str(failure.exception)
        self.assertIn("reference ", message)
        self.assertIn("list_proposals", message)
        self.assertIn("category=ValueError", logs.output[0])
        self.assertNotIn("private-provider-or-meal-text", message + logs.output[0])
        self.assertIn(message.split("reference ")[1].split(")")[0], logs.output[0])


class SafeGuidanceTests(SimpleTestCase):
    def test_fixed_guidance_survives_tool_error_sanitization(self):
        from .. import server

        def invalid(raw):
            raise operations.OperationError(
                "Inspect current records before another operation."
            )

        with self.assertRaisesMessage(
            server.ToolError, "Inspect current records before another operation."
        ):
            async_to_sync(server.call)(invalid)


class ConnectionErrorTests(SimpleTestCase):
    def test_reconnectable_failure_preserves_required_scope_metadata(self):
        from apps.mcp.framework.errors import ConnectionPermissionDenied

        from .. import server
        from ..permissions import ESTIMATE, READ, WRITE

        def denied(raw):
            raise ConnectionPermissionDenied(
                "private-token-value",
                "insufficient_scope",
                required_scopes=[READ, WRITE, ESTIMATE],
            )

        output = async_to_sync(server.call)(denied).model_dump(by_alias=True)
        self.assertTrue(output["isError"])
        self.assertIn(
            'scope="macromapper:read macromapper:write macromapper:estimate"',
            output["_meta"]["mcp/www_authenticate"][0],
        )
        self.assertNotIn("private-token-value", str(output))

    def test_object_permission_denial_does_not_request_reconnection(self):
        from django.core.exceptions import PermissionDenied

        from .. import server

        def denied(raw):
            raise PermissionDenied("private-record")

        with self.assertRaisesMessage(
            server.ToolError, "MCP permission denied"
        ) as failure:
            async_to_sync(server.call)(denied)
        self.assertNotIn("private-record", str(failure.exception))

    def test_unexpected_provider_failure_is_sanitized(self):
        from .. import server

        def unavailable(raw):
            raise RuntimeError("private-provider-response")

        with self.assertLogs(server.logger, level="WARNING") as logs:
            with self.assertRaises(server.ToolError) as failure:
                async_to_sync(server.call)(unavailable)
        self.assertIn("reference ", str(failure.exception))
        self.assertNotIn(
            "private-provider-response", str(failure.exception) + str(logs.output)
        )
