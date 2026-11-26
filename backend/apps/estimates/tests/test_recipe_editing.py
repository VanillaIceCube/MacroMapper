"""Ingredient reparenting, recipe identity and atomic hierarchy edits."""

from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.foods.services import create_food_version

from ..models import MealProposal
from ..services import (
    _catalog_food,
    accept_reviewed_proposal,
    apply_proposal_follow_up,
    normalize_items,
    secure_review_items,
)
from .helpers import shared_food


class RecipeEditingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="recipe-owner", email="recipe-owner@example.com"
        )
        cls.other = get_user_model().objects.create_user(
            username="other-owner", email="other-owner@example.com"
        )
        cls.tilapia = shared_food(name="Tilapia")
        cls.flour = shared_food(name="Flour")
        cls.breading = shared_food(name="Breading")
        cls.eggs = shared_food(name="Egg")
        cls.recipe = shared_food(
            name="Breaded tilapia",
            components=[
                {"food_item": food, "servings": Decimal("1"), "order": order}
                for order, food in enumerate((cls.tilapia, cls.flour, cls.breading))
            ],
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.proposal = MealProposal.objects.create(
            owner=self.owner,
            description="Breaded tilapia made with tilapia, eggs, flour and breading",
            entry_date=date(2026, 11, 11),
            name="Breaded tilapia",
            items=normalize_items(
                [
                    _catalog_food(self.recipe.current_version, key="fish"),
                    _catalog_food(self.eggs.current_version, servings="2", key="eggs"),
                ]
            ),
        )

    def apply(self, result, *, text="Put the two eggs inside the breaded tilapia"):
        self.proposal.refresh_from_db()
        return apply_proposal_follow_up(
            proposal=self.proposal,
            owner=self.owner,
            follow_up=text,
            items=deepcopy(self.proposal.items),
            result=result,
        )

    def test_move_existing_eggs_preserves_identity_quantity_and_saved_hierarchy(self):
        original = deepcopy(self.proposal.items[1])
        result = self.apply({"reparentings": [{"key": "eggs", "parent_key": "fish"}]})
        self.assertTrue(result["applied"])
        self.proposal.refresh_from_db()
        self.assertEqual(len(self.proposal.items), 1)
        fish = self.proposal.items[0]
        egg = next(child for child in fish["components"] if child["key"] == "eggs")
        self.assertEqual(egg["food_item_id"], original["food_item_id"])
        self.assertEqual(egg["food_version_id"], original["food_version_id"])
        self.assertEqual(Decimal(egg["servings"]), Decimal("2"))
        self.assertEqual(egg["nutrients"], original["nutrients"])
        self.assertEqual(Decimal(fish["nutrients"]["calories"]), Decimal("500"))
        self.assertEqual(len(fish["components"]), 4)

        # Review and reload must retain the move rather than enforce the old parent.
        reviewed = secure_review_items(
            proposal=self.proposal,
            owner=self.owner,
            items=deepcopy(self.proposal.items),
        )
        self.assertEqual(len(reviewed[0]["components"]), 4)
        meal = accept_reviewed_proposal(self.owner, self.proposal)
        meal.refresh_from_db()
        self.assertEqual(meal.items.count(), 1)
        saved = meal.items.get()
        self.assertEqual(saved.calories, Decimal("500"))
        response = self.client.get(f"/api/meals/{meal.pk}/")
        self.assertEqual(response.status_code, 200, response.data)
        tree = response.data["items"][0]["component_snapshot"]
        saved_eggs = [child for child in tree if child["food_name"] == "Egg"]
        self.assertEqual(len(saved_eggs), 1)
        self.assertEqual(Decimal(saved_eggs[0]["servings"]), Decimal("2"))
        self.assertEqual(saved_eggs[0]["food_version_id"], original["food_version_id"])
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.current_version.components.count(), 3)

    def test_move_ingredient_back_to_meal_and_adjust_nested_quantity(self):
        self.apply({"reparentings": [{"key": "eggs", "parent_key": "fish"}]})
        self.apply({"serving_updates": [{"key": "eggs", "servings": "3"}]})
        self.proposal.refresh_from_db()
        self.assertEqual(
            Decimal(self.proposal.items[0]["nutrients"]["calories"]), Decimal("600")
        )
        self.apply({"reparentings": [{"key": "eggs", "parent_key": None}]})
        self.proposal.refresh_from_db()
        self.assertEqual(len(self.proposal.items), 2)
        egg = next(item for item in self.proposal.items if item["key"] == "eggs")
        self.assertEqual(Decimal(egg["servings"]), Decimal("3"))
        fish = next(item for item in self.proposal.items if item["key"] == "fish")
        self.assertEqual(Decimal(fish["nutrients"]["calories"]), Decimal("300"))

    def test_cycle_unknown_parent_and_self_move_are_rejected_atomically(self):
        before = deepcopy(self.proposal.items)
        invalid = (
            [{"key": "fish", "parent_key": "fish"}],
            [{"key": "eggs", "parent_key": "missing"}],
            [{"key": "missing", "parent_key": "fish"}],
            [
                {
                    "key": "fish",
                    "parent_key": self.proposal.items[0]["components"][0]["key"],
                }
            ],
        )
        for moves in invalid:
            with self.subTest(moves=moves):
                with self.assertRaises(ValidationError):
                    self.apply({"reparentings": moves})
                self.proposal.refresh_from_db()
                self.assertEqual(self.proposal.items, before)
                self.assertEqual(self.proposal.revisions.count(), 0)

    def test_foreign_proposal_cannot_be_edited(self):
        with self.assertRaises(MealProposal.DoesNotExist):
            apply_proposal_follow_up(
                proposal=self.proposal,
                owner=self.other,
                follow_up="Move eggs",
                items=self.proposal.items,
                result={"reparentings": [{"key": "eggs", "parent_key": "fish"}]},
            )

    def test_move_into_atomic_food_cannot_discard_destination_nutrition(self):
        before = deepcopy(self.proposal.items)
        with self.assertRaises(ValidationError):
            self.apply({"reparentings": [{"key": "fish", "parent_key": "eggs"}]})
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.items, before)

    def test_move_to_parent_already_containing_same_food_version_rejects_duplicate(
        self,
    ):
        self.proposal.items[0]["components"].append(
            _catalog_food(self.eggs.current_version, key="already-inside", servings="1")
        )
        self.proposal.items = normalize_items(self.proposal.items)
        self.proposal.save(update_fields=["items"])
        before = deepcopy(self.proposal.items)
        with self.assertRaises(ValidationError):
            self.apply({"reparentings": [{"key": "eggs", "parent_key": "fish"}]})
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.items, before)

    def test_move_rejects_duplicate_canonical_ingredient_with_different_version(self):
        alternative = create_food_version(
            food_item=self.eggs,
            created_by=None,
            definition={
                "serving_quantity": Decimal("1"),
                "serving_unit": "item",
                "serving_label": "1 egg",
                "provenance": "ai_estimate",
                "confidence_score": Decimal("0.8"),
                "nutrients": {"calories": Decimal("120")},
                "sources": [],
                "components": [],
            },
        )
        self.assertNotEqual(alternative.pk, self.proposal.items[1]["food_version_id"])
        self.proposal.items[0]["components"].append(
            _catalog_food(alternative, key="already-inside", servings="1")
        )
        self.proposal.items = normalize_items(self.proposal.items)
        self.proposal.save(update_fields=["items"])
        before = deepcopy(self.proposal.items)
        with self.assertRaises(ValidationError):
            self.apply({"reparentings": [{"key": "eggs", "parent_key": "fish"}]})
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.items, before)
        self.assertEqual(self.proposal.revisions.count(), 0)

    def test_move_last_child_clears_old_container_values(self):
        fish = self.proposal.items[0]
        fish["components"] = fish["components"][:1]
        self.proposal.items = normalize_items(self.proposal.items)
        self.proposal.save(update_fields=["items"])
        child_key = fish["components"][0]["key"]
        self.apply({"reparentings": [{"key": child_key, "parent_key": None}]})
        self.proposal.refresh_from_db()
        fish = next(item for item in self.proposal.items if item["key"] == "fish")
        self.assertEqual(fish["components"], [])
        self.assertTrue(all(value is None for value in fish["nutrients"].values()))
        total = sum(
            Decimal(item["nutrients"].get("calories") or 0) * Decimal(item["servings"])
            for item in self.proposal.items
        )
        self.assertEqual(total, Decimal("300"))

    def test_reparent_and_fraction_apply_once_and_keep_recipe_quantities(self):
        self.apply(
            {
                "reparentings": [{"key": "eggs", "parent_key": "fish"}],
                "fraction_updates": [
                    {"key": "fish", "fraction": "0.75", "excluded_keys": []}
                ],
            }
        )
        self.proposal.refresh_from_db()
        fish = self.proposal.items[0]
        self.assertEqual(Decimal(fish["servings"]), Decimal("0.75"))
        self.assertEqual(Decimal(fish["nutrients"]["calories"]), Decimal("500"))
        egg = next(child for child in fish["components"] if child["key"] == "eggs")
        self.assertEqual(Decimal(egg["servings"]), Decimal("2"))
        meal = accept_reviewed_proposal(self.owner, self.proposal)
        self.assertEqual(meal.items.get().calories, Decimal("375"))
