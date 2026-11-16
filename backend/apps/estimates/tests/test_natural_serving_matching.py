"""Catalog resolution respects natural sizes and compatible serving bases."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase

from apps.foods.identity import version_definition
from apps.foods.models import FoodItem
from apps.foods.services import create_food_version

from ..models import MealProposal
from ..provider import EstimatedFood, _serialize_food
from ..services import (
    _catalog_food,
    accept_proposal,
    apply_proposal_follow_up,
    create_proposal,
    secure_review_items,
)
from .natural_serving_fixtures import NaturalServingFixtures


class NaturalServingMatchingTests(NaturalServingFixtures, TestCase):
    def test_two_small_apples_resolve_canonical_food_without_provider(self):
        with patch("apps.estimates.services.get_estimation_provider") as provider:
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

    def test_initial_large_intent_does_not_reuse_unsupported_small_catalog_serving(
        self,
    ):
        food, original = self.small_only_catalog_apple()
        self.assertEqual(original["natural_servings"], [])
        description = "Two large yellow apples"
        provider = Mock()
        provider.extract_intents.return_value = {
            "name": "Yellow apples",
            "items": [
                {
                    "raw_text": description,
                    "search_name": "Yellow apple",
                    "quantity": 2,
                    "defining_terms": ["large", "yellow"],
                }
            ],
        }
        provider.estimate.return_value = self.size_estimate(
            self.large_yellow_apple(servings=2)
        )
        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            proposal = create_proposal(
                owner=self.user, description=description, entry_date=date(2026, 11, 11)
            )
        provider.extract_intents.assert_called_once_with(description)
        provider.estimate.assert_called_once_with(description)
        item = proposal.items[0]
        self.assertEqual(item["food_item_id"], food.pk)
        self.assertNotEqual(item["food_version_id"], original["food_version_id"])
        self.assertEqual(Decimal(item["serving_weight_grams"]), Decimal("225"))
        self.assertEqual(Decimal(item["servings"]), Decimal("2"))
        self.assertEqual(item["selected_portion_key"], "size:large")
        self.assertEqual(food.versions.count(), 2)
        meal = accept_proposal(proposal=proposal)
        self.assertEqual(meal.items.get().calories, Decimal("240"))
        self.assertEqual(
            meal.items.get().servings
            * meal.items.get().food_version.serving_weight_grams,
            Decimal("450"),
        )

    def test_natural_size_without_base_weight_does_not_resolve_large_intent(self):
        personal = self.weightless_medium_personal_apple()
        original_version_id = personal.current_version_id
        catalog = _catalog_food(personal.current_version)
        self.assertNotIn(
            "size:large", {option["key"] for option in catalog["portion_options"]}
        )
        description = "Two large yellow apples"
        provider = Mock()
        provider.extract_intents.return_value = {
            "name": "Yellow apples",
            "items": [
                {
                    "raw_text": description,
                    "search_name": "Yellow apple",
                    "quantity": 2,
                    "defining_terms": ["large", "yellow"],
                }
            ],
        }
        provider.estimate.return_value = self.size_estimate(
            self.large_yellow_apple(servings=2)
        )
        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            proposal = create_proposal(
                owner=self.user, description=description, entry_date=date(2026, 11, 11)
            )
        provider.extract_intents.assert_called_once_with(description)
        provider.estimate.assert_called_once_with(description)
        item = proposal.items[0]
        self.assertNotEqual(item["food_item_id"], personal.pk)
        self.assertEqual(item["selected_portion_key"], "size:large")
        self.assertEqual(Decimal(item["serving_weight_grams"]), Decimal("225"))
        self.assertEqual(Decimal(item["servings"]), Decimal("2"))
        meal = accept_proposal(proposal=proposal)
        self.assertEqual(meal.items.get().calories, Decimal("240"))
        personal.refresh_from_db()
        self.assertEqual(personal.current_version_id, original_version_id)
        self.assertIsNone(personal.current_version.serving_weight_grams)
        self.assertEqual(personal.current_version.calories, Decimal("80"))
        self.assertEqual(personal.versions.count(), 1)

    def test_declared_medium_base_remains_usable_without_base_weight(self):
        personal = self.weightless_medium_personal_apple()
        with patch("apps.estimates.services.get_estimation_provider") as provider:
            proposal = create_proposal(
                owner=self.user,
                description="Two medium yellow apples",
                entry_date=date(2026, 11, 11),
            )
        provider.assert_not_called()
        item = proposal.items[0]
        self.assertEqual(item["food_item_id"], personal.pk)
        self.assertEqual(item["food_version_id"], personal.current_version_id)
        self.assertEqual(item["selected_portion_key"], "base")
        self.assertEqual(Decimal(item["servings"]), Decimal("2"))
        self.assertIsNone(item["serving_weight_grams"])
        meal = accept_proposal(proposal=proposal)
        self.assertEqual(meal.items.get().calories, Decimal("160"))
        self.assertEqual(meal.items.get().food_version_id, personal.current_version_id)

    def test_unsupported_serialized_size_publishes_new_version_instead_of_small_addon(
        self,
    ):
        food, original = self.small_only_catalog_apple()
        original["servings"] = "2"
        proposal = MealProposal.objects.create(
            owner=self.user,
            entry_date=date(2026, 11, 11),
            name="Yellow apples",
            items=[original],
        )
        addition = self.large_yellow_apple()
        self.assertNotIn(
            "large", f"{addition['name']} {addition['serving_label']}".casefold()
        )
        self.assertEqual(addition["selected_portion_key"], "size:large")
        outcome = apply_proposal_follow_up(
            proposal=proposal,
            owner=self.user,
            follow_up="I also ate one large yellow apple separately",
            items=deepcopy(proposal.items),
            result={**self.size_estimate(addition), "items_to_add": [addition]},
        )
        self.assertTrue(outcome["applied"])
        proposal.refresh_from_db()
        self.assertEqual(len(proposal.items), 2)
        self.assertEqual(
            [item["food_item_id"] for item in proposal.items], [food.pk, food.pk]
        )
        self.assertNotEqual(
            proposal.items[1]["food_version_id"], original["food_version_id"]
        )
        self.assertEqual(
            Decimal(proposal.items[0]["serving_weight_grams"]), Decimal("150")
        )
        self.assertEqual(Decimal(proposal.items[0]["servings"]), Decimal("2"))
        self.assertEqual(
            Decimal(proposal.items[1]["serving_weight_grams"]), Decimal("225")
        )
        self.assertEqual(Decimal(proposal.items[1]["servings"]), Decimal("1"))
        self.assertEqual(proposal.items[1]["selected_portion_key"], "size:large")
        self.assertEqual(food.versions.count(), 2)
        meal = accept_proposal(proposal=proposal)
        self.assertEqual(
            sum(item.calories for item in meal.items.all()), Decimal("280")
        )
        self.assertEqual(
            sum(
                item.servings * item.food_version.serving_weight_grams
                for item in meal.items.all()
            ),
            Decimal("525"),
        )
        self.assertEqual(FoodItem.objects.filter(scope="personal").count(), 0)

    def test_custom_weight_fallback_remains_valid_without_natural_catalog_sizes(self):
        food, original = self.small_only_catalog_apple()
        with patch("apps.estimates.services.get_estimation_provider") as provider:
            proposal = create_proposal(
                owner=self.user,
                description="Yellow apple",
                entry_date=date(2026, 11, 11),
            )
        provider.assert_not_called()
        item = deepcopy(proposal.items[0])
        self.assertIn("g", {option["key"] for option in item["portion_options"]})
        item.update(selected_portion_key="g", servings="1.5")
        proposal.items = secure_review_items(
            proposal=proposal, owner=self.user, items=[item]
        )
        proposal.save(update_fields=["items"])
        meal = accept_proposal(proposal=proposal)
        saved = meal.items.get()
        self.assertEqual(saved.food_version_id, original["food_version_id"])
        self.assertEqual(saved.selected_portion_key, "g")
        self.assertEqual(
            saved.servings * saved.food_version.serving_weight_grams, Decimal("225")
        )
        self.assertEqual(saved.calories, Decimal("120"))
        self.assertEqual(food.versions.count(), 1)

    def test_declared_small_base_reuses_catalog_without_natural_choices(self):
        food, original = self.small_only_catalog_apple()
        for size_word in ("small", "smallish"):
            with self.subTest(size_word=size_word):
                with patch(
                    "apps.estimates.services.get_estimation_provider"
                ) as provider:
                    proposal = create_proposal(
                        owner=self.user,
                        description=f"Two {size_word} yellow apples",
                        entry_date=date(2026, 11, 11),
                    )
                provider.assert_not_called()
                item = proposal.items[0]
                self.assertEqual(item["food_item_id"], food.pk)
                self.assertEqual(item["food_version_id"], original["food_version_id"])
                self.assertEqual(Decimal(item["servings"]), Decimal("2"))
                self.assertEqual(item["selected_portion_key"], "base")
                self.assertEqual(Decimal(item["serving_weight_grams"]), Decimal("150"))

    def test_size_constraint_is_not_borrowed_from_another_food_in_same_clause(self):
        food, original = self.small_only_catalog_apple()
        with patch("apps.estimates.services.get_estimation_provider") as provider:
            proposal = create_proposal(
                owner=self.user,
                description="Two large red apples and yellow apple",
                entry_date=date(2026, 11, 11),
            )
        provider.assert_not_called()
        self.assertEqual(len(proposal.items), 2)
        red, yellow = proposal.items
        self.assertEqual(red["food_item_id"], self.apple.pk)
        self.assertEqual(red["selected_portion_key"], "size:large")
        self.assertEqual(Decimal(red["servings"]), Decimal("3"))
        self.assertEqual(yellow["food_item_id"], food.pk)
        self.assertEqual(yellow["food_version_id"], original["food_version_id"])
        self.assertEqual(Decimal(yellow["servings"]), Decimal("1"))
        self.assertEqual(Decimal(yellow["serving_weight_grams"]), Decimal("150"))

    def test_unlabeled_countable_weight_does_not_reuse_different_catalog_base(self):
        food, original = self.small_only_catalog_apple()
        original["servings"] = "2"
        proposal = MealProposal.objects.create(
            owner=self.user,
            entry_date=date(2026, 11, 11),
            name="Yellow apples",
            items=[original],
        )
        addition = _serialize_food(
            EstimatedFood(
                name="Yellow apple",
                serving_unit="item",
                serving_label="1 item",
                serving_weight_grams=225,
                confidence_score=0.8,
                nutrients={"calories": 120},
            ),
            key="weight-only-apple",
        )
        self.assertEqual(addition["selected_portion_key"], "base")
        outcome = apply_proposal_follow_up(
            proposal=proposal,
            owner=self.user,
            follow_up="I also ate one yellow apple weighing 225 grams",
            items=deepcopy(proposal.items),
            result={**self.size_estimate(addition), "items_to_add": [addition]},
        )
        self.assertTrue(outcome["applied"])
        proposal.refresh_from_db()
        self.assertEqual(len(proposal.items), 2)
        added = proposal.items[1]
        self.assertEqual(added["food_item_id"], food.pk)
        self.assertNotEqual(added["food_version_id"], original["food_version_id"])
        self.assertEqual(Decimal(added["serving_weight_grams"]), Decimal("225"))
        self.assertEqual(Decimal(added["servings"]), Decimal("1"))
        meal = accept_proposal(proposal=proposal)
        self.assertEqual(
            sum(item.calories for item in meal.items.all()), Decimal("280")
        )
        self.assertEqual(
            sum(
                item.servings * item.food_version.serving_weight_grams
                for item in meal.items.all()
            ),
            Decimal("525"),
        )

    def test_added_size_does_not_merge_different_version_serving_bases(self):
        small_definition = version_definition(self.apple.current_version)
        large_definition = deepcopy(small_definition)
        large_definition.update(
            serving_label="1 large apple",
            serving_weight_grams=Decimal("225"),
            nutrients={"calories": Decimal("120")},
        )
        historical_large = create_food_version(
            food_item=self.apple, definition=large_definition, created_by=None
        )
        historical_large.refresh_from_db()
        historical_item = _catalog_food(
            historical_large, servings="2", key="historical-large"
        )
        current_small = create_food_version(
            food_item=self.apple, definition=small_definition, created_by=None
        )
        self.assertNotEqual(historical_large.pk, current_small.pk)
        proposal = MealProposal.objects.create(
            owner=self.user,
            entry_date=date(2026, 11, 11),
            name="Apples",
            description="Two large apples from a previously reviewed version",
            items=[historical_item],
        )
        added_large = _serialize_food(
            EstimatedFood(
                name="Red apple",
                servings=1,
                serving_unit="item",
                serving_label="1 large apple",
                serving_weight_grams=225,
                natural_servings=self.sizes,
                confidence_score=0.8,
                nutrients={"calories": 120},
            ),
            key="new-large-apple",
        )
        for expected_current_servings in ("1.5", "3"):
            proposal.refresh_from_db()
            outcome = apply_proposal_follow_up(
                proposal=proposal,
                owner=self.user,
                follow_up="I also ate one more large apple separately",
                items=deepcopy(proposal.items),
                result={"items_to_add": [deepcopy(added_large)]},
            )
            self.assertTrue(outcome["applied"])
            proposal.refresh_from_db()
            self.assertEqual(len(proposal.items), 2)
            self.assertEqual(proposal.items[0], historical_item)
            added = proposal.items[1]
            self.assertEqual(added["food_item_id"], self.apple.pk)
            self.assertEqual(added["food_version_id"], current_small.pk)
            self.assertEqual(added["selected_portion_key"], "size:large")
            self.assertEqual(
                Decimal(added["servings"]), Decimal(expected_current_servings)
            )
        meal = accept_proposal(proposal=proposal)
        self.assertEqual(meal.items.count(), 2)
        self.assertEqual(meal.items.get(order=0).food_version_id, historical_large.pk)
        self.assertEqual(meal.items.get(order=1).food_version_id, current_small.pk)
        self.assertEqual(meal.items.get(order=0).calories, Decimal("240"))
        self.assertEqual(meal.items.get(order=1).calories, Decimal("240"))
        self.assertEqual(self.apple.versions.count(), 3)
        self.assertEqual(FoodItem.objects.filter(scope="personal").count(), 0)
