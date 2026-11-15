"""Disabled-profile imports and actionable errors without private exception text."""

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase

from .. import services


class DisabledDiscoveryTests(SimpleTestCase):
    def test_domain_app_and_registry_import_do_not_require_enabled_oauth_models(self):
        from ..server import Action

        self.assertIn("meal.delete", Action.__args__)
        self.assertEqual(len(services.OPERATIONS), 19)

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
            raise services.OperationError("Inspect current records and preview again.")

        with self.assertRaisesMessage(
            server.ToolError, "Inspect current records and preview again."
        ):
            async_to_sync(server.call)(invalid)
