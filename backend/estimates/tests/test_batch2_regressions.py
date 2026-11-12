"""Independent, synthetic regressions for recipe hierarchy and consumed portions."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from foods.models import FoodItem
from foods.services import create_food_version

from ..models import MealProposal
from ..provider import EstimatedFood, EstimatedMeal, OpenAIMealEstimationProvider
from ..serializers import ProposalItemsField
from ..services import (
    _catalog_food,
    accept_proposal,
    apply_proposal_follow_up,
    create_proposal,
    normalize_items,
    secure_review_items,
)
from .helpers import shared_food


class RecipeEditRegressionTests(TestCase):
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
        meal = accept_proposal(proposal=self.proposal)
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
        meal = accept_proposal(proposal=self.proposal)
        self.assertEqual(meal.items.get().calories, Decimal("375"))


class ConsumedRecipeFractionRegressionTests(TestCase):
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


class InitialRecipeInterpretationRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="initial-owner")

    def food(self, name, *, servings=1, components=None, recipe_fraction=None):
        values = {
            "name": name,
            "servings": servings,
            "serving_quantity": 1,
            "serving_unit": "item",
            "serving_label": "one item",
            "serving_weight_grams": 100,
            "confidence_score": 0.8,
            "nutrients": {"calories": 100},
            "components": components or [],
        }
        if recipe_fraction is not None:
            values["recipe_fraction"] = recipe_fraction
        return EstimatedFood(**values)

    def provider(self, foods):
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            id="resp_synthetic_recipe",
            output_parsed=EstimatedMeal(
                name="Recipe", confidence_score=0.8, items=foods
            ),
        )
        return OpenAIMealEstimationProvider(client=client)

    def test_initial_recipe_fraction_and_full_addons_round_trip_to_saved_totals(self):
        for fraction, wording in (
            (0.75, "75% of that"),
            (0.5, "half the recipe"),
            (0.25, "one of four servings"),
        ):
            with self.subTest(wording=wording):
                provider = self.provider(
                    [
                        self.food(
                            "Chilaquiles rojos",
                            components=[
                                self.food("Tomato", servings=3),
                                self.food("Tortilla chips"),
                            ],
                            recipe_fraction=fraction,
                        ),
                        self.food("Chicken breast", servings=2),
                        self.food("Greek yogurt"),
                    ]
                )
                estimate = provider.estimate(
                    f"Chilaquiles, I ate {wording}, plus two chicken breasts and Greek yogurt"
                )
                self.assertEqual(
                    Decimal(estimate["items"][0]["servings"]), Decimal(str(fraction))
                )
                self.assertEqual(
                    Decimal(estimate["items"][0]["components"][0]["servings"]),
                    Decimal("3"),
                )
                with (
                    patch(
                        "estimates.services.resolve_catalog_matches",
                        return_value={
                            "matches": [],
                            "unmatched_description": "Recipe",
                            "unmatched_descriptions": ["Recipe"],
                        },
                    ),
                    patch("estimates.services.get_estimation_provider") as configured,
                ):
                    configured.return_value.extract_intents.return_value = None
                    configured.return_value.estimate.return_value = estimate
                    proposal = create_proposal(
                        owner=self.owner,
                        description=f"I ate {wording} plus chicken and yogurt",
                        entry_date=date(2026, 11, 11),
                    )
                meal = accept_proposal(proposal=proposal)
                self.assertEqual(
                    sum(item.calories for item in meal.items.all()),
                    Decimal("400") * Decimal(str(fraction)) + Decimal("300"),
                )
                self.assertEqual(
                    FoodItem.objects.filter(scope="personal", owner=self.owner).count(),
                    0,
                )

    def test_initial_breaded_fish_retains_all_four_ingredients_as_children(self):
        estimate = self.provider(
            [
                self.food(
                    "Breaded tilapia",
                    components=[
                        self.food("Tilapia"),
                        self.food("Egg", servings=2),
                        self.food("Flour"),
                        self.food("Breading"),
                    ],
                )
            ]
        ).estimate(
            "I had breaded tilapia made with tilapia, two eggs, flour and breading"
        )
        self.assertEqual(len(estimate["items"]), 1)
        components = estimate["items"][0]["components"]
        self.assertEqual(
            [child["name"] for child in components],
            ["Tilapia", "Egg", "Flour", "Breading"],
        )
        self.assertEqual(Decimal(components[1]["servings"]), Decimal("2"))

    def test_recipe_interpretation_retains_full_context_despite_ingredient_catalog_hits(
        self,
    ):
        shared_food(name="Egg")
        shared_food(name="Flour")
        description = "I had breaded tilapia. It was made with tilapia, two eggs, flour and breading."
        estimate = self.provider(
            [
                self.food(
                    "Breaded tilapia",
                    components=[
                        self.food("Tilapia"),
                        self.food("Egg", servings=2),
                        self.food("Flour"),
                        self.food("Breading"),
                    ],
                )
            ]
        ).estimate(description)
        configured = Mock()
        configured.estimate.return_value = estimate
        with patch(
            "estimates.services.get_estimation_provider", return_value=configured
        ):
            proposal = create_proposal(
                owner=self.owner, description=description, entry_date=date(2026, 11, 11)
            )
        configured.extract_intents.assert_not_called()
        configured.estimate.assert_called_once_with(description)
        self.assertEqual(len(proposal.items), 1)
        self.assertEqual(
            [child["name"] for child in proposal.items[0]["components"]],
            ["Tilapia", "Egg", "Flour", "Breading"],
        )
        self.assertEqual(
            Decimal(proposal.items[0]["components"][1]["servings"]), Decimal("2")
        )

    def test_maximum_natural_sizes_and_measurements_survive_review_validation(self):
        values = self.food("Fruit smoothie").model_dump()
        values.update(
            serving_volume_ml=240,
            natural_servings=[
                {
                    "key": f"size_{index}",
                    "label": f"Portion {index}",
                    "weight_grams": 50 + index * 10,
                }
                for index in range(12)
            ],
        )
        estimate = self.provider([EstimatedFood(**values)]).estimate("Fruit smoothie")
        configured = Mock()
        configured.extract_intents.return_value = None
        configured.estimate.return_value = estimate
        with patch(
            "estimates.services.get_estimation_provider", return_value=configured
        ):
            proposal = create_proposal(
                owner=self.owner,
                description="Fruit smoothie",
                entry_date=date(2026, 11, 11),
            )
        self.assertEqual(len(proposal.items[0]["portion_options"]), 20)
        reviewed = ProposalItemsField().run_validation(proposal.items)
        self.assertEqual(len(reviewed[0]["portion_options"]), 20)

    def test_same_food_in_different_sizes_keeps_distinct_valid_meal_instances(self):
        apple = shared_food(name="Red apple")
        create_food_version(
            food_item=apple,
            created_by=None,
            definition={
                "serving_quantity": Decimal("1"),
                "serving_unit": "item",
                "serving_label": "1 small apple",
                "serving_weight_grams": Decimal("150"),
                "natural_servings": [
                    {"key": "small", "label": "Small", "weight_grams": "150"},
                    {"key": "large", "label": "Large", "weight_grams": "225"},
                ],
                "provenance": "ai_estimate",
                "confidence_score": Decimal("0.9"),
                "nutrients": {"calories": Decimal("100")},
                "sources": [],
                "components": [],
            },
        )
        with patch("estimates.services.get_estimation_provider") as configured:
            proposal = create_proposal(
                owner=self.owner,
                description="one small red apple + one large red apple",
                entry_date=date(2026, 11, 11),
            )
        configured.assert_not_called()
        self.assertEqual(len(proposal.items), 2)
        self.assertEqual(len({item["key"] for item in proposal.items}), 2)
        self.assertEqual(
            [item["food_item_id"] for item in proposal.items], [apple.pk, apple.pk]
        )
        self.assertEqual(
            [item["selected_portion_key"] for item in proposal.items],
            ["size:small", "size:large"],
        )
        self.assertEqual(
            [Decimal(item["servings"]) for item in proposal.items],
            [Decimal("1"), Decimal("1.5")],
        )
        ProposalItemsField().run_validation(proposal.items)
        meal = accept_proposal(proposal=proposal)
        self.assertEqual(
            sum(item.calories for item in meal.items.all()), Decimal("250")
        )
