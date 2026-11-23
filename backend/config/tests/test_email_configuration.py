"""Project email selection, credentials and bounded timeouts."""

import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from .helpers import BACKEND


class EmailConfigurationTests(SimpleTestCase):
    def settings_values(self, **values):
        with patch.dict(os.environ, values, clear=True), patch("dotenv.load_dotenv"):
            return runpy.run_path(
                str(Path(__file__).resolve().parents[1] / "settings.py")
            )

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

    def test_explicit_backend_selectors_are_not_rewritten(self):
        for backend in [
            BACKEND,
            "authentication.email_backends.ResendApiEmailBackend",
            "apps.authentication.email_backends.ResendApiEmailBackend",
            "apps.email.backends.ResendApiEmailBackend",
        ]:
            with self.subTest(backend=backend):
                values = self.settings_values(DJANGO_EMAIL_BACKEND=backend)
                self.assertEqual(values["EMAIL_BACKEND"], backend)

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
