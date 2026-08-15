import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage, get_connection
from django.test import override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class RegistrationTests(APITestCase):
    def test_register_creates_user_and_returns_session(self):
        response = self.client.post(
            "/auth/register/",
            {"email": "mapper@example.com", "password": "test_password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        user = User.objects.get(email="mapper@example.com")
        self.assertEqual(user.username, "mapper")
        self.assertEqual(response.data["username"], "mapper")
        self.assertEqual(response.data["email"], "mapper@example.com")
        self.assertTrue(response.data["access"])
        self.assertTrue(response.data["refresh"])

    def test_register_accepts_an_explicit_username(self):
        response = self.client.post(
            "/auth/register/",
            {
                "email": "mapper@example.com",
                "username": "macro_mapper",
                "password": "test_password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            User.objects.get(email="mapper@example.com").username, "macro_mapper"
        )

    def test_register_makes_derived_usernames_unique(self):
        User.objects.create_user(
            username="mapper",
            email="first@example.com",
            password="test_password",
        )

        response = self.client.post(
            "/auth/register/",
            {"email": "mapper@example.com", "password": "test_password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            User.objects.get(email="mapper@example.com").username, "mapper01"
        )

    def test_register_rejects_missing_credentials(self):
        response = self.client.post("/auth/register/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Email and password required.")

    def test_register_rejects_invalid_or_duplicate_email(self):
        invalid = self.client.post(
            "/auth/register/",
            {"email": "not-an-email", "password": "test_password"},
            format="json",
        )
        User.objects.create_user(
            username="existing",
            email="existing@example.com",
            password="test_password",
        )
        duplicate = self.client.post(
            "/auth/register/",
            {"email": "EXISTING@example.com", "password": "test_password"},
            format="json",
        )

        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid.data["error"], "Invalid email address.")
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(duplicate.data["error"], "Email already exists.")


class LoginAndRefreshTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="mapper",
            email="mapper@example.com",
            password="test_password",
        )

    def test_login_with_email_returns_tokens_and_profile(self):
        response = self.client.post(
            "/auth/login/",
            {"email": "MAPPER@example.com", "password": "test_password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data["access"])
        self.assertTrue(response.data["refresh"])
        self.assertEqual(response.data["username"], "mapper")
        self.assertEqual(response.data["email"], "mapper@example.com")

    def test_login_rejects_bad_credentials(self):
        response = self.client.post(
            "/auth/login/",
            {"email": "mapper@example.com", "password": "wrong"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_returns_a_new_access_token(self):
        login_response = self.client.post(
            "/auth/login/",
            {"email": "mapper@example.com", "password": "test_password"},
            format="json",
        )
        response = self.client.post(
            "/auth/refresh/",
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data["access"])


class PasswordResetTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="mapper",
            email="mapper@example.com",
            password="old_password_123",
        )

    @patch("authentication.views.send_mail")
    def test_forgot_password_sends_a_branded_reset_link(self, mock_send_mail):
        response = self.client.post(
            "/auth/forgot-password/",
            {"email": "mapper@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send_mail.assert_called_once()
        args = mock_send_mail.call_args.args
        self.assertEqual(args[0], "Reset your FullStackTemplate password")
        self.assertIn("/reset-password?uid=", args[1])
        self.assertIn("token=", args[1])

    @patch("authentication.views.send_mail")
    def test_forgot_password_does_not_disclose_unknown_accounts(self, mock_send_mail):
        response = self.client.post(
            "/auth/forgot-password/",
            {"email": "missing@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Password reset link has been sent!")
        mock_send_mail.assert_not_called()

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


class ResendApiEmailBackendTests(APITestCase):
    @override_settings(
        EMAIL_BACKEND="authentication.email_backends.ResendApiEmailBackend",
        EMAIL_HOST_PASSWORD="resend-api-key",
        EMAIL_TIMEOUT=7,
        DEFAULT_FROM_EMAIL="fullstacktemplate@example.com",
    )
    @patch("authentication.email_backends.request.urlopen")
    def test_send_messages_posts_to_resend_api(self, mock_urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.getcode.return_value = 200
        mock_urlopen.return_value = response

        sent_count = get_connection().send_messages(
            [
                EmailMessage(
                    "Reset your FullStackTemplate password",
                    "Use this link.",
                    None,
                    ["mapper@example.com"],
                )
            ]
        )

        self.assertEqual(sent_count, 1)
        request_arg = mock_urlopen.call_args.args[0]
        self.assertEqual(request_arg.full_url, "https://api.resend.com/emails")
        self.assertEqual(
            request_arg.get_header("Authorization"), "Bearer resend-api-key"
        )
        self.assertEqual(
            request_arg.get_header("User-agent"),
            "FullStackTemplate/1.0 (+https://app.example.com)",
        )
        payload = json.loads(request_arg.data.decode("utf-8"))
        self.assertEqual(payload["from"], "fullstacktemplate@example.com")
        self.assertEqual(payload["to"], ["mapper@example.com"])

    @override_settings(
        EMAIL_BACKEND="authentication.email_backends.ResendApiEmailBackend",
        EMAIL_HOST_PASSWORD="",
    )
    def test_send_messages_requires_api_key(self):
        with self.assertRaises(ValueError):
            get_connection().send_messages(
                [
                    EmailMessage(
                        "Subject",
                        "Body",
                        "fullstacktemplate@example.com",
                        ["mapper@example.com"],
                    )
                ]
            )
