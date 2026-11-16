"""Account creation, duplicate identities and registration validation."""

from unittest.mock import patch

from django.db import IntegrityError
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from .helpers import CredentialFixtures, User


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


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RegistrationInputTests(CredentialFixtures, APITestCase):
    def test_registration_rejects_non_string_credentials_and_bad_payloads(self):
        count = User.objects.count()
        for field in ("email", "password", "username"):
            values = (123, True, [], {}) + ((None,) if field != "username" else ())
            for value in values:
                with self.subTest(field=field, value=value):
                    payload = {
                        "email": "new-contract@example.com",
                        "password": "New-Contract-Password-89!",
                    }
                    payload[field] = value
                    response = self.client.post(
                        "/auth/register/", payload, format="json"
                    )
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertIn("error", response.data)
                    self.assertEqual(User.objects.count(), count)
        response = self.client.post(
            "/auth/register/", ["not", "an", "object"], format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), count)

    def test_registration_preserves_password_and_normalizes_identity(self):
        password = "  New-Contract-Password-89!  "
        response = self.client.post(
            "/auth/register/",
            {
                "email": " NEW-CONTRACT@example.com ",
                "username": " new-contract ",
                "password": password,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email="new-contract@example.com")
        self.assertEqual(user.username, "new-contract")
        self.assertTrue(user.check_password(password))
        self.assertFalse(user.check_password(password.strip()))

    def test_registration_collision_is_a_client_error(self):
        from django.db import IntegrityError

        with patch(
            "apps.authentication.views.User.objects.create_user",
            side_effect=IntegrityError("duplicate"),
        ):
            response = self.client.post(
                "/auth/register/",
                {
                    "email": "new-contract@example.com",
                    "password": "New-Contract-Password-89!",
                },
                format="json",
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Email or username already exists."})
        self.assertFalse(User.objects.filter(email="new-contract@example.com").exists())

    def test_failed_session_creation_rolls_back_registration(self):
        with patch(
            "apps.authentication.views.RefreshToken.for_user",
            side_effect=RuntimeError("session unavailable"),
        ):
            with self.assertRaisesMessage(RuntimeError, "session unavailable"):
                self.client.post(
                    "/auth/register/",
                    {
                        "email": "new-contract@example.com",
                        "password": "New-Contract-Password-89!",
                    },
                    format="json",
                )
        self.assertFalse(User.objects.filter(email="new-contract@example.com").exists())
