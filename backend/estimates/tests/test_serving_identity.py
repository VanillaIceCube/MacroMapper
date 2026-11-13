"""Synthetic natural-serving definitions; weights are fixtures, not a food database."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from foods.identity import version_definition
from foods.models import FoodItem
from foods.services import create_food_item, create_food_version

from ..models import MealProposal
from ..provider import EstimatedFood, _serialize_food
from ..services import (
    _catalog_food,
    _shared_estimate_items,
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

    def test_follow_up_large_apple_stays_separate_from_existing_small_apples(self):
        self.apple.current_version.refresh_from_db()
        small_apples = _catalog_food(
            self.apple.current_version, servings="2", key="small-apples"
        )
        proposal = MealProposal.objects.create(
            owner=self.user,
            entry_date=date(2026, 11, 11),
            name="Apples",
            description="Two small red apples",
            items=[small_apples],
        )
        original_small = deepcopy(small_apples)
        added_large = _serialize_food(
            EstimatedFood(
                name="Red apple",
                servings=1,
                serving_quantity=1,
                serving_unit="item",
                serving_label="1 large apple",
                serving_weight_grams=225,
                natural_servings=self.sizes,
                confidence_score=0.8,
                nutrients={"calories": 120},
            ),
            key="new-large-apple",
        )
        outcome = apply_proposal_follow_up(
            proposal=proposal,
            owner=self.user,
            follow_up="I also ate one large red apple separately",
            items=deepcopy(proposal.items),
            result={"items_to_add": [added_large]},
        )
        self.assertTrue(outcome["applied"])
        proposal.refresh_from_db()
        self.assertEqual(len(proposal.items), 2)
        self.assertEqual(proposal.items[0], original_small)
        large = proposal.items[1]
        self.assertEqual(large["food_item_id"], self.apple.pk)
        self.assertEqual(large["food_version_id"], self.apple.current_version_id)
        self.assertEqual(large["selected_portion_key"], "size:large")
        self.assertEqual(Decimal(large["servings"]), Decimal("1.5"))
        multiplier = next(
            Decimal(option["serving_multiplier"])
            for option in large["portion_options"]
            if option["key"] == "size:large"
        )
        self.assertEqual(Decimal(large["servings"]) / multiplier, Decimal("1"))
        self.assertEqual(
            Decimal(large["servings"]) * Decimal(large["serving_weight_grams"]),
            Decimal("225"),
        )
        meal = accept_proposal(proposal=proposal)
        self.assertEqual(meal.items.count(), 2)
        self.assertEqual(
            sum(item.calories for item in meal.items.all()), Decimal("280")
        )
        self.assertEqual(meal.items.get(order=0).calories, Decimal("160"))
        self.assertEqual(meal.items.get(order=1).calories, Decimal("120"))
        self.assertEqual(meal.items.get(order=1).selected_portion_key, "size:large")
        self.assertEqual(self.apple.versions.count(), 1)
        self.assertEqual(FoodItem.objects.filter(scope="personal").count(), 0)

    def small_only_catalog_apple(self):
        serialized = _serialize_food(
            EstimatedFood(
                name="Yellow apple",
                serving_unit="item",
                serving_label="1 small apple",
                serving_weight_grams=150,
                confidence_score=0.8,
                nutrients={"calories": 80},
            ),
            key="small-yellow-apple",
        )
        item = _shared_estimate_items(self.size_estimate(serialized))[0]
        food = FoodItem.objects.get(pk=item["food_item_id"])
        return food, item

    def size_estimate(self, item):
        return {
            "name": "Yellow apples",
            "confidence_score": Decimal("0.8"),
            "provider_name": "OpenAI",
            "provider_model": "mock-only",
            "provider_response_id": "mock-size-response",
            "items": [item],
        }

    def large_yellow_apple(self, *, servings=1):
        return _serialize_food(
            EstimatedFood(
                name="Large yellow apple",
                servings=servings,
                serving_unit="item",
                serving_label="1 item",
                serving_weight_grams=225,
                natural_servings=[
                    {"key": "large", "label": "Large", "weight_grams": 225}
                ],
                confidence_score=0.8,
                nutrients={"calories": 120},
            ),
            key="large-yellow-apple",
        )

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
        with patch("estimates.services.get_estimation_provider", return_value=provider):
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

    def weightless_medium_personal_apple(self):
        return create_food_item(
            name="Yellow apple",
            scope="personal",
            origin_type="generic",
            provider_name="",
            owner=self.user,
            created_by=self.user,
            definition={
                "serving_quantity": Decimal("1"),
                "serving_unit": "item",
                "serving_label": "1 medium apple",
                "serving_weight_grams": None,
                "natural_servings": [
                    {"key": "large", "label": "Large", "weight_grams": "225"}
                ],
                "provenance": "user_entered",
                "confidence_score": None,
                "nutrients": {"calories": Decimal("80")},
                "sources": [],
                "components": [],
            },
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
        with patch("estimates.services.get_estimation_provider", return_value=provider):
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
        with patch("estimates.services.get_estimation_provider") as provider:
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
        with patch("estimates.services.get_estimation_provider") as provider:
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
                with patch("estimates.services.get_estimation_provider") as provider:
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
        with patch("estimates.services.get_estimation_provider") as provider:
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

    def test_serialized_size_selection_survives_canonical_name_and_generic_label(self):
        self.apple.current_version.refresh_from_db()
        proposal = MealProposal.objects.create(
            owner=self.user,
            entry_date=date(2026, 11, 11),
            name="Apples",
            description="Two small apples",
            items=[
                _catalog_food(self.apple.current_version, servings="2", key="small")
            ],
        )
        addition = _serialize_food(
            EstimatedFood(
                name="Large red apple",
                serving_unit="item",
                serving_label="1 item",
                serving_weight_grams=225,
                natural_servings=self.sizes,
                servings=1,
                confidence_score=0.8,
                nutrients={"calories": 120},
            ),
            key="serialized-large",
        )
        self.assertEqual(addition["name"].casefold(), "red apple")
        self.assertEqual(addition["serving_label"], "1 item")
        self.assertEqual(addition["selected_portion_key"], "size:large")
        self.assertEqual(
            next(
                Decimal(option["serving_multiplier"])
                for option in addition["portion_options"]
                if option["key"] == "size:large"
            ),
            Decimal("1"),
        )
        outcome = apply_proposal_follow_up(
            proposal=proposal,
            owner=self.user,
            follow_up="I also ate one large apple separately",
            items=deepcopy(proposal.items),
            result={"items_to_add": [addition]},
        )
        self.assertTrue(outcome["applied"])
        proposal.refresh_from_db()
        self.assertEqual(len(proposal.items), 2)
        self.assertEqual(
            [item["food_item_id"] for item in proposal.items],
            [self.apple.pk, self.apple.pk],
        )
        self.assertEqual(
            [item["food_version_id"] for item in proposal.items],
            [self.apple.current_version_id, self.apple.current_version_id],
        )
        self.assertEqual(
            [item["selected_portion_key"] for item in proposal.items],
            ["size:small", "size:large"],
        )
        self.assertEqual(
            [Decimal(item["servings"]) for item in proposal.items],
            [Decimal("2"), Decimal("1.5")],
        )
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
        self.assertEqual(meal.items.get(order=1).selected_portion_key, "size:large")
        self.assertEqual(self.apple.versions.count(), 1)
        self.assertEqual(FoodItem.objects.filter(scope="personal").count(), 0)
