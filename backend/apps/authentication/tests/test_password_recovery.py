"""Generic recovery responses and malformed email inputs."""

from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from .helpers import CredentialFixtures, PasswordResetFixtures


class PasswordRecoveryTests(PasswordResetFixtures, APITestCase):
    @patch("apps.authentication.views.send_mail")
    def test_forgot_password_sends_a_branded_reset_link(self, mock_send_mail):
        response = self.client.post(
            "/auth/forgot-password/",
            {"email": "mapper@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send_mail.assert_called_once()
        args = mock_send_mail.call_args.args
        self.assertEqual(args[0], "Reset your MacroMapper password")
        self.assertIn("/reset-password?uid=", args[1])
        self.assertIn("token=", args[1])

    @patch("apps.authentication.views.send_mail")
    def test_forgot_password_does_not_disclose_unknown_accounts(self, mock_send_mail):
        response = self.client.post(
            "/auth/forgot-password/",
            {"email": "missing@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Password reset link has been sent!")
        mock_send_mail.assert_not_called()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PasswordRecoveryInputTests(CredentialFixtures, APITestCase):
    @patch("apps.authentication.views.send_mail")
    def test_forgot_password_rejects_non_string_email_without_sending(self, send_mail):
        for value in (123, True, [], {}, None):
            with self.subTest(value=value):
                response = self.client.post(
                    "/auth/forgot-password/", {"email": value}, format="json"
                )
                self.assertEqual(response.status_code, 400, response.data)
        send_mail.assert_not_called()
