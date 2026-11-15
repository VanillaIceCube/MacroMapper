"""Bounded component graph queries and resilient saved snapshots."""

from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.estimates.services import _catalog_food, _matches_catalog_tree
from apps.foods.models import FoodComponent, FoodItem, FoodItemVersion
from apps.foods.services import (
    build_component_map,
    create_food_item,
)

from ..models import MealEntry
from ..serializers import MealItemSerializer, _is_valid_component_snapshot
from ..services import _component_tree, _effective_nutrients, replace_meal_items
from .helpers import User, definition


class ComponentGraphTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="graph-owner")
        cls.root = cls.make_graph(width=3, prefix="saved")
        cls.meal = MealEntry.objects.create(
            owner=cls.owner, entry_date=date(2026, 10, 10), name="Nested meal"
        )
        replace_meal_items(
            meal_entry=cls.meal,
            item_inputs=[{"food_item": cls.root, "servings": Decimal("1"), "order": 0}],
        )
        cls.saved_item = cls.meal.items.select_related("food_version").get()

    @classmethod
    def make_food(cls, name, components):
        return create_food_item(
            name=name,
            scope=FoodItem.Scope.SHARED,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=None,
            definition={
                **definition(components=components),
                "provenance": FoodItemVersion.Provenance.OFFICIAL,
                "confidence_score": Decimal("0.990"),
                "sources": [
                    {
                        "title": name,
                        "provider": "Example",
                        "url": "https://example.com",
                        "accessed_on": date(2026, 10, 10),
                    }
                ],
            },
            created_by=cls.owner,
        )

    @classmethod
    def make_graph(cls, *, width, prefix):
        branches = []
        for index in range(width):
            child = cls.make_food(f"{prefix} leaf {index}", [])
            for level in range(3):
                child = cls.make_food(
                    f"{prefix} branch {index} level {level}",
                    [{"food_item": child, "servings": Decimal("2"), "order": 0}],
                )
            branches.append(
                {"food_item": child, "servings": Decimal("2"), "order": index}
            )
        return cls.make_food(f"{prefix} root", branches)

    def test_deep_catalog_query_budget_is_independent_of_branch_count(self):
        for width in (1, 4):
            with self.subTest(width=width):
                food = self.make_graph(width=width, prefix=f"catalog-{width}")
                version = (
                    FoodItemVersion.objects.select_related("food_item")
                    .prefetch_related("sources")
                    .get(pk=food.current_version_id)
                )
                # Four nonempty component levels (components + sources), then leaves.
                with self.assertNumQueries(9):
                    item = _catalog_food(version)
                self.assertEqual(item["nutrients"]["calories"], str(1600 * width))
                self.assertEqual(len(item["components"]), width)
                for branch in item["components"]:
                    for _ in range(3):
                        branch = branch["components"][0]
                    self.assertEqual(branch["nutrients"]["calories"], "100")
                    self.assertEqual(branch["sources"][0]["accessed_on"], "2026-10-10")
                    self.assertEqual(branch["components"], [])

    def test_snapshot_and_nutrients_reuse_the_loaded_graph_without_queries(self):
        version = self.root.current_version
        with self.assertNumQueries(9):
            component_map = build_component_map([version.pk])
        nutrient_cache = {}
        with self.assertNumQueries(0):
            totals = _effective_nutrients(
                version,
                component_map=component_map,
                nutrient_cache=nutrient_cache,
            )
            cached_count = len(nutrient_cache)
            snapshot = _component_tree(
                version,
                component_map=component_map,
                nutrient_cache=nutrient_cache,
            )
        self.assertEqual(len(nutrient_cache), cached_count)
        self.assertEqual(totals["calories"], Decimal("4800"))
        self.assertEqual(len(snapshot), 3)
        self.assertEqual(snapshot[0]["nutrients"][0]["amount"], "800.0000")

    def test_meal_creation_batches_component_loading_across_items(self):
        other_root = self.make_graph(width=4, prefix="other")
        with CaptureQueriesContext(connection) as queries:
            replace_meal_items(
                meal_entry=self.meal,
                item_inputs=[
                    {"food_item": self.root, "servings": Decimal("2"), "order": 0},
                    {"food_item": other_root, "servings": Decimal("1"), "order": 1},
                ],
            )
        graph_queries = [
            query
            for query in queries
            if 'FROM "foods_foodcomponent"' in query["sql"]
            or 'FROM "foods_sourcereference"' in query["sql"]
        ]
        self.assertEqual(len(graph_queries), 9)
        first, second = self.meal.items.order_by("order")
        self.assertEqual(first.calories, Decimal("9600"))
        self.assertEqual(second.calories, Decimal("6400"))
        self.assertEqual(len(first.component_snapshot), 3)
        self.assertEqual(len(second.component_snapshot), 4)

    def test_catalog_matching_reuses_the_complete_graph(self):
        version = (
            FoodItemVersion.objects.select_related("food_item")
            .prefetch_related("sources")
            .get(pk=self.root.current_version_id)
        )
        component_map = build_component_map([version.pk])
        with self.assertNumQueries(0):
            item = _catalog_food(version, component_map=component_map)
            self.assertTrue(
                _matches_catalog_tree(item, version, component_map=component_map)
            )
        item["components"][0]["components"][0]["nutrients"]["calories"] = "1"
        with self.assertNumQueries(0):
            self.assertFalse(
                _matches_catalog_tree(item, version, component_map=component_map)
            )

    def test_complete_snapshot_is_reused_without_queries(self):
        self.assertTrue(
            _is_valid_component_snapshot(self.saved_item.component_snapshot)
        )
        with self.assertNumQueries(0):
            result = MealItemSerializer().get_component_snapshot(self.saved_item)
        self.assertIs(result, self.saved_item.component_snapshot)

    def test_each_missing_component_field_rebuilds_the_snapshot(self):
        original = deepcopy(self.saved_item.component_snapshot)
        for nested in (False, True):
            for field in set(original[0]) - {"evidence"}:
                with self.subTest(field=field, nested=nested):
                    incomplete = deepcopy(original)
                    component = (
                        incomplete[0]["components"][0] if nested else incomplete[0]
                    )
                    component.pop(field)
                    self.saved_item.component_snapshot = incomplete
                    result = MealItemSerializer().get_component_snapshot(
                        self.saved_item
                    )
                    self.assertEqual(result, original)

    def test_malformed_snapshot_values_rebuild_the_snapshot(self):
        original = deepcopy(self.saved_item.component_snapshot)
        invalid_values = {
            "food_item_id": True,
            "food_version_id": "1",
            "food_name": None,
            "provider_name": [],
            "origin_type": "unknown",
            "servings": "NaN",
            "serving_quantity": 1,
            "serving_unit": {},
            "serving_label": 123,
            "serving_weight_grams": "-1",
            "serving_volume_ml": "Infinity",
            "confidence_score": "1.1",
            "provenance": "unknown",
            "portion_options": [{"key": "base"}],
            "nutrients": [
                {"key": "calories", "name": "Calories", "unit": "kcal", "amount": {}}
            ],
            "sources": [
                {
                    "title": "Source",
                    "provider": "",
                    "url": "https://example.com",
                    "accessed_on": [],
                    "is_official": False,
                }
            ],
            "components": {},
        }
        for field, value in invalid_values.items():
            with self.subTest(field=field):
                malformed = deepcopy(original)
                malformed[0][field] = value
                self.saved_item.component_snapshot = malformed
                self.assertFalse(_is_valid_component_snapshot(malformed))
                result = MealItemSerializer().get_component_snapshot(self.saved_item)
                self.assertEqual(result, original)

    def test_corrupt_cycle_terminates_without_hiding_sibling_branches(self):
        branch = self.root.current_version.components.first().child_version
        FoodComponent.objects.create(
            parent_version=branch,
            child_version=self.root.current_version,
            servings=Decimal("1"),
            order=1,
        )
        component_map = build_component_map([self.root.current_version_id])
        with self.assertNumQueries(
            1
        ):  # Root sources; all descendant sources are loaded.
            item = _catalog_food(self.root.current_version, component_map=component_map)
        self.assertEqual(len(item["components"]), 3)
        self.assertEqual(len(item["components"][0]["components"]), 1)
        self.assertEqual(item["nutrients"]["calories"], "4800")
