"""Reset-link validation and exact replacement-password handling."""

from django.contrib.auth.tokens import default_token_generator
from django.test import override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

from .helpers import CredentialFixtures, PasswordResetFixtures


class PasswordResetTests(PasswordResetFixtures, APITestCase):
    def test_reset_password_updates_the_user(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        response = self.client.post(
            "/auth/reset-password/",
            {"uid": uid, "token": token, "password": "new_password_123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new_password_123!"))

    def test_reset_password_rejects_invalid_link(self):
        response = self.client.post(
            "/auth/reset-password/",
            {"uid": "invalid", "token": "invalid", "password": "new_password_123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Invalid or expired reset link.")

    def test_reset_password_rejects_non_integer_decoded_uid(self):
        non_int_uid = urlsafe_base64_encode(force_bytes("not-an-int"))

        response = self.client.post(
            "/auth/reset-password/",
            {
                "uid": non_int_uid,
                "token": "invalid-token",
                "password": "new_password_123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Invalid or expired reset link.")


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PasswordResetInputTests(CredentialFixtures, APITestCase):
    def test_reset_rejects_non_string_inputs_without_changing_password(self):
        for field in ("uid", "token", "password"):
            for value in (123, True, [], {}, None):
                with self.subTest(field=field, value=value):
                    payload = self.reset_payload()
                    payload[field] = value
                    response = self.client.post(
                        "/auth/reset-password/", payload, format="json"
                    )
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertIn("error", response.data)
                    self.user.refresh_from_db()
                    self.assertTrue(self.user.check_password(self.password))
        response = self.client.post(
            "/auth/reset-password/", ["not", "an", "object"], format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_reset_preserves_spaces_and_invalidates_used_link(self):
        payload = self.reset_payload()
        payload["password"] = "  Updated-Contract-Password-89!  "
        response = self.client.post("/auth/reset-password/", payload, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(payload["password"]))
        self.assertFalse(self.user.check_password(payload["password"].strip()))
        for password, expected in (
            (payload["password"], 200),
            (payload["password"].strip(), 401),
        ):
            login = self.client.post(
                "/auth/login/",
                {"email": self.user.email, "password": password},
                format="json",
            )
            self.assertEqual(login.status_code, expected, login.data)
        reused = self.client.post("/auth/reset-password/", payload, format="json")
        self.assertEqual(reused.status_code, 400)
