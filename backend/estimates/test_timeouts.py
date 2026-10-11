import time
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from .models import MealProposal
from .provider import EstimationProviderError, OpenAIMealEstimationProvider


@override_settings(OPENAI_API_KEY="test-key", OPENAI_MEAL_ESTIMATION_TIMEOUT=110)
class ProviderDeadlineTests(SimpleTestCase):
    def test_sequential_calls_share_remaining_budget(self):
        clock = Mock(monotonic=Mock(return_value=10))
        client = Mock()
        with patch("estimates.provider.time", clock):
            provider = OpenAIMealEstimationProvider(client=client)
            clock.monotonic.return_value = 40
            provider._parse(model="test")
            self.assertEqual(client.responses.parse.call_args.kwargs["timeout"], 80)
            clock.monotonic.return_value = 90
            provider._parse(model="test")
            self.assertEqual(client.responses.parse.call_args.kwargs["timeout"], 30)
            clock.monotonic.return_value = 120
            with self.assertRaises(EstimationProviderError):
                provider._parse(model="test")
            self.assertEqual(client.responses.parse.call_count, 2)

    def test_sdk_retries_are_disabled(self):
        with patch("estimates.provider.OpenAI") as sdk:
            OpenAIMealEstimationProvider()
        self.assertEqual(sdk.call_args.kwargs["max_retries"], 0)

    @override_settings(OPENAI_MEAL_ESTIMATION_TIMEOUT=0.05)
    def test_wall_deadline_returns_while_sdk_call_is_still_blocked(self):
        release = Event()
        entered = Event()

        def slow_call(**kwargs):
            entered.set()
            release.wait(2)
            return SimpleNamespace(output_parsed=None)

        client = Mock()
        client.responses.parse.side_effect = slow_call
        # Isolate the pool; release abandoned I/O before the executor is joined.
        with ThreadPoolExecutor(max_workers=1) as executor:
            with (
                patch("estimates.provider._PROVIDER_EXECUTOR", executor),
                patch("estimates.provider._PROVIDER_SLOTS", BoundedSemaphore(1)),
            ):
                try:
                    provider = OpenAIMealEstimationProvider(client=client)
                    started = time.monotonic()
                    with self.assertRaises(EstimationProviderError):
                        provider.estimate("toast")
                    self.assertTrue(entered.is_set())
                    self.assertLess(time.monotonic() - started, 0.5)
                    # A timed-out running call retains capacity; no growing queue.
                    with self.assertRaisesRegex(EstimationProviderError, "busy"):
                        OpenAIMealEstimationProvider(client=client)._parse(model="test")
                    self.assertEqual(client.responses.parse.call_count, 1)
                finally:
                    release.set()


@override_settings(OPENAI_API_KEY="test-key", OPENAI_MEAL_ESTIMATION_TIMEOUT=0.05)
class DeadlineResponseTests(TestCase):
    def test_deadline_returns_json_503_without_publishing_a_late_proposal(self):
        release = Event()
        client = Mock()
        client.responses.parse.side_effect = lambda **kwargs: release.wait(2)
        api = APIClient()
        api.force_authenticate(
            get_user_model().objects.create_user(
                username="cap", email="cap@example.com"
            )
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            with (
                patch("estimates.provider._PROVIDER_EXECUTOR", executor),
                patch("estimates.provider._PROVIDER_SLOTS", BoundedSemaphore(1)),
                patch(
                    "estimates.services.get_estimation_provider",
                    return_value=OpenAIMealEstimationProvider(client=client),
                ),
            ):
                try:
                    response = api.post(
                        "/api/meal-proposals/",
                        {
                            "description": "Unknown mixed meal",
                            "entry_date": "2026-10-11",
                        },
                        format="json",
                    )
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response["Content-Type"], "application/json")
                    self.assertIn("log the meal manually", response.data["detail"])
                finally:
                    release.set()
        self.assertFalse(MealProposal.objects.exists())
