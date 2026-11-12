"""Synthetic natural-serving definitions; weights are fixtures, not a food database."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from foods.models import FoodItem
from foods.services import create_food_item

from ..models import MealProposal
from ..provider import EstimatedFood, _serialize_food
from ..services import (
    _catalog_food,
    accept_proposal,
    apply_proposal_follow_up,
    create_proposal,
    secure_review_items,
)


class ServingIdentityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="size-owner")
        cls.sizes = [
            {"key": key, "label": key.title(), "weight_grams": weight}
            for key, weight in (("small", "150"), ("medium", "180"), ("large", "225"))
        ]
        cls.apple = create_food_item(
            name="Red apple",
            scope="shared",
            origin_type="generic",
            provider_name="",
            owner=None,
            created_by=None,
            definition={
                "serving_quantity": Decimal("1"),
                "serving_unit": "item",
                "serving_label": "1 small apple",
                "serving_weight_grams": Decimal("150"),
                "natural_servings": cls.sizes,
                "provenance": "ai_estimate",
                "confidence_score": Decimal("0.8"),
                "nutrients": {"calories": Decimal("80")},
                "sources": [],
                "components": [],
            },
        )

    def test_two_small_apples_resolve_canonical_food_without_provider(self):
        with patch("estimates.services.get_estimation_provider") as provider:
            proposal = create_proposal(
                owner=self.user,
                description="two small red apples",
                entry_date=date(2026, 11, 11),
            )
        provider.assert_not_called()
        item = proposal.items[0]
        self.assertEqual(item["name"], "Red apple")
        self.assertEqual(item["selected_portion_key"], "size:small")
        self.assertEqual(Decimal(item["servings"]), 2)

    def test_natural_size_changes_recalculate_once_and_reload_selected_count(self):
        proposal = MealProposal.objects.create(
            owner=self.user,
            entry_date=date(2026, 11, 11),
            name="Apples",
            description="Two small red apples",
            items=[
                _catalog_food(self.apple.current_version, servings="2", key="apple")
            ],
        )
        for key, multiplier in (("medium", "1.2"), ("large", "1.5")):
            proposal.refresh_from_db()
            result = apply_proposal_follow_up(
                proposal=proposal,
                owner=self.user,
                follow_up=f"Make them {key}",
                items=proposal.items,
                result={
                    "portion_updates": [{"key": "apple", "portion_key": f"size:{key}"}]
                },
            )
            proposal = result["proposal"]
            self.assertEqual(
                Decimal(proposal.items[0]["servings"]),
                Decimal("2") * Decimal(multiplier),
            )
            self.assertEqual(proposal.items[0]["food_item_id"], self.apple.pk)
        reviewed = secure_review_items(
            proposal=proposal, owner=self.user, items=deepcopy(proposal.items)
        )
        self.assertFalse(reviewed[0]["is_user_modified"])
        meal = accept_proposal(proposal=proposal)
        self.assertEqual(meal.items.get().calories, 240)
        self.assertEqual(FoodItem.objects.filter(scope="personal").count(), 0)
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(f"/api/meals/{meal.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["items"][0]["selected_portion_key"], "size:large"
        )
        self.assertEqual(Decimal(response.data["items"][0]["servings"]), 3)

    def test_provider_separates_generic_size_and_preserves_branded_size_name(self):
        generic = EstimatedFood(
            name="Small red apple",
            servings=2,
            serving_unit="item",
            serving_label="1 small apple",
            serving_weight_grams=150,
            natural_servings=self.sizes,
            confidence_score=0.8,
            nutrients={"calories": 80},
        )
        item = _serialize_food(generic, key="apple")
        self.assertEqual(item["name"], "red apple")
        self.assertEqual(item["selected_portion_key"], "size:small")
        branded = generic.model_copy(
            update={
                "name": "Jumbo Apple Snack",
                "provider_name": "Example",
                "origin_type": "branded",
            }
        )
        self.assertEqual(
            _serialize_food(branded, key="sku")["name"], "Jumbo Apple Snack"
        )

    def test_custom_grams_to_natural_size_preserves_weight_and_nutrition(self):
        item = _catalog_food(self.apple.current_version, servings="2", key="apple")
        item["selected_portion_key"] = "g"
        proposal = MealProposal.objects.create(
            owner=self.user, entry_date=date(2026, 11, 11), name="Apples", items=[item]
        )
        result = apply_proposal_follow_up(
            proposal=proposal,
            owner=self.user,
            follow_up="Show large portions",
            items=proposal.items,
            result={"portion_updates": [{"key": "apple", "portion_key": "size:large"}]},
        )
        self.assertEqual(Decimal(result["proposal"].items[0]["servings"]), 2)

    def test_missing_natural_size_metadata_keeps_custom_weight_fallback(self):
        food = EstimatedFood(
            name="Carrot",
            serving_weight_grams=70,
            confidence_score=0.8,
            nutrients={"calories": 30},
        )
        item = _serialize_food(food, key="carrot")
        self.assertIn("g", {option["key"] for option in item["portion_options"]})
        self.assertFalse(
            any(option["key"].startswith("size:") for option in item["portion_options"])
        )
