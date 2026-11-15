"""Manual and AI-assisted meal builder adjustments."""

from copy import deepcopy
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase

from ..models import MealProposal, MealProposalRevision
from .helpers import ProposalFixtures, shared_food, simple_ai_estimate


class BuilderAdjustmentTests(ProposalFixtures, TestCase):
    def test_builder_adjustment_can_create_a_meal_from_no_foods(self):
        addition = simple_ai_estimate(name="Apple", calories="95")["items"][0]
        provider = Mock()
        provider.follow_up.return_value = {
            "name": "Apple Snack",
            "message": "Added an apple.",
            "confidence_score": Decimal("0.9"),
            "remove_keys": [],
            "serving_updates": [],
            "items_to_add": [addition],
            "provider_name": "OpenAI",
            "provider_model": "gpt-test",
            "provider_response_id": "resp_empty_builder_adjustment",
        }

        with patch(
            "apps.estimates.views.get_estimation_provider", return_value=provider
        ):
            response = self.client.post(
                "/api/meal-proposals/adjustments/",
                {
                    "adjustment": "Add an apple",
                    "entry_date": "2026-08-16",
                    "name": "",
                    "notes": "",
                    "items": [],
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["applied"])
        self.assertEqual(response.data["proposal"]["name"], "Apple Snack")
        self.assertEqual(response.data["proposal"]["items"][0]["name"], "Apple")
        self.assertEqual(
            response.data["proposal"]["revisions"][0]["kind"],
            MealProposalRevision.Kind.AI_FOLLOW_UP,
        )
        provider.follow_up.assert_called_once_with(
            original_description="",
            meal_name="Meal",
            items=[],
            follow_up="Add an apple",
        )

        accepted = self.client.post(
            f"/api/meal-proposals/{response.data['proposal']['id']}/accept/"
        )

        self.assertEqual(accepted.status_code, 201, accepted.data)
        self.assertEqual(accepted.data["name"], "Apple Snack")
        self.assertIn("AI adjustments:\n- Add an apple", accepted.data["notes"])
        self.assertNotIn("Estimated from:", accepted.data["notes"])

    def test_builder_adjustment_preserves_catalog_foods_and_applies_quantity_changes(
        self,
    ):
        apple = shared_food(name="Apple")
        proposal_response = self.client.post(
            "/api/meal-proposals/",
            {"description": "Apple", "entry_date": "2026-08-16"},
            format="json",
        )
        item = proposal_response.data["items"][0]
        provider = Mock()
        provider.follow_up.return_value = {
            "name": "Two Apples",
            "message": "Changed the apple quantity to two.",
            "confidence_score": Decimal("0.95"),
            "remove_keys": [],
            "serving_updates": [{"key": item["key"], "servings": 2}],
            "items_to_add": [],
            "provider_name": "OpenAI",
            "provider_model": "gpt-test",
            "provider_response_id": "resp_builder_quantity_adjustment",
        }

        with patch(
            "apps.estimates.views.get_estimation_provider", return_value=provider
        ):
            response = self.client.post(
                "/api/meal-proposals/adjustments/",
                {
                    "adjustment": "Make that two apples",
                    "entry_date": "2026-08-16",
                    "name": "Apple",
                    "notes": "",
                    "items": [item],
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200, response.data)
        adjusted_item = response.data["proposal"]["items"][0]
        self.assertEqual(adjusted_item["food_item_id"], apple.pk)
        self.assertEqual(Decimal(adjusted_item["servings"]), Decimal("2"))
        self.assertEqual(response.data["proposal"]["name"], "Two Apples")

    def test_builder_adjustment_accepts_removed_catalog_components(self):
        tortilla = shared_food(name="Flour tortilla")
        filling = shared_food(name="Egg and potato filling")
        burrito = shared_food(
            name="Breakfast burrito",
            components=[
                {"food_item": tortilla, "servings": Decimal("1"), "order": 0},
                {"food_item": filling, "servings": Decimal("1"), "order": 1},
            ],
        )
        proposal_response = self.client.post(
            "/api/meal-proposals/",
            {"description": "Breakfast burrito", "entry_date": "2026-08-16"},
            format="json",
        )
        item = deepcopy(proposal_response.data["items"][0])
        item["components"] = [item["components"][1]]
        provider = Mock()
        provider.follow_up.return_value = {
            "name": "Double filling bowl",
            "message": "Removed the tortilla and doubled the remaining filling.",
            "confidence_score": Decimal("0.9"),
            "remove_keys": [],
            "serving_updates": [{"key": item["key"], "servings": 2}],
            "items_to_add": [],
            "provider_name": "OpenAI",
            "provider_model": "gpt-test",
            "provider_response_id": "resp_removed_component",
        }

        with patch(
            "apps.estimates.views.get_estimation_provider", return_value=provider
        ):
            response = self.client.post(
                "/api/meal-proposals/adjustments/",
                {
                    "adjustment": "Remove the tortilla and make it two servings",
                    "entry_date": "2026-08-16",
                    "name": "Breakfast burrito",
                    "notes": "",
                    "items": [item],
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200, response.data)
        adjusted_item = response.data["proposal"]["items"][0]
        self.assertEqual(adjusted_item["food_item_id"], burrito.pk)
        self.assertEqual(
            [component["food_item_id"] for component in adjusted_item["components"]],
            [filling.pk],
        )
        self.assertEqual(adjusted_item["source_kind"], "user_modified_estimate")

    def test_builder_adjustment_cleans_up_proposal_on_unexpected_exception(self):
        shared_food(name="Apple")
        proposal_response = self.client.post(
            "/api/meal-proposals/",
            {"description": "Apple", "entry_date": "2026-08-16"},
            format="json",
        )
        item = proposal_response.data["items"][0]
        initial_count = MealProposal.objects.count()
        provider = Mock()
        provider.follow_up.side_effect = RuntimeError("Unexpected provider error")

        with patch(
            "apps.estimates.views.get_estimation_provider", return_value=provider
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    "/api/meal-proposals/adjustments/",
                    {
                        "adjustment": "Make that two apples",
                        "entry_date": "2026-08-16",
                        "name": "Apple",
                        "notes": "",
                        "items": [item],
                    },
                    format="json",
                )

        self.assertEqual(MealProposal.objects.count(), initial_count)
