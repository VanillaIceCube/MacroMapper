"""AI-assisted adjustments and reviewed meal drafts without premature diary writes."""

from decimal import Decimal
from unittest.mock import Mock, patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.estimates.models import MealProposal
from apps.estimates.provider import EstimationProviderError
from apps.estimates.services import _catalog_food
from apps.foods.models import FoodItem
from apps.foods.services import (
    create_food_item,
)

from ..models import MealEntry, MealItem
from .helpers import MealEntryFixtures, definition


class MealDraftTests(MealEntryFixtures, APITestCase):
    @patch("apps.meals.views.get_estimation_provider")
    def test_ai_adjustment_returns_an_editable_draft_without_changing_meal(
        self, get_provider
    ):
        created = self.create_meal(
            item_inputs=[{"food_item": self.apple.id, "servings": "1", "order": 0}]
        )
        item = _catalog_food(
            self.apple.current_version,
            servings=Decimal("1"),
            key="saved-apple",
        )
        provider = Mock()
        provider.follow_up.return_value = {
            "name": "Breakfast",
            "message": "Changed the apple to two servings.",
            "confidence_score": Decimal("0.9"),
            "remove_keys": [],
            "serving_updates": [{"key": "saved-apple", "servings": Decimal("2")}],
            "items_to_add": [],
            "provider_name": "OpenAI",
            "provider_model": "gpt-test",
            "provider_response_id": "resp-edit-meal",
        }
        get_provider.return_value = provider

        response = self.client.post(
            f"/api/meals/{created.data['id']}/adjustments/",
            {
                "adjustment": "Make that two apples",
                "entry_date": "2026-08-16",
                "name": "Breakfast",
                "notes": "Before work",
                "items": [item],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data["applied"])
        self.assertEqual(
            Decimal(response.data["proposal"]["items"][0]["servings"]),
            Decimal("2"),
        )
        self.assertEqual(MealProposal.objects.count(), 0)
        saved_item = MealItem.objects.get(meal_entry_id=created.data["id"])
        self.assertEqual(saved_item.servings, Decimal("1"))

    @patch("apps.meals.views.get_estimation_provider")
    def test_ai_adjustment_preserves_an_archived_version_pinned_to_the_meal(
        self, get_provider
    ):
        created = self.create_meal(
            item_inputs=[{"food_item": self.apple.id, "servings": "1", "order": 0}]
        )
        saved_version_id = created.data["items"][0]["food_version_id"]
        item = _catalog_food(
            self.apple.current_version,
            servings=Decimal("1"),
            key="saved-apple",
        )
        archive_response = self.client.delete(f"/api/foods/{self.apple.id}/")
        self.assertEqual(archive_response.status_code, status.HTTP_204_NO_CONTENT)
        provider = Mock()
        provider.follow_up.return_value = {
            "name": "Breakfast",
            "message": "Changed the apple to two servings.",
            "confidence_score": Decimal("0.9"),
            "remove_keys": [],
            "serving_updates": [{"key": "saved-apple", "servings": Decimal("2")}],
            "items_to_add": [],
            "provider_name": "OpenAI",
            "provider_model": "gpt-test",
            "provider_response_id": "resp-archived-edit-meal",
        }
        get_provider.return_value = provider

        response = self.client.post(
            f"/api/meals/{created.data['id']}/adjustments/",
            {
                "adjustment": "Make that two apples",
                "entry_date": "2026-08-16",
                "name": "Breakfast",
                "notes": "Before work",
                "items": [item],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        adjusted_item = response.data["proposal"]["items"][0]
        self.assertEqual(adjusted_item["food_version_id"], saved_version_id)
        self.assertEqual(Decimal(adjusted_item["servings"]), Decimal("2"))
        self.assertEqual(MealProposal.objects.count(), 0)
        saved_item = MealItem.objects.get(meal_entry_id=created.data["id"])
        self.assertEqual(saved_item.food_version_id, saved_version_id)
        self.assertEqual(saved_item.servings, Decimal("1"))

    @patch("apps.meals.views.get_estimation_provider")
    def test_ai_adjustment_deletes_temporary_proposal_on_provider_error(
        self, get_provider
    ):
        created = self.create_meal(
            item_inputs=[{"food_item": self.apple.id, "servings": "1", "order": 0}]
        )
        item = _catalog_food(
            self.apple.current_version,
            servings=Decimal("1"),
            key="saved-apple",
        )
        provider = Mock()
        provider.follow_up.side_effect = EstimationProviderError("Provider unavailable")
        get_provider.return_value = provider

        response = self.client.post(
            f"/api/meals/{created.data['id']}/adjustments/",
            {
                "adjustment": "Make that two apples",
                "entry_date": "2026-08-16",
                "name": "Breakfast",
                "notes": "Before work",
                "items": [item],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE, response.data
        )
        self.assertEqual(MealProposal.objects.count(), 0)

    @patch("apps.meals.views.get_estimation_provider")
    def test_ai_adjustment_deletes_temporary_proposal_on_unexpected_exception(
        self, get_provider
    ):
        created = self.create_meal(
            item_inputs=[{"food_item": self.apple.id, "servings": "1", "order": 0}]
        )
        item = _catalog_food(
            self.apple.current_version,
            servings=Decimal("1"),
            key="saved-apple",
        )
        provider = Mock()
        provider.follow_up.side_effect = RuntimeError("Unexpected internal failure")
        get_provider.return_value = provider

        with self.assertRaises(RuntimeError):
            self.client.post(
                f"/api/meals/{created.data['id']}/adjustments/",
                {
                    "adjustment": "Make that two apples",
                    "entry_date": "2026-08-16",
                    "name": "Breakfast",
                    "notes": "Before work",
                    "items": [item],
                },
                format="json",
            )

        self.assertEqual(MealProposal.objects.count(), 0)

    def test_full_draft_create_materializes_reviewed_nutrition(self):
        self.client.force_authenticate(user=self.owner)
        item = _catalog_food(
            self.apple.current_version,
            servings=Decimal("1"),
            key="manual-apple",
        )
        item["nutrients"]["calories"] = "120"

        response = self.client.post(
            "/api/meals/drafts/",
            {
                "entry_date": "2026-08-16",
                "name": "Reviewed apple",
                "notes": "Adjusted before saving.",
                "items": [item],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        saved_item = MealItem.objects.get(meal_entry_id=response.data["id"])
        self.assertEqual(saved_item.calories, Decimal("120"))
        self.assertEqual(saved_item.food_version.provenance, "user_modified_estimate")
        self.assertEqual(
            saved_item.food_version.derived_from_id,
            self.apple.current_version_id,
        )
        self.assertEqual(saved_item.food_version.food_item.owner, self.owner)

    def test_full_draft_update_preserves_meal_and_materializes_component_edit(self):
        composite = create_food_item(
            name="Apple toast",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.owner,
            definition=definition(
                components=[
                    {"food_item": self.apple, "servings": Decimal("1"), "order": 0},
                    {"food_item": self.toast, "servings": Decimal("1"), "order": 1},
                ],
            ),
            created_by=self.owner,
        )
        created = self.create_meal(
            item_inputs=[
                {"food_item": self.apple.id, "servings": "1", "order": 0},
                {"food_item": composite.id, "servings": "1", "order": 1},
            ]
        )
        apple_version_id = created.data["items"][0]["food_version_id"]
        composite_version_id = created.data["items"][1]["food_version_id"]
        apple_item = _catalog_food(
            self.apple.current_version,
            servings=Decimal("2"),
            key="saved-apple",
        )
        composite_item = _catalog_food(
            composite.current_version,
            servings=Decimal("1"),
            key="saved-composite",
        )
        composite_item["components"][0]["servings"] = "3"

        response = self.client.put(
            f"/api/meals/{created.data['id']}/draft/",
            {
                "entry_date": "2026-08-17",
                "name": "Updated breakfast",
                "notes": "Same meal, richer draft.",
                "items": [apple_item, composite_item],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["id"], created.data["id"])
        self.assertEqual(MealEntry.objects.count(), 1)
        saved_items = list(MealItem.objects.filter(meal_entry_id=created.data["id"]))
        self.assertEqual(saved_items[0].food_version_id, apple_version_id)
        self.assertEqual(saved_items[0].servings, Decimal("2"))
        self.assertNotEqual(saved_items[1].food_version_id, composite_version_id)
        self.assertEqual(
            saved_items[1].food_version.derived_from_id,
            composite_version_id,
        )
        self.assertEqual(
            saved_items[1].food_version.components.order_by("order").first().servings,
            Decimal("3"),
        )

    def test_full_draft_update_can_modify_a_version_pinned_before_archiving(self):
        created = self.create_meal(
            item_inputs=[{"food_item": self.apple.id, "servings": "1", "order": 0}]
        )
        saved_version_id = created.data["items"][0]["food_version_id"]
        archive_response = self.client.delete(f"/api/foods/{self.apple.id}/")
        self.assertEqual(archive_response.status_code, status.HTTP_204_NO_CONTENT)
        item = _catalog_food(
            self.apple.current_version,
            servings=Decimal("1"),
            key="archived-apple",
        )
        item["nutrients"]["calories"] = "120"

        response = self.client.put(
            f"/api/meals/{created.data['id']}/draft/",
            {
                "entry_date": "2026-08-17",
                "name": "Updated archived apple",
                "notes": "",
                "items": [item],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        saved_item = MealItem.objects.get(meal_entry_id=created.data["id"])
        self.assertEqual(saved_item.calories, Decimal("120"))
        self.assertEqual(saved_item.food_version.provenance, "user_modified_estimate")
        self.assertEqual(saved_item.food_version.derived_from_id, saved_version_id)
