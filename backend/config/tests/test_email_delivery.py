"""Mocked Resend transport and standard Anymail behavior."""

import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

import requests
from anymail.exceptions import AnymailAPIError, AnymailConfigurationError
from django.core.mail import EmailMessage, EmailMultiAlternatives, get_connection
from django.test import SimpleTestCase, override_settings

from .helpers import BACKEND, PRIVATE, api_response


@override_settings(
    EMAIL_BACKEND=BACKEND,
    DEFAULT_FROM_EMAIL="App <no-reply@example.test>",
    ANYMAIL={
        "RESEND_API_KEY": "sk-private-key",
        "REQUESTS_TIMEOUT": 7,
        "DEBUG_API_REQUESTS": False,
    },
)
class EmailDeliveryTests(SimpleTestCase):
    def message(self):
        return EmailMessage("private-subject", PRIVATE, to=["recipient@example.test"])

    @patch("requests.sessions.Session.request")
    def test_empty_batch_and_formatted_message_use_the_supported_http_boundary(
        self, request
    ):
        request.return_value = api_response()
        self.assertEqual(get_connection().send_messages([]), 0)
        request.assert_not_called()
        message = EmailMultiAlternatives(
            "private-subject",
            "plain body",
            to=["recipient@example.test"],
            cc=["copy@example.test"],
            bcc=["hidden@example.test"],
            reply_to=["reply@example.test"],
        )
        message.attach_alternative("<p>HTML body</p>", "text/html")
        self.assertEqual(get_connection().send_messages([message]), 1)
        request.assert_called_once()
        sent = request.call_args.kwargs
        self.assertEqual(sent["url"], "https://api.resend.com/emails")
        self.assertEqual(sent["method"], "POST")
        self.assertEqual(sent["headers"]["Authorization"], "Bearer sk-private-key")
        self.assertEqual(sent["timeout"], 7)
        payload = json.loads(sent["data"])
        self.assertEqual(payload["from"], "App <no-reply@example.test>")
        self.assertEqual(payload["to"], ["recipient@example.test"])
        self.assertEqual(payload["cc"], ["copy@example.test"])
        self.assertEqual(payload["bcc"], ["hidden@example.test"])
        self.assertEqual(payload["reply_to"], ["reply@example.test"])
        self.assertEqual(payload["text"], "plain body")
        self.assertEqual(payload["html"], "<p>HTML body</p>")

    def test_session_has_no_automatic_retries_or_request_dump_hook(self):
        connection = get_connection()
        connection.open()
        try:
            self.assertIs(connection.debug_api_requests, False)
            self.assertEqual(connection.session.hooks["response"], [])
            for adapter in connection.session.adapters.values():
                self.assertEqual(adapter.max_retries.total, 0)
        finally:
            connection.close()

    @override_settings(ANYMAIL={"REQUESTS_TIMEOUT": 10, "DEBUG_API_REQUESTS": False})
    @patch("requests.sessions.Session.request")
    def test_missing_api_key_is_a_visible_configuration_error_before_http(
        self, request
    ):
        with self.assertRaises(AnymailConfigurationError):
            get_connection()
        request.assert_not_called()

    @patch("requests.sessions.Session.request")
    def test_operational_errors_respect_silent_mode_without_retries_or_private_output(
        self, request
    ):
        cases = [
            api_response(code, {"message": PRIVATE})
            for code in [400, 401, 403, 422, 429, 500, 503]
        ]
        cases += [requests.Timeout(PRIVATE), requests.ConnectionError(PRIVATE)]
        for failure in cases:
            for silent in [False, True]:
                with self.subTest(failure=type(failure).__name__, silent=silent):
                    request.reset_mock()
                    request.side_effect = (
                        failure if isinstance(failure, Exception) else None
                    )
                    request.return_value = failure
                    output, errors = StringIO(), StringIO()
                    with (
                        self.assertNoLogs(level="WARNING"),
                        redirect_stdout(output),
                        redirect_stderr(errors),
                    ):
                        if silent:
                            self.assertEqual(
                                get_connection(fail_silently=True).send_messages(
                                    [self.message()]
                                ),
                                0,
                            )
                        else:
                            with self.assertRaises(AnymailAPIError):
                                get_connection(fail_silently=False).send_messages(
                                    [self.message()]
                                )
                    request.assert_called_once()
                    self.assertEqual(output.getvalue(), "")
                    self.assertEqual(errors.getvalue(), "")

    @patch("requests.sessions.Session.request")
    def test_partial_batch_counts_success_without_retrying_or_continuing_after_a_raised_failure(
        self, request
    ):
        request.side_effect = [requests.Timeout(PRIVATE), api_response()]
        self.assertEqual(
            get_connection(fail_silently=True).send_messages(
                [self.message(), self.message()]
            ),
            1,
        )
        self.assertEqual(request.call_count, 2)
        request.reset_mock()
        request.side_effect = [requests.Timeout(PRIVATE), api_response()]
        with self.assertRaises(AnymailAPIError):
            get_connection(fail_silently=False).send_messages(
                [self.message(), self.message()]
            )
        request.assert_called_once()
