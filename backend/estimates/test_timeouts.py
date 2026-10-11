import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import BoundedSemaphore, Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from foods.models import FoodItem, FoodItemVersion
from foods.services import create_food_item

from .models import MealProposal
from .provider import EstimationProviderError, OpenAIMealEstimationProvider
from .services import _catalog_food, create_proposal, save_meal_draft


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


class EstimationTransactionTests(TransactionTestCase):
    def _draft(self):
        owner = get_user_model().objects.create_user(
            username="draft-owner", email="draft-owner@example.com"
        )
        food = create_food_item(
            name="Toast",
            scope=FoodItem.Scope.PERSONAL,
            owner=owner,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            definition={
                "serving_quantity": Decimal("1"),
                "serving_unit": FoodItemVersion.ServingUnit.ITEM,
                "serving_label": "1 toast",
                "provenance": FoodItemVersion.Provenance.USER_ENTERED,
                "confidence_score": None,
                "nutrients": {"calories": Decimal("100")},
                "sources": [],
                "components": [],
            },
            created_by=owner,
        )
        return (
            owner,
            food,
            {
                "owner": owner,
                "meal": None,
                "entry_date": "2026-10-11",
                "name": "",
                "notes": "",
                "items": [_catalog_food(food.current_version, servings=Decimal("1"))],
            },
        )

    def test_blank_name_wait_allows_a_concurrent_database_write(self):
        _, _, draft = self._draft()

        def ordinary_write():
            try:
                get_user_model().objects.create_user(
                    username="name-concurrent", email="name-concurrent@example.com"
                )
            finally:
                connections.close_all()

        def generate_name(selected_foods):
            self.assertFalse(connections["default"].in_atomic_block)
            self.assertEqual(selected_foods[0]["name"], "Toast")
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(ordinary_write).result(timeout=2)
            return "Named toast"

        provider = Mock()
        provider.generate_name.side_effect = generate_name
        with patch("meals.services.get_estimation_provider", return_value=provider):
            meal = save_meal_draft(**draft)
        self.assertEqual(meal.name, "Named toast")
        self.assertEqual(meal.items.count(), 1)
        self.assertTrue(
            get_user_model().objects.filter(username="name-concurrent").exists()
        )

    def test_blank_name_draft_revalidates_food_archived_during_ai_wait(self):
        _, food, draft = self._draft()

        def generate_name(selected_foods):
            FoodItem.objects.filter(pk=food.pk).update(archived_at=timezone.now())
            return "Named toast"

        provider = Mock()
        provider.generate_name.side_effect = generate_name
        with patch("meals.services.get_estimation_provider", return_value=provider):
            with self.assertRaises(ValidationError):
                save_meal_draft(**draft)
        self.assertFalse(draft["owner"].meal_entries.exists())

    def test_publication_and_proposal_roll_back_if_revision_fails(self):
        owner = get_user_model().objects.create_user(
            username="rollback-owner", email="rollback@example.com"
        )
        provider = Mock()
        provider.extract_intents.return_value = None
        provider.estimate.return_value = {
            "name": "Synthetic meal",
            "confidence_score": 0.8,
            "provider_name": "fake",
            "provider_model": "fake",
            "provider_response_id": "fake",
        }

        def publish(estimate):
            FoodItem.objects.create(name="Synthetic published food", scope="shared")
            return []

        with (
            patch("estimates.services.get_estimation_provider", return_value=provider),
            patch("estimates.services._shared_estimate_items", side_effect=publish),
            patch(
                "estimates.services.create_proposal_revision",
                side_effect=RuntimeError("Synthetic revision failure"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "revision failure"):
                create_proposal(
                    owner=owner, description="Unknown meal", entry_date="2026-10-11"
                )
        self.assertFalse(FoodItem.objects.exists())
        self.assertFalse(MealProposal.objects.exists())

    def test_provider_wait_does_not_hold_a_sqlite_read_transaction(self):
        owner = get_user_model().objects.create_user(
            username="estimate-owner", email="estimate-owner@example.com"
        )

        def ordinary_write():
            try:
                get_user_model().objects.create_user(
                    username="concurrent-request", email="concurrent@example.com"
                )
            finally:
                connections.close_all()

        def estimate(description):
            self.assertFalse(connections["default"].in_atomic_block)
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(ordinary_write).result(timeout=2)
            raise EstimationProviderError("Synthetic provider failure")

        provider = Mock()
        provider.extract_intents.return_value = None
        provider.estimate.side_effect = estimate
        with patch("estimates.services.get_estimation_provider", return_value=provider):
            with self.assertRaises(EstimationProviderError):
                create_proposal(
                    owner=owner,
                    description="Unknown mixed meal",
                    entry_date="2026-10-11",
                )
        self.assertTrue(
            get_user_model().objects.filter(username="concurrent-request").exists()
        )
        self.assertFalse(MealProposal.objects.exists())
