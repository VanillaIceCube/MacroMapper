"""Initial recipe interpretation, ingredient context and natural serving sizes."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.foods.models import FoodItem
from apps.foods.services import create_food_version

from ..provider import (
    EstimatedFood,
    EstimatedMeal,
    OpenAIMealEstimationProvider,
)
from ..serializers import ProposalItemsField
from ..services import (
    accept_proposal,
    create_proposal,
)
from .helpers import shared_food


class InitialRecipeInterpretationTests(TestCase):
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
                        "apps.estimates.services.resolve_catalog_matches",
                        return_value={
                            "matches": [],
                            "unmatched_description": "Recipe",
                            "unmatched_descriptions": ["Recipe"],
                        },
                    ),
                    patch(
                        "apps.estimates.services.get_estimation_provider"
                    ) as configured,
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
            "apps.estimates.services.get_estimation_provider", return_value=configured
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
            "apps.estimates.services.get_estimation_provider", return_value=configured
        ):
            proposal = create_proposal(
                owner=self.owner,
                description="Fruit smoothie",
                entry_date=date(2026, 11, 11),
            )
        self.assertEqual(len(proposal.items[0]["portion_options"]), 20)
        reviewed = ProposalItemsField().run_validation(proposal.items)
        self.assertEqual(len(reviewed[0]["portion_options"]), 20)

    def sized_apple(self):
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
        return apple

    def test_same_food_in_different_sizes_keeps_distinct_valid_meal_instances(self):
        apple = self.sized_apple()
        with patch("apps.estimates.services.get_estimation_provider") as configured:
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

    def test_extracted_intents_combine_equivalent_sizes_without_losing_other_sizes(
        self,
    ):
        apple = self.sized_apple()
        configured = Mock()
        configured.extract_intents.return_value = {
            "name": "Mixed-size apples",
            "items": [
                {
                    "raw_text": text,
                    "search_name": "Red apple",
                    "quantity": quantity,
                    "defining_terms": ["red"],
                }
                for text, quantity in (
                    ("one small red apple", 1),
                    ("two large red apples", 2),
                    ("one smallish red apple", 1),
                )
            ],
        }
        description = "Some orchard fruit in different portions"
        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=configured
        ):
            proposal = create_proposal(
                owner=self.owner,
                description=description,
                entry_date=date(2026, 11, 11),
            )
        configured.extract_intents.assert_called_once_with(description)
        configured.estimate.assert_not_called()
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
            [Decimal("2"), Decimal("3")],
        )
        ProposalItemsField().run_validation(proposal.items)
        meal = accept_proposal(proposal=proposal)
        self.assertEqual(
            sum(item.calories for item in meal.items.all()), Decimal("500")
        )
