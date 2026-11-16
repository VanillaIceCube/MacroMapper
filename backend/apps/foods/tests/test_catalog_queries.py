"""Catalog visibility, search ranking, pagination and component query budgets."""

from datetime import date
from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from apps.meals.models import MealEntry, MealItem

from ..models import (
    FoodItem,
    FoodItemVersion,
)
from ..services import (
    create_food_item,
)
from .helpers import FoodApiFixtures, food_definition


class CatalogQueryTests(FoodApiFixtures, APITestCase):
    def test_food_endpoint_requires_authentication(self):
        food_response = self.client.get("/api/foods/")

        self.assertEqual(food_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_catalog_lists_shared_and_owned_foods_only(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get("/api/foods/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            {item["id"] for item in response.data},
            {self.shared_food.id, self.personal_food.id},
        )
        shared = next(
            item for item in response.data if item["id"] == self.shared_food.id
        )
        self.assertEqual(shared["current_version"]["portion_options"][0]["key"], "base")

    def test_catalog_search_matches_name_and_provider(self):
        self.client.force_authenticate(user=self.owner)

        name_response = self.client.get("/api/foods/?search=apple")
        provider_response = self.client.get("/api/foods/?search=Orchard")

        self.assertEqual(
            [item["id"] for item in name_response.data],
            [self.shared_food.id],
        )
        self.assertEqual(
            [item["id"] for item in provider_response.data],
            [self.shared_food.id],
        )

    def test_catalog_relevance_prefers_exact_then_prefix_name_matches(self):
        self.client.force_authenticate(user=self.owner)
        exact_food = create_food_item(
            name="Apple",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.owner,
            definition=food_definition(calories="95", confidence=None),
            created_by=self.owner,
        )
        prefix_food = create_food_item(
            name="Apple slices",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.owner,
            definition=food_definition(calories="80", confidence=None),
            created_by=self.owner,
        )

        response = self.client.get(
            "/api/foods/?search=apple&ordering=relevance,name,id"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data[:2]],
            [exact_food.id, prefix_food.id],
        )

    def test_catalog_recently_logged_sort_is_user_specific(self):
        owner_shared_meal = MealEntry.objects.create(
            owner=self.owner,
            entry_date=date(2026, 8, 10),
            name="Shared apple meal",
        )
        owner_personal_meal = MealEntry.objects.create(
            owner=self.owner,
            entry_date=date(2026, 8, 12),
            name="Owner smoothie meal",
        )
        other_shared_meal = MealEntry.objects.create(
            owner=self.other_user,
            entry_date=date(2026, 8, 20),
            name="Other user's shared apple meal",
        )
        for meal, food in (
            (owner_shared_meal, self.shared_food),
            (owner_personal_meal, self.personal_food),
            (other_shared_meal, self.shared_food),
        ):
            version = food.current_version
            MealItem.objects.create(
                meal_entry=meal,
                food_version=version,
                servings=Decimal("1"),
                food_name=food.name,
                provider_name=food.provider_name,
                serving_quantity=version.serving_quantity,
                serving_unit=version.serving_unit,
                serving_label=version.serving_label,
            )
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            "/api/foods/?ordering=-has_logged,-last_logged_on,name,id"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data],
            [self.personal_food.id, self.shared_food.id],
        )

    def test_catalog_filters_combine_with_search(self):
        self.client.force_authenticate(user=self.owner)

        shared_response = self.client.get(
            "/api/foods/?search=apple&scope=shared&origin_type=branded"
            "&provider=orchard&provenance=official"
        )
        personal_response = self.client.get(
            "/api/foods/?scope=personal&provenance=user_entered"
        )
        excluded_response = self.client.get("/api/foods/?search=apple&scope=personal")

        self.assertEqual(
            [item["id"] for item in shared_response.data], [self.shared_food.id]
        )
        self.assertEqual(
            [item["id"] for item in personal_response.data], [self.personal_food.id]
        )
        self.assertEqual(excluded_response.data, [])

    def test_catalog_search_matches_source_metadata(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get("/api/foods/?search=Official%20apple%20data")

        self.assertEqual([item["id"] for item in response.data], [self.shared_food.id])

    def test_catalog_rejects_invalid_filter_values(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get("/api/foods/?scope=everyone")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("scope", response.data)

    def test_catalog_limit_applies_after_recent_ordering(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get("/api/foods/?ordering=-created_at&limit=1")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data], [self.personal_food.id]
        )

    def test_catalog_offset_returns_the_next_ordered_page(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get("/api/foods/?ordering=name,id&limit=1&offset=1")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [self.shared_food.id])

    def test_catalog_list_uses_bulk_loaded_top_level_components(self):
        create_food_item(
            name="Apple plate",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.owner,
            definition=food_definition(
                calories="305",
                confidence=None,
                components=[
                    {
                        "food_item": self.shared_food,
                        "servings": Decimal("1"),
                        "order": 0,
                    },
                    {
                        "food_item": self.personal_food,
                        "servings": Decimal("1"),
                        "order": 1,
                    },
                ],
            ),
            created_by=self.owner,
        )
        self.client.force_authenticate(user=self.owner)

        with CaptureQueriesContext(connection) as captured:
            response = self.client.get("/api/foods/")

        component_queries = [
            query
            for query in captured.captured_queries
            if "foods_foodcomponent" in query["sql"].lower()
        ]
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            len(component_queries),
            1,
            [query["sql"] for query in component_queries],
        )
        plate = next(item for item in response.data if item["name"] == "Apple plate")
        self.assertEqual(
            plate["current_version"]["components"][0]["food_item_name"],
            "Shared apple",
        )

    def test_catalog_retrieve_uses_bulk_loaded_components(self):
        plate = create_food_item(
            name="Apple plate detail",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.owner,
            definition=food_definition(
                calories="305",
                confidence=None,
                components=[
                    {
                        "food_item": self.shared_food,
                        "servings": Decimal("1"),
                        "order": 0,
                    },
                    {
                        "food_item": self.personal_food,
                        "servings": Decimal("1"),
                        "order": 1,
                    },
                ],
            ),
            created_by=self.owner,
        )
        self.client.force_authenticate(user=self.owner)

        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(f"/api/foods/{plate.id}/")

        component_queries = [
            query
            for query in captured.captured_queries
            if "foods_foodcomponent" in query["sql"].lower()
        ]
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertLessEqual(
            len(component_queries),
            2,
            [query["sql"] for query in component_queries],
        )
        component_names = {
            item["food_item_name"]
            for item in response.data["current_version"]["components"]
        }
        self.assertEqual(component_names, {"Shared apple", "Owner smoothie"})

    def test_catalog_create_uses_bulk_loaded_components(self):
        self.client.force_authenticate(user=self.owner)
        payload = self.personal_food_payload(
            name="Apple toast combo",
            definition={
                "serving_quantity": "1",
                "serving_unit": FoodItemVersion.ServingUnit.ITEM,
                "serving_label": "one combo",
                "provenance": FoodItemVersion.Provenance.USER_ENTERED,
                "confidence_score": None,
                "nutrients": {"calories": "300"},
                "sources": [],
                "components": [
                    {"food_item": self.shared_food.id, "servings": "1", "order": 0},
                    {"food_item": self.personal_food.id, "servings": "1", "order": 1},
                ],
            },
        )

        with CaptureQueriesContext(connection) as captured:
            response = self.client.post("/api/foods/", payload, format="json")

        read_component_queries = [
            query
            for query in captured.captured_queries
            if 'WHERE "foods_foodcomponent"."parent_version_id" IN' in query["sql"]
        ]
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertLessEqual(
            len(read_component_queries),
            2,
            [query["sql"] for query in read_component_queries],
        )
        component_names = {
            item["food_item_name"]
            for item in response.data["current_version"]["components"]
        }
        self.assertEqual(component_names, {"Shared apple", "Owner smoothie"})

    def test_shared_detail_retains_provenance_confidence_and_sources(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(f"/api/foods/{self.shared_food.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        definition = response.data["current_version"]
        self.assertEqual(definition["provenance"], FoodItemVersion.Provenance.OFFICIAL)
        self.assertEqual(definition["confidence_score"], "0.990")
        self.assertEqual(
            definition["sources"][0]["url"],
            "https://example.com/apple",
        )
