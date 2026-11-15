"""Consumed recipe fractions and separate ingredient quantities."""

from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.foods.models import FoodItem, FoodItemVersion

from ..models import MealProposal
from ..services import (
    _catalog_food,
    accept_proposal,
    apply_proposal_follow_up,
    normalize_items,
)
from .helpers import shared_food


class ConsumedRecipeFractionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="fraction-owner")
        cls.tomatoes = shared_food(name="Tomato")
        cls.chips = shared_food(name="Tortilla chips")
        cls.cheese = shared_food(name="Cotija cheese")
        cls.recipe = shared_food(
            name="Chilaquiles rojos",
            components=[
                {"food_item": cls.tomatoes, "servings": Decimal("3"), "order": 0},
                {"food_item": cls.chips, "servings": Decimal("1"), "order": 1},
                {"food_item": cls.cheese, "servings": Decimal("1"), "order": 2},
            ],
        )
        cls.chicken = shared_food(name="Chicken breast")
        cls.yogurt = shared_food(name="Greek yogurt", provider_name="Kirkland")

    def setUp(self):
        self.proposal = MealProposal.objects.create(
            owner=self.owner,
            description="Chilaquiles. I had 75% of that, plus chicken and yogurt.",
            entry_date=date(2026, 11, 11),
            name="Chilaquiles with chicken and yogurt",
            items=normalize_items(
                [
                    _catalog_food(self.recipe.current_version, key="recipe"),
                    _catalog_food(
                        self.chicken.current_version, servings="2", key="chicken"
                    ),
                    _catalog_food(self.yogurt.current_version, key="yogurt"),
                ]
            ),
        )

    def apply_fraction(self, fraction):
        self.proposal.refresh_from_db()
        return apply_proposal_follow_up(
            proposal=self.proposal,
            owner=self.owner,
            follow_up="Only the recipe fraction; keep chicken and yogurt at full portions",
            items=deepcopy(self.proposal.items),
            result={
                "fraction_updates": [
                    {
                        "key": "recipe",
                        "fraction": fraction,
                        "excluded_keys": ["chicken", "yogurt"],
                    }
                ]
            },
        )

    def test_absolute_fraction_does_not_scale_separate_addons_or_recipe_children(self):
        original_children = deepcopy(self.proposal.items[0]["components"])
        for fraction in ("0.75", "0.5", "0.25", "0.75"):
            with self.subTest(fraction=fraction):
                outcome = self.apply_fraction(fraction)
                self.assertTrue(outcome["applied"])
                self.proposal.refresh_from_db()
                recipe, chicken, yogurt = self.proposal.items
                self.assertEqual(Decimal(recipe["servings"]), Decimal(fraction))
                self.assertEqual(recipe["components"], original_children)
                self.assertEqual(
                    Decimal(recipe["nutrients"]["calories"]), Decimal("500")
                )
                self.assertEqual(Decimal(chicken["servings"]), Decimal("2"))
                self.assertEqual(Decimal(yogurt["servings"]), Decimal("1"))
        meal = accept_proposal(proposal=self.proposal)
        self.assertEqual(
            sum(item.calories for item in meal.items.all()), Decimal("675")
        )
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.current_version.components.count(), 3)

    def test_invalid_fraction_is_rejected_without_revisions_or_data_changes(self):
        before = deepcopy(self.proposal.items)
        for fraction in ("0", "-0.2", "NaN", "Infinity", "not-a-fraction"):
            with self.subTest(fraction=fraction):
                with self.assertRaises(ValidationError):
                    self.apply_fraction(fraction)
                self.proposal.refresh_from_db()
                self.assertEqual(self.proposal.items, before)
                self.assertEqual(self.proposal.revisions.count(), 0)

    def test_separate_addon_does_not_merge_into_partially_consumed_recipe_ingredient(
        self,
    ):
        recipe = shared_food(
            name="Chilaquiles with yogurt",
            components=[
                {"food_item": self.tomatoes, "servings": Decimal("3"), "order": 0},
                {"food_item": self.chips, "servings": Decimal("1"), "order": 1},
                {"food_item": self.yogurt, "servings": Decimal("1"), "order": 2},
            ],
        )
        self.proposal.items = normalize_items(
            [
                _catalog_food(recipe.current_version, servings="0.75", key="recipe"),
                _catalog_food(
                    self.chicken.current_version, servings="2", key="chicken"
                ),
            ]
        )
        self.proposal.save(update_fields=["items"])
        original_children = deepcopy(self.proposal.items[0]["components"])
        catalog_before = list(FoodItem.objects.order_by("pk").values())
        versions_before = list(FoodItemVersion.objects.order_by("pk").values())

        # This is a separately eaten side, even though the same food occurs in the recipe.
        for servings, expected_addon in (("2", "2"), ("1", "3")):
            self.proposal.refresh_from_db()
            addition = _catalog_food(self.yogurt.current_version, servings=servings)
            addition.update(food_item_id=None, food_version_id=None)
            outcome = apply_proposal_follow_up(
                proposal=self.proposal,
                owner=self.owner,
                follow_up=f"I also had {servings} full yogurt servings separately on the side",
                items=deepcopy(self.proposal.items),
                result={"items_to_add": [addition]},
            )
            self.assertTrue(outcome["applied"])
            self.proposal.refresh_from_db()
            self.assertEqual(len(self.proposal.items), 3)
            recipe_item, chicken, addon = self.proposal.items
            self.assertEqual(recipe_item["components"], original_children)
            self.assertEqual(Decimal(recipe_item["servings"]), Decimal("0.75"))
            self.assertEqual(
                Decimal(recipe_item["nutrients"]["calories"]), Decimal("500")
            )
            self.assertEqual(Decimal(chicken["servings"]), Decimal("2"))
            self.assertEqual(addon["food_item_id"], self.yogurt.pk)
            self.assertEqual(addon["food_version_id"], self.yogurt.current_version_id)
            self.assertEqual(Decimal(addon["servings"]), Decimal(expected_addon))
            self.assertEqual(
                list(FoodItem.objects.order_by("pk").values()), catalog_before
            )
            self.assertEqual(
                list(FoodItemVersion.objects.order_by("pk").values()), versions_before
            )

        meal = accept_proposal(proposal=self.proposal)
        self.assertEqual(meal.items.count(), 3)
        self.assertEqual(
            sum(item.calories for item in meal.items.all()), Decimal("875")
        )
        saved_recipe = meal.items.get(order=0)
        self.assertEqual(saved_recipe.calories, Decimal("375"))
        saved_yogurt = next(
            child
            for child in saved_recipe.component_snapshot
            if child["food_item_id"] == self.yogurt.pk
        )
        self.assertEqual(Decimal(saved_yogurt["servings"]), Decimal("1"))
        self.assertEqual(meal.items.get(order=2).calories, Decimal("300"))
        self.assertEqual(list(FoodItem.objects.order_by("pk").values()), catalog_before)
        self.assertEqual(
            list(FoodItemVersion.objects.order_by("pk").values()), versions_before
        )

    def test_explicit_exclusions_guard_conflicting_provider_quantity_and_portion_edits(
        self,
    ):
        chicken = self.proposal.items[1]
        chicken["portion_options"].append(
            {
                "key": "size:large",
                "label": "Large",
                "unit_label": "Large",
                "serving_multiplier": "2",
            }
        )
        self.proposal.save(update_fields=["items"])
        result = apply_proposal_follow_up(
            proposal=self.proposal,
            owner=self.owner,
            follow_up="75% of the recipe except chicken and yogurt",
            items=deepcopy(self.proposal.items),
            result={
                "fraction_updates": [
                    {
                        "key": "recipe",
                        "fraction": "0.75",
                        "excluded_keys": ["chicken", "yogurt"],
                    }
                ],
                "serving_updates": [
                    {"key": "chicken", "servings": "1.5"},
                    {"key": "yogurt", "servings": "0.75"},
                ],
                "portion_updates": [{"key": "chicken", "portion_key": "size:large"}],
            },
        )
        self.assertTrue(result["applied"])
        self.proposal.refresh_from_db()
        recipe, chicken, yogurt = self.proposal.items
        self.assertEqual(Decimal(recipe["servings"]), Decimal("0.75"))
        self.assertEqual(Decimal(chicken["servings"]), Decimal("2"))
        self.assertEqual(chicken["selected_portion_key"], "base")
        self.assertEqual(Decimal(yogurt["servings"]), Decimal("1"))

    def test_conflicting_fraction_and_quantity_for_same_recipe_are_rejected(self):
        before = deepcopy(self.proposal.items)
        with self.assertRaises(ValidationError):
            apply_proposal_follow_up(
                proposal=self.proposal,
                owner=self.owner,
                follow_up="75% of the recipe",
                items=deepcopy(self.proposal.items),
                result={
                    "fraction_updates": [
                        {"key": "recipe", "fraction": "0.75", "excluded_keys": []}
                    ],
                    "serving_updates": [{"key": "recipe", "servings": "0.5"}],
                },
            )
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.items, before)
