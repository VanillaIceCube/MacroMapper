from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import IntegrityError
from django.test import override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()

PRIVATE = "recipient@example.test reset?token=private-token sk-private-key private-body"


class RegistrationTests(APITestCase):
    def test_register_rejects_weak_password(self):
        response = self.client.post(
            "/auth/register/",
            {"email": "mapper@example.com", "password": "short"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("too short", response.data["error"].lower())
        self.assertFalse(User.objects.filter(email="mapper@example.com").exists())

    def test_register_rejects_common_numeric_and_user_similar_passwords(self):
        for password in ("password", "123456789012", "mapper", "macro_mapper"):
            with self.subTest(password=password):
                response = self.client.post(
                    "/auth/register/",
                    {
                        "email": "mapper@example.com",
                        "username": "macro_mapper",
                        "password": password,
                    },
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertFalse(
                    User.objects.filter(email="mapper@example.com").exists()
                )

    def test_register_checks_similarity_to_derived_username(self):
        response = self.client.post(
            "/auth/register/",
            {"email": "longusername@example.com", "password": "longusername"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("too similar", response.data["error"].lower())
        self.assertFalse(User.objects.filter(email="longusername@example.com").exists())

    def test_register_rejects_non_string_password_without_creating_user(self):
        for password in (123456789, ["long-password"], {"value": "long-password"}):
            with self.subTest(password=password):
                response = self.client.post(
                    "/auth/register/",
                    {"email": "invalid-password@example.com", "password": password},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertFalse(
                    User.objects.filter(email="invalid-password@example.com").exists()
                )

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

    @patch("apps.authentication.views.User.objects.create_user")
    def test_register_handles_integrity_error(self, mock_create_user):
        mock_create_user.side_effect = IntegrityError("UNIQUE constraint failed")

        response = self.client.post(
            "/auth/register/",
            {"email": "race@example.com", "password": "test_password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Email or username already exists.")

    def test_register_handles_empty_local_part_username(self):
        from apps.authentication.views import _build_unique_username

        self.assertEqual(_build_unique_username(""), "user")
        self.assertEqual(_build_unique_username("   "), "user")


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

    def test_login_normalizes_email_whitespace(self):
        response = self.client.post(
            "/auth/login/",
            {"email": "  mapper@example.com  ", "password": "test_password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["username"], "mapper")

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


@override_settings(
    EMAIL_BACKEND="apps.email.backends.ResendApiEmailBackend",
    EMAIL_HOST_PASSWORD="sk-private-key",
)
class PasswordResetFailurePrivacyTests(APITestCase):
    def setUp(self):
        get_user_model().objects.create_user(
            username="fixture",
            email="fixture@example.test",
            password="fixture-password-123",
        )

    @patch("apps.email.backends.request.urlopen")
    def test_real_reset_caller_keeps_failure_and_unknown_account_responses_equal(
        self, urlopen
    ):
        for exc in [
            HTTPError("https://api.resend.com/emails", 429, PRIVATE, {}, None),
            TimeoutError(PRIVATE),
            URLError(PRIVATE),
        ]:
            with self.subTest(error=type(exc).__name__):
                urlopen.reset_mock()
                urlopen.side_effect = exc
                with self.assertLogs("apps", level="ERROR") as logs:
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
                urlopen.assert_called_once()
                for record in logs.records:
                    self.assertIsNone(record.exc_info)
                    for private in [
                        "private-token",
                        "sk-private-key",
                        "recipient@example.test",
                        "fixture@example.test",
                        "user_id",
                        "private-body",
                    ]:
                        self.assertNotIn(private, record.getMessage())
