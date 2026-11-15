"""Bounded JSON output and complete cursor/offset recovery of diary records."""

import json
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.http import Http404
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.meals.models import MealEntry, MealItem
from apps.meals.serializers import MealEntrySerializer
from apps.meals.services import replace_meal_items

from .. import services
from .helpers import MealToolFixtures


@skipUnless(settings.MCP_ENABLED, "Run the enabled app-owned OAuth profile")
class MCPResponseLimitTests(MealToolFixtures, TestCase):
    def test_diary_node_budget_pages_and_meal_item_pages_recover_every_id(self):
        food = self.composite()
        meals = []
        for _ in range(3):
            payload = self.meal_payload()
            payload["item_inputs"] = [
                {"food_item": food.pk, "servings": "1", "order": index}
                for index in range(3)
            ]
            meals.append(
                self.confirm(self.preview(payload=payload))["result"]["data"]["id"]
            )
        page = services.list_records(self.raw, "meals", {"date": "2026-10-30"}, 20, 0)
        self.assertTrue(page["has_more"])
        self.assertLess(len(page["data"]), 3)
        found, offset = [], 0
        while True:
            page = services.list_records(
                self.raw, "meals", {"date": "2026-10-30"}, 20, offset
            )
            services.json_value(page, maximum=65536)
            found.extend(record["id"] for record in page["data"])
            if not page["has_more"]:
                break
            self.assertGreater(page["next_offset"], offset)
            offset = page["next_offset"]
        self.assertEqual(found, meals)
        meal = MealEntry.objects.get(pk=meals[0])
        replace_meal_items(
            meal_entry=meal,
            item_inputs=[
                {"food_item": food, "servings": 1, "order": index}
                for index in range(25)
            ],
        )
        listing = services.list_records(self.raw, "meals", {"date": "2026-10-30"}, 1, 0)
        self.assertTrue(listing["truncated"])
        self.assertNotIn("items", listing["data"][0])
        self.assertEqual(listing["data"][0]["item_count"], 25)
        item_ids, offset = [], 0
        while True:
            page = services.get_meal(self.raw, meal.pk, 20, offset)
            services.json_value(page, maximum=65536)
            self.assertFalse(page["truncated"])
            self.assertEqual(page["data"]["item_count"], 25)
            item_ids.extend(item["id"] for item in page["data"]["items"])
            if not page["has_more"]:
                break
            self.assertGreater(page["next_offset"], offset)
            offset = page["next_offset"]
        self.assertEqual(item_ids, list(meal.items.values_list("id", flat=True)))
        with self.assertRaises(Http404):
            foreign = MealEntry.objects.create(
                owner=self.other, entry_date=meal.entry_date, name="Private"
            )
            services.get_meal(self.raw, foreign.pk)
        self.assertEqual(
            services.list_records(self.raw, "meals", {"date": "2026-10-30"}, 1, 999)[
                "data"
            ],
            [],
        )

    def test_single_oversized_or_trimmed_item_returns_only_honest_summary(self):
        meal = self.make_meal()
        original = services.MealItemSerializer.to_representation
        for expansion in (
            ["é" * 1900] * 10,
            list(range(21)),
            ["x" * 2001],
            [[list(range(10)) for _ in range(20)] for _ in range(20)],
        ):
            with self.subTest(size=len(expansion)):
                with patch.object(
                    services.MealItemSerializer,
                    "to_representation",
                    lambda serializer, item: (
                        original(serializer, item) | {"synthetic_expansion": expansion}
                    ),
                ):
                    page = services.get_meal(self.raw, meal.pk)
                self.assertTrue(page["truncated"])
                self.assertNotIn("items", page["data"])
                self.assertIn("MacroMapper", page["data"]["detail"])
                self.assertIsNone(page["next_offset"])
                services.json_value(page, maximum=65536)

    def test_diary_byte_budget_reduces_page_without_omitting_records(self):
        ids = [self.make_meal().pk for _ in range(3)]
        original = MealEntrySerializer.to_representation

        def expanded(serializer, instance):
            return original(serializer, instance) | {
                "synthetic_expansion": ["é" * 1900] * 4
            }

        with patch.object(MealEntrySerializer, "to_representation", expanded):
            page = services.list_records(
                self.raw, "meals", {"date": "2026-10-30"}, 20, 0
            )
            self.assertFalse(page["truncated"])
            self.assertTrue(page["has_more"])
            self.assertEqual(page["next_offset"], 1)
            found = [page["data"][0]["id"]]
            for offset in (1, 2):
                page = services.list_records(
                    self.raw, "meals", {"date": "2026-10-30"}, 20, offset
                )
                services.json_value(page, maximum=65536)
                found.extend(item["id"] for item in page["data"])
            self.assertEqual(found, ids)
            self.assertFalse(page["has_more"])

    def test_oversized_first_item_keeps_later_items_reachable(self):
        meal = self.make_meal()
        replace_meal_items(
            meal_entry=meal,
            item_inputs=[
                {"food_item": self.food, "servings": 1, "order": index}
                for index in range(2)
            ],
        )
        first, second = list(meal.items.all())
        original = services.MealItemSerializer.to_representation

        def expanded(serializer, item):
            output = original(serializer, item)
            return (
                output | {"synthetic_expansion": ["é" * 1900] * 10}
                if item.pk == first.pk
                else output
            )

        with patch.object(services.MealItemSerializer, "to_representation", expanded):
            page = services.get_meal(self.raw, meal.pk)
            self.assertTrue(page["truncated"])
            self.assertTrue(page["has_more"])
            self.assertEqual(page["next_offset"], 1)
            self.assertEqual(page["data"]["item_id"], first.pk)
            self.assertNotIn("items", page["data"])
            remaining = services.get_meal(self.raw, meal.pk, 20, page["next_offset"])
            self.assertFalse(remaining["truncated"])
            self.assertFalse(remaining["has_more"])
            self.assertEqual(
                [item["id"] for item in remaining["data"]["items"]], [second.pk]
            )

    def test_offset_limit_returns_explicit_terminal_summary(self):
        meal = self.make_meal()
        item = meal.items.first()
        MealItem.objects.bulk_create(
            [
                MealItem(
                    **{
                        field.attname: getattr(item, field.attname)
                        for field in MealItem._meta.fields
                        if not field.primary_key and field.name != "order"
                    },
                    order=index,
                )
                for index in range(1, 1003)
            ]
        )
        page = services.get_meal(self.raw, meal.pk, 1, 1000)
        self.assertTrue(page["truncated"])
        self.assertFalse(page["has_more"])
        self.assertIsNone(page["next_offset"])
        self.assertTrue(page["data"]["pagination_limit_reached"])
        self.assertIn("MacroMapper", page["data"]["detail"])
        MealEntry.objects.bulk_create(
            [
                MealEntry(
                    owner=self.user,
                    entry_date=meal.entry_date,
                    name="Synthetic diary entry",
                )
                for _ in range(1002)
            ]
        )
        listing = services.list_records(
            self.raw, "meals", {"date": meal.entry_date.isoformat()}, 1, 1000
        )
        self.assertTrue(listing["truncated"])
        self.assertFalse(listing["has_more"])
        self.assertIsNone(listing["next_offset"])
        self.assertTrue(listing["data"][0]["pagination_limit_reached"])

    def test_json_node_and_byte_limits_remain_unchanged_at_boundaries(self):
        under = [[0] * 99 for _ in range(19)] + [[0] * 98]
        self.assertEqual(services.json_value(under, maximum=65536), under)
        over = under + [0]
        with self.assertRaises(ValidationError):
            services.json_value(over, maximum=65536)
        under_bytes = ["x" * 2000] * 32
        encoded = len(json.dumps(under_bytes).encode())
        self.assertEqual(services.json_value(under_bytes, maximum=encoded), under_bytes)
        with self.assertRaises(ValidationError):
            services.json_value(under_bytes, maximum=encoded - 1)
