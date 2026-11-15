"""Application settings and mocked HTTP contracts for the maintained email backend."""

import json
import os
import runpy
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import requests
from anymail.exceptions import AnymailAPIError, AnymailConfigurationError
from django.core.mail import EmailMessage, EmailMultiAlternatives, get_connection
from django.test import SimpleTestCase, override_settings

BACKEND = "anymail.backends.resend.EmailBackend"
PRIVATE = "recipient@example.test reset?token=private-token sk-private-key private-body"


def api_response(status=200, body=None):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(body or {"id": "synthetic-message-id"}).encode()
    response.headers["Content-Type"] = "application/json"
    return response


class EmailConfigurationTests(SimpleTestCase):
    def settings_values(self, **values):
        with patch.dict(os.environ, values, clear=True), patch("dotenv.load_dotenv"):
            return runpy.run_path(str(Path(__file__).with_name("settings.py")))

    def test_console_default_and_custom_smtp_selection_are_preserved(self):
        default = self.settings_values()
        self.assertEqual(
            default["EMAIL_BACKEND"], "django.core.mail.backends.console.EmailBackend"
        )
        self.assertIn("anymail", default["INSTALLED_APPS"])
        for backend in [
            "django.core.mail.backends.smtp.EmailBackend",
            "example.custom.EmailBackend",
        ]:
            with self.subTest(backend=backend):
                values = self.settings_values(DJANGO_EMAIL_BACKEND=backend)
                self.assertEqual(values["EMAIL_BACKEND"], backend)

    def test_existing_backend_selectors_use_the_maintained_backend(self):
        for backend in [
            BACKEND,
            "authentication.email_backends.ResendApiEmailBackend",
            "apps.authentication.email_backends.ResendApiEmailBackend",
            "apps.email.backends.ResendApiEmailBackend",
        ]:
            with self.subTest(backend=backend):
                values = self.settings_values(DJANGO_EMAIL_BACKEND=backend)
                self.assertEqual(values["EMAIL_BACKEND"], BACKEND)

    def test_existing_key_maps_without_mutation_and_blank_keys_are_omitted(self):
        values = self.settings_values(DJANGO_EMAIL_HOST_KEY=" synthetic-key ")
        self.assertEqual(values["EMAIL_HOST_PASSWORD"], " synthetic-key ")
        self.assertEqual(values["ANYMAIL"]["RESEND_API_KEY"], " synthetic-key ")
        for key in ["", "   "]:
            with self.subTest(key=repr(key)):
                values = self.settings_values(DJANGO_EMAIL_HOST_KEY=key)
                self.assertNotIn("RESEND_API_KEY", values["ANYMAIL"])

    def test_timeout_is_bounded_and_request_dumps_stay_disabled(self):
        for timeout, expected in [
            ("1", 1),
            ("7", 7),
            ("30", 30),
            ("0", 10),
            ("-1", 10),
            ("31", 10),
        ]:
            with self.subTest(timeout=timeout):
                values = self.settings_values(DJANGO_EMAIL_TIMEOUT=timeout)
                self.assertEqual(values["ANYMAIL"]["REQUESTS_TIMEOUT"], expected)
                self.assertIs(values["ANYMAIL"]["DEBUG_API_REQUESTS"], False)
        self.assertEqual(self.settings_values()["ANYMAIL"]["REQUESTS_TIMEOUT"], 10)
        with self.assertRaises(ValueError):
            self.settings_values(DJANGO_EMAIL_TIMEOUT="not-an-integer")


@override_settings(
    EMAIL_BACKEND=BACKEND,
    DEFAULT_FROM_EMAIL="App <no-reply@example.test>",
    ANYMAIL={
        "RESEND_API_KEY": "sk-private-key",
        "REQUESTS_TIMEOUT": 7,
        "DEBUG_API_REQUESTS": False,
    },
)
class AnymailDeliveryTests(SimpleTestCase):
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
