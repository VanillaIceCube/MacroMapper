"""JWT login, exact credentials and access-token renewal."""

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from .helpers import CredentialFixtures, User


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


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class LoginInputTests(CredentialFixtures, APITestCase):
    def test_login_normalizes_email_and_keeps_password_exact(self):
        response = self.client.post(
            "/auth/login/",
            {"email": " CONTRACT@EXAMPLE.COM ", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["email"], "contract@example.com")
