"""Catalog resolution, partial matches and provider fallback."""

from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase

from apps.foods.models import FoodItem, FoodItemVersion
from apps.foods.services import create_food_item

from ..models import MealProposal
from .helpers import ProposalFixtures, shared_food, simple_ai_estimate


class CatalogMatchingTests(ProposalFixtures, TestCase):
    def test_catalog_match_bypasses_provider_and_retains_official_source(self):
        patty = shared_food(name="Beef patty")
        shared_food(
            name="Double-Double",
            provider_name="In-N-Out",
            origin_type=FoodItem.OriginType.RESTAURANT,
            components=[{"food_item": patty, "servings": Decimal("2"), "order": 0}],
        )

        with patch("apps.estimates.services.get_estimation_provider") as provider:
            response = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "Double-Double from In-N-Out",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        provider.assert_not_called()
        self.assertEqual(response.data["generator"], MealProposal.Generator.CATALOG)
        self.assertEqual(response.data["items"][0]["source_kind"], "official_verified")
        self.assertEqual(
            response.data["items"][0]["components"][0]["name"], "Beef patty"
        )
        self.assertEqual(
            response.data["items"][0]["sources"][0]["url"],
            "https://example.com/double-double",
        )

    def test_personal_catalog_match_retains_user_entered_source(self):
        personal = create_food_item(
            name="My overnight oats",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.user,
            definition={
                "serving_quantity": Decimal("1"),
                "serving_unit": FoodItemVersion.ServingUnit.SERVING,
                "serving_label": "one bowl",
                "provenance": FoodItemVersion.Provenance.USER_ENTERED,
                "confidence_score": None,
                "nutrients": {"calories": Decimal("320")},
                "sources": [],
                "components": [],
            },
            created_by=self.user,
        )

        with patch("apps.estimates.services.get_estimation_provider") as provider:
            response = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "My overnight oats",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201, response.data)
        provider.assert_not_called()
        self.assertEqual(response.data["items"][0]["food_item_id"], personal.pk)
        self.assertEqual(response.data["items"][0]["source_kind"], "user_entered")

    def test_catalog_resolver_combines_typoed_composite_and_joined_food_with_quantity(
        self,
    ):
        for name in ("Bacon", "Egg", "Cheese", "Biscuit"):
            shared_food(name=name, provider_name="McDonald's")
        biscuit = shared_food(
            name="Bacon, Egg & Cheese Biscuit",
            provider_name="McDonald's",
            origin_type=FoodItem.OriginType.RESTAURANT,
        )
        preferred_hash_browns = shared_food(
            name="Hash Browns",
            provider_name="McDonald's",
            origin_type=FoodItem.OriginType.RESTAURANT,
            provenance=FoodItemVersion.Provenance.AI_ESTIMATE,
            confidence="0.970",
        )
        shared_food(
            name="Hash Browns",
            provider_name="McDonald's",
            origin_type=FoodItem.OriginType.RESTAURANT,
            provenance=FoodItemVersion.Provenance.AI_ESTIMATE,
            confidence="0.930",
        )

        with patch("apps.estimates.services.get_estimation_provider") as provider:
            response = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": (
                        "McDonalds Bacon Egg & Cheese Busicut and 2 hashbrowns"
                    ),
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        provider.assert_not_called()
        self.assertEqual(response.data["generator"], MealProposal.Generator.CATALOG)
        self.assertEqual(len(response.data["items"]), 2)
        self.assertEqual(
            [item["food_item_id"] for item in response.data["items"]],
            [biscuit.pk, preferred_hash_browns.pk],
        )
        self.assertEqual(
            [Decimal(item["servings"]) for item in response.data["items"]],
            [Decimal("1"), Decimal("2")],
        )
        self.assertNotIn(
            "Bacon",
            [item["name"] for item in response.data["items"]],
        )

    def test_catalog_resolver_applies_quantity_before_the_provider_name(self):
        biscuit = shared_food(
            name="Bacon, Egg & Cheese Biscuit",
            provider_name="McDonald's",
            origin_type=FoodItem.OriginType.RESTAURANT,
        )

        with patch("apps.estimates.services.get_estimation_provider") as provider:
            response = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "3 McDonalds Bacon Egg Cheese Busicuits",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        provider.assert_not_called()
        self.assertEqual(response.data["items"][0]["food_item_id"], biscuit.pk)
        self.assertEqual(Decimal(response.data["items"][0]["servings"]), Decimal("3"))

    def test_catalog_resolver_handles_heavily_typoed_provider_and_food(self):
        hash_browns = shared_food(
            name="Hash Browns",
            provider_name="McDonald's",
            origin_type=FoodItem.OriginType.RESTAURANT,
        )

        with patch("apps.estimates.services.get_estimation_provider") as provider:
            response = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "mcdonlds oar hsh brown",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        provider.assert_not_called()
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["food_item_id"], hash_browns.pk)
        self.assertEqual(Decimal(response.data["items"][0]["servings"]), Decimal("1"))

    def test_ai_intents_resolve_same_food_from_two_providers(self):
        kfc_fries = shared_food(
            name="KFC Crinkle Cut Fries",
            provider_name="KFC",
            origin_type=FoodItem.OriginType.RESTAURANT,
        )
        mcdonalds_fries = shared_food(
            name="World Famous Fries",
            provider_name="McDonald's",
            origin_type=FoodItem.OriginType.RESTAURANT,
        )
        provider = Mock()
        provider.extract_intents.return_value = {
            "name": "KFC & McDonald's Fries",
            "items": [
                {
                    "raw_text": "fries from KFC",
                    "search_name": "fries",
                    "provider_name": "KFC",
                    "quantity": 1,
                    "defining_terms": ["fries"],
                    "aliases": ["Crinkle Cut Fries"],
                },
                {
                    "raw_text": "fries from McDonald's",
                    "search_name": "fries",
                    "provider_name": "McDonald's",
                    "quantity": 1,
                    "defining_terms": ["fries"],
                    "aliases": ["World Famous Fries"],
                },
            ],
        }

        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            response = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "I had fries from kfc and fries from mcdonalds",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        provider.extract_intents.assert_called_once_with(
            "I had fries from kfc and fries from mcdonalds"
        )
        provider.estimate.assert_not_called()
        self.assertEqual(response.data["generator"], MealProposal.Generator.CATALOG)
        self.assertEqual(response.data["name"], "KFC & McDonald's Fries")
        self.assertEqual(
            [item["food_item_id"] for item in response.data["items"]],
            [kfc_fries.pk, mcdonalds_fries.pk],
        )

    def test_ai_intents_estimate_only_the_provider_food_missing_from_catalog(self):
        kfc_fries = shared_food(
            name="KFC Crinkle Cut Fries",
            provider_name="KFC",
            origin_type=FoodItem.OriginType.RESTAURANT,
        )
        provider = Mock()
        provider.extract_intents.return_value = {
            "name": "KFC & McDonald's Fries",
            "items": [
                {
                    "raw_text": "fries from KFC",
                    "search_name": "fries",
                    "provider_name": "KFC",
                    "quantity": 1,
                    "defining_terms": ["fries"],
                    "aliases": ["Crinkle Cut Fries"],
                },
                {
                    "raw_text": "fries from McDonald's",
                    "search_name": "fries",
                    "provider_name": "McDonald's",
                    "quantity": 1,
                    "defining_terms": ["fries"],
                    "aliases": ["World Famous Fries"],
                },
            ],
        }
        provider.estimate.return_value = simple_ai_estimate(
            name="World Famous Fries",
            calories="230",
        )
        provider.estimate.return_value["items"][0].update(
            {
                "provider_name": "McDonald's",
                "origin_type": FoodItem.OriginType.RESTAURANT,
            }
        )

        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            response = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "I had fries from kfc and fries from mcdonalds",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "KFC & McDonald's Fries")
        provider.estimate.assert_called_once_with("fries from McDonald's")
        self.assertEqual(
            [item["food_item_id"] for item in response.data["items"][:1]],
            [kfc_fries.pk],
        )
        self.assertEqual(response.data["items"][1]["name"], "World Famous Fries")
        self.assertEqual(response.data["items"][1]["source_kind"], "ai_estimate")

    def test_mixed_catalog_and_ai_items_keep_same_name_from_different_providers(self):
        kfc_fries = shared_food(
            name="Fries",
            provider_name="KFC",
            origin_type=FoodItem.OriginType.RESTAURANT,
        )
        provider = Mock()
        provider.extract_intents.return_value = {
            "items": [
                {
                    "raw_text": "fries from KFC",
                    "search_name": "fries",
                    "provider_name": "KFC",
                    "quantity": 1,
                    "defining_terms": ["fries"],
                    "aliases": [],
                },
                {
                    "raw_text": "fries from McDonald's",
                    "search_name": "fries",
                    "provider_name": "McDonald's",
                    "quantity": 1,
                    "defining_terms": ["fries"],
                    "aliases": [],
                },
            ]
        }
        provider.estimate.return_value = simple_ai_estimate(
            name="Fries",
            calories="230",
        )
        provider.estimate.return_value["items"][0].update(
            {
                "provider_name": "McDonald's",
                "origin_type": FoodItem.OriginType.RESTAURANT,
            }
        )

        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            response = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "fries from KFC and fries from McDonald's",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.data["items"]), 2)
        self.assertEqual(response.data["items"][0]["food_item_id"], kfc_fries.pk)
        self.assertEqual(
            [item["provider_name"] for item in response.data["items"]],
            ["KFC", "McDonald's"],
        )
        self.assertEqual(
            response.data["items"][1]["nutrients"]["calories"],
            "230",
        )

    def test_ai_intent_does_not_match_fries_to_fried_chicken(self):
        fried_chicken = shared_food(
            name="KFC Fried Chicken Piece",
            provider_name="KFC",
            origin_type=FoodItem.OriginType.RESTAURANT,
        )
        provider = Mock()
        provider.extract_intents.return_value = {
            "items": [
                {
                    "raw_text": "fries from KFC",
                    "search_name": "fries",
                    "provider_name": "KFC",
                    "quantity": 1,
                    "defining_terms": ["fries"],
                    "aliases": [],
                }
            ]
        }
        provider.estimate.return_value = simple_ai_estimate(
            name="KFC Secret Recipe Fries",
            calories="320",
        )
        provider.estimate.return_value["items"][0].update(
            {
                "provider_name": "KFC",
                "origin_type": FoodItem.OriginType.RESTAURANT,
            }
        )

        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            response = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "fries from KFC",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        provider.estimate.assert_called_once_with("fries from KFC")
        self.assertNotEqual(response.data["items"][0]["food_item_id"], fried_chicken.pk)
        self.assertEqual(response.data["items"][0]["name"], "KFC Secret Recipe Fries")

    def test_catalog_resolver_uses_ai_only_for_unmatched_foods(self):
        biscuit = shared_food(
            name="Bacon, Egg & Cheese Biscuit",
            provider_name="McDonald's",
            origin_type=FoodItem.OriginType.RESTAURANT,
        )
        provider = Mock()
        provider.estimate.return_value = simple_ai_estimate(
            name="Black coffee", calories="5"
        )

        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            response = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "McDonalds Bacon Egg Cheese Biscuit and coffee",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        provider.estimate.assert_called_once_with("coffee McDonald's")
        self.assertEqual(response.data["generator"], MealProposal.Generator.OPENAI)
        self.assertEqual(
            [item["name"] for item in response.data["items"]],
            [biscuit.name, "Black coffee"],
        )
        self.assertEqual(response.data["items"][0]["food_item_id"], biscuit.pk)
        self.assertEqual(response.data["items"][1]["source_kind"], "ai_estimate")

    def test_partial_catalog_match_sends_complete_food_clause_to_ai(self):
        shared_food(
            name="Bacon, Egg & Cheese Biscuit",
            provider_name="McDonald's",
            origin_type=FoodItem.OriginType.RESTAURANT,
        )
        hash_browns = shared_food(
            name="Hash Browns",
            provider_name="McDonald's",
            origin_type=FoodItem.OriginType.RESTAURANT,
        )
        estimate = simple_ai_estimate(
            name="Bacon, Egg & Cheese McGriddles",
            calories="430",
        )
        estimate["items"][0].update(
            {
                "provider_name": "McDonald's",
                "origin_type": FoodItem.OriginType.RESTAURANT,
                "serving_label": "1 sandwich",
            }
        )
        provider = Mock()
        provider.estimate.return_value = estimate

        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            response = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": (
                        "Bacon Egg and Cheese McGriddle + 3 hashbrowns mcdonalds"
                    ),
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        provider.estimate.assert_called_once_with(
            "Bacon Egg and Cheese McGriddle McDonald's"
        )
        items_by_name = {item["name"]: item for item in response.data["items"]}
        self.assertEqual(
            set(items_by_name),
            {"Bacon, Egg & Cheese McGriddles", "Hash Browns"},
        )
        self.assertEqual(
            items_by_name["Hash Browns"]["food_item_id"],
            hash_browns.pk,
        )
        self.assertEqual(
            Decimal(items_by_name["Hash Browns"]["servings"]),
            Decimal("3"),
        )
        self.assertEqual(
            items_by_name["Bacon, Egg & Cheese McGriddles"]["nutrients"]["calories"],
            "430",
        )
        self.assertNotIn(
            "Bacon, Egg & Cheese Biscuit",
            items_by_name,
        )
        self.assertNotIn("Sausage McGriddles", items_by_name)
