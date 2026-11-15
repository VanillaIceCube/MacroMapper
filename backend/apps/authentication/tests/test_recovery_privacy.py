"""Provider failures never disclose account or email details."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from .helpers import PRIVATE


@override_settings(
    EMAIL_BACKEND="anymail.backends.resend.EmailBackend",
    ANYMAIL={
        "RESEND_API_KEY": "sk-private-key",
        "REQUESTS_TIMEOUT": 10,
        "DEBUG_API_REQUESTS": False,
    },
)
class PasswordResetFailurePrivacyTests(APITestCase):
    def setUp(self):
        get_user_model().objects.create_user(
            username="fixture",
            email="fixture@example.test",
            password="fixture-password-123",
        )

    @patch("requests.sessions.Session.request")
    def test_real_reset_caller_keeps_failure_and_unknown_account_responses_equal(
        self, request
    ):
        response = requests.Response()
        response.status_code = 429
        response._content = PRIVATE.encode()
        response.headers["Content-Type"] = "text/plain"
        failures = [
            response,
            requests.Timeout(PRIVATE),
            requests.ConnectionError(PRIVATE),
        ]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                request.reset_mock()
                request.side_effect = (
                    failure if isinstance(failure, Exception) else None
                )
                request.return_value = failure
                output, errors = StringIO(), StringIO()
                with (
                    self.assertLogs("apps.authentication", level="ERROR") as logs,
                    redirect_stdout(output),
                    redirect_stderr(errors),
                ):
                    known = self.client.post(
                        "/auth/forgot-password/",
                        {"email": "fixture@example.test"},
                        format="json",
                    )
                unknown = self.client.post(
                    "/auth/forgot-password/",
                    {"email": "missing@example.test"},
                    format="json",
                )
                self.assertEqual(known.status_code, 200)
                self.assertEqual(known.data, unknown.data)
                request.assert_called_once()
                text = output.getvalue() + errors.getvalue()
                for record in logs.records:
                    self.assertIsNone(record.exc_info)
                    text += record.getMessage()
                for private in [
                    "private-token",
                    "sk-private-key",
                    "recipient@example.test",
                    "fixture@example.test",
                    "user_id",
                    "private-body",
                    "token=",
                ]:
                    self.assertNotIn(private, text)
