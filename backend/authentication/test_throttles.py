from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase


@override_settings(AUTHENTICATION_THROTTLE_ENABLED=True, SECURE_SSL_REDIRECT=False)
class AuthenticationThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_login_rate_limit_ignores_forged_forwarding_headers(self):
        for index in range(10):
            response = self.client.post(
                "/auth/login/",
                {},
                format="json",
                HTTP_X_FORWARDED_FOR=f"192.0.2.{index}",
            )
            self.assertEqual(response.status_code, 400)
        response = self.client.post(
            "/auth/login/",
            {},
            format="json",
            HTTP_X_FORWARDED_FOR="198.51.100.1",
        )
        self.assertEqual(response.status_code, 429)

    def test_refresh_endpoint_uses_authentication_limit(self):
        for _ in range(10):
            self.client.post("/auth/refresh/", {}, format="json")
        response = self.client.post("/auth/refresh/", {}, format="json")
        self.assertEqual(response.status_code, 429)
