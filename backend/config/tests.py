import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, SimpleTestCase, override_settings


class ProductionSettingsTests(SimpleTestCase):
    def settings_values(self, **values):
        with patch.dict(os.environ, values, clear=True), patch("dotenv.load_dotenv"):
            return runpy.run_path(str(Path(__file__).with_name("settings.py")))

    def production_values(self, **overrides):
        return self.settings_values(
            **{
                "DJANGO_DEBUG": "0",
                "DJANGO_SECRET_KEY": "test-only-generated-production-secret",
                "DJANGO_ALLOWED_HOSTS": " macromapper.judeandrewalaba.com ",
                "DJANGO_CORS_ALLOWED_ORIGINS": "https://macromapper.judeandrewalaba.com",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://macromapper.judeandrewalaba.com",
                **overrides,
            }
        )

    def test_development_keeps_local_defaults_and_http_cookies(self):
        values = self.settings_values()
        self.assertTrue(values["DEBUG"])
        self.assertIn("macromapper.localhost", values["ALLOWED_HOSTS"])
        self.assertFalse(values["SESSION_COOKIE_SECURE"])
        self.assertFalse(values["CSRF_COOKIE_SECURE"])

    def test_production_requires_explicit_secret_and_hosts(self):
        for missing in ("DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS"):
            with (
                self.subTest(missing=missing),
                self.assertRaisesMessage(ImproperlyConfigured, missing),
            ):
                self.production_values(**{missing: ""})

    def test_production_excludes_development_origins_and_secures_cookies(self):
        values = self.production_values()
        self.assertEqual(values["ALLOWED_HOSTS"], ["macromapper.judeandrewalaba.com"])
        for key in ("CORS_ALLOWED_ORIGINS", "CSRF_TRUSTED_ORIGINS"):
            self.assertEqual(values[key], ["https://macromapper.judeandrewalaba.com"])
        self.assertTrue(values["SESSION_COOKIE_SECURE"])
        self.assertTrue(values["CSRF_COOKIE_SECURE"])
        with override_settings(
            **{
                key: values[key]
                for key in (
                    "ALLOWED_HOSTS",
                    "USE_X_FORWARDED_HOST",
                    "SECURE_PROXY_SSL_HEADER",
                    "SESSION_COOKIE_SECURE",
                    "CSRF_COOKIE_SECURE",
                )
            }
        ):
            request = RequestFactory().get(
                "/admin/login/",
                HTTP_HOST="macromapper.judeandrewalaba.com",
                HTTP_X_FORWARDED_HOST="attacker.invalid",
                HTTP_X_FORWARDED_PROTO="https",
            )
            self.assertEqual(request.get_host(), "macromapper.judeandrewalaba.com")
            self.assertTrue(request.is_secure())
            response = self.client.get(
                "/admin/login/",
                HTTP_HOST="macromapper.judeandrewalaba.com",
                secure=True,
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.cookies["csrftoken"]["secure"])
