"""Synthetic MCP reliability regressions; no owner data or paid provider calls."""

import json
from datetime import timedelta
from unittest import skipUnless
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from estimates.models import MealProposal
from estimates.services import _catalog_food
from foods.models import FoodItem
from foods.nutrients import NUTRIENT_FIELDS
from foods.services import create_food_item
from meals.models import MealEntry, MealItem
from meals.serializers import MealEntrySerializer
from meals.services import replace_meal_items

from . import services
from .models import Confirmation
from .tests import Fixtures, definition


class SafeGuidanceTests(SimpleTestCase):
    def test_fixed_guidance_survives_tool_error_sanitization(self):
        from . import server

        def invalid(raw):
            raise services.OperationError("Inspect current records and preview again.")

        with self.assertRaisesMessage(
            server.ToolError, "Inspect current records and preview again."
        ):
            async_to_sync(server.call)(invalid)


@skipUnless(settings.MCP_ENABLED, "Run the enabled app-owned OAuth profile")
class MealReliabilityTests(Fixtures, TestCase):
    def composite(self):
        children = []
        for index in range(6):
            data = definition()
            data["nutrients"] = dict.fromkeys(NUTRIENT_FIELDS, "1")
            child = create_food_item(
                name=f"Synthetic ingredient {index}",
                scope="shared",
                origin_type="generic",
                provider_name="",
                owner=None,
                definition=data,
                created_by=None,
            )
            children.append({"food_item": child, "servings": "1", "order": index})
        data = definition()
        data["components"] = children
        return create_food_item(
            name="Synthetic composite",
            scope="shared",
            origin_type="generic",
            provider_name="",
            owner=None,
            definition=data,
            created_by=None,
        )

    def draft_payload(self, foods):
        return {
            "entry_date": "2026-10-30",
            "name": "Synthetic draft",
            "notes": "",
            "items": [
                _catalog_food(food.current_version, key=f"fixture-{index}")
                for index, food in enumerate(foods)
            ],
        }

    def test_large_updates_save_once_instead_of_rolling_back_output_budget(self):
        food = self.composite()
        for action in ("meal.update", "meal.draft_update", "meal.draft_create"):
            with self.subTest(action=action):
                meal = self.make_meal() if action != "meal.draft_create" else None
                if action == "meal.update":
                    payload = self.meal_payload()
                    payload["item_inputs"] = [
                        {"food_item": food.pk, "servings": "1", "order": index}
                        for index in range(5)
                    ]
                else:
                    payload = self.draft_payload([food] * 5)
                services.json_value(payload)  # Existing 32-KiB / 2,000-node limit.
                pending = self.preview(action, meal.pk if meal else None, payload)
                before = MealEntry.objects.count()
                outcome = self.confirm(pending)
                self.assertTrue(outcome["applied"])
                self.assertTrue(outcome["result"]["truncated"])
                saved = MealEntry.objects.get(pk=outcome["result"]["data"]["id"])
                self.assertEqual(saved.items.count(), 5)
                self.assertEqual(MealEntry.objects.count(), before + (meal is None))
                services.json_value(outcome, maximum=65536)
                with self.assertRaises(ValidationError):
                    services.result(MealEntrySerializer(saved).data)
                with self.assertRaises(ValidationError):
                    self.confirm(pending)
                self.assertFalse(
                    Confirmation.objects.filter(pk=pending["confirmation_id"]).exists()
                )

    def test_unlinked_manual_draft_fails_at_preview_with_catalog_guidance(self):
        payload = self.draft_payload([self.food])
        manual = {
            "key": "manual-bar",
            "name": "Synthetic ice cream bar",
            "provenance": "user_entered",
            "source_kind": "user_entered",
            "nutrients": {"calories": "180", "fiber": None},
            "sources": [{"title": "Retailer", "url": "https://example.com/bar"}],
        }
        for items in ([manual], payload["items"] + [manual]):
            with self.subTest(mixed=len(items) > 1):
                payload["items"] = items
                with self.assertRaisesMessage(ValidationError, "food.create"):
                    self.preview("meal.draft_create", payload=payload)
                self.assertFalse(Confirmation.objects.exists())
                self.assertFalse(MealEntry.objects.exists())
                self.assertFalse(MealProposal.objects.exists())

    def test_manual_food_create_then_mixed_draft_saves_once_without_ai(self):
        with patch(
            "estimates.services.get_estimation_provider",
            side_effect=AssertionError("No paid request"),
        ):
            personal = self.confirm(
                self.preview(
                    "food.create",
                    payload={
                        "name": "Synthetic manual bar",
                        "origin_type": "generic",
                        "provider_name": "",
                        "definition": definition("180"),
                    },
                )
            )
            food = FoodItem.objects.get(pk=personal["result"]["data"]["id"])
            self.assertEqual(food.owner, self.user)
            payload = self.draft_payload([self.food, food])
            payload["items"][0]["servings"] = "0.5"
            pending = self.preview("meal.draft_create", payload=payload)
            self.assertFalse(MealEntry.objects.exists())
            outcome = self.confirm(pending)
            self.assertFalse(outcome["result"]["truncated"])
            meal_id = outcome["result"]["data"]["id"]
            self.assertEqual(MealEntry.objects.count(), 1)
            self.assertEqual(MealItem.objects.filter(meal_entry_id=meal_id).count(), 2)
            with self.assertRaises(ValidationError):
                self.confirm(pending)
            self.assertFalse(MealProposal.objects.exists())

    def test_small_update_and_draft_update_preserve_full_results(self):
        meal = self.make_meal()
        for action, payload in (
            ("meal.update", {"notes": "Small edit"}),
            ("meal.draft_update", self.draft_payload([self.food])),
        ):
            with self.subTest(action=action):
                outcome = self.confirm(self.preview(action, meal.pk, payload))
                self.assertFalse(outcome["result"]["truncated"])
                self.assertEqual(outcome["result"]["data"]["id"], meal.pk)
                self.assertEqual(len(outcome["result"]["data"]["items"]), 1)

    def test_byte_budget_success_receipt_does_not_mask_business_failure(self):
        meal = self.make_meal()
        original = MealEntrySerializer.to_representation

        def oversized(serializer, instance):
            return original(serializer, instance) | {
                "synthetic_expansion": ["é" * 1900] * 10
            }

        with patch.object(MealEntrySerializer, "to_representation", oversized):
            pending = self.preview(
                "meal.update", meal.pk, {"notes": "Saved despite bytes"}
            )
            outcome = self.confirm(pending)
        self.assertTrue(outcome["result"]["truncated"])
        self.assertEqual(outcome["result"]["data"]["id"], meal.pk)
        services.json_value(outcome, maximum=65536)
        meal.refresh_from_db()
        self.assertEqual(meal.notes, "Saved despite bytes")
        with self.assertRaises(ValidationError):
            self.confirm(pending)

    def test_real_business_failure_rolls_back_meal_items_and_approval(self):
        meal = self.make_meal()
        before_items = list(meal.items.values_list("pk", flat=True))
        pending = self.preview(
            "meal.update",
            meal.pk,
            {
                "name": "Must roll back",
                "item_inputs": self.meal_payload()["item_inputs"],
            },
        )

        def fail_after_delete(*, meal_entry, item_inputs):
            meal_entry.items.all().delete()
            raise DjangoValidationError("Synthetic business failure")

        with patch("meals.serializers.replace_meal_items", fail_after_delete):
            with self.assertRaises(DjangoValidationError):
                self.confirm(pending)
        meal.refresh_from_db()
        self.assertEqual(meal.name, "Lunch")
        self.assertEqual(list(meal.items.values_list("pk", flat=True)), before_items)
        self.assertTrue(
            Confirmation.objects.filter(pk=pending["confirmation_id"]).exists()
        )

    def test_draft_business_failure_rolls_back_new_personal_food_and_approval(self):
        payload = self.draft_payload([self.food])
        payload["items"][0]["nutrients"]["calories"] = "250"
        pending = self.preview("meal.draft_create", payload=payload)
        before = FoodItem.objects.count()
        with patch(
            "estimates.services.replace_meal_items",
            side_effect=DjangoValidationError("Synthetic business failure"),
        ):
            with self.assertRaises(ValidationError):
                self.confirm(pending)
        self.assertEqual(FoodItem.objects.count(), before)
        self.assertFalse(MealEntry.objects.exists())
        self.assertFalse(MealItem.objects.exists())
        self.assertTrue(
            Confirmation.objects.filter(pk=pending["confirmation_id"]).exists()
        )

    def test_old_pending_manual_draft_is_rechecked_without_consuming_approval(self):
        pending = self.preview(
            "meal.draft_create", payload=self.draft_payload([self.food])
        )
        # Simulate an approval produced before preview applied business checks.
        payload = self.draft_payload([self.food])
        payload["items"][0].update(food_item_id=None, food_version_id=None)
        Confirmation.objects.filter(pk=pending["confirmation_id"]).update(
            payload=payload,
            fingerprint=services.snapshot(
                "meal.draft_create", None, self.user, payload, []
            ),
        )
        with self.assertRaisesMessage(ValidationError, "food.create"):
            self.confirm(pending)
        self.assertTrue(
            Confirmation.objects.filter(pk=pending["confirmation_id"]).exists()
        )
        self.assertFalse(MealEntry.objects.exists())

    def test_confirmation_errors_are_actionable_and_stale_draft_is_unchanged(self):
        with self.assertRaisesMessage(ValidationError, "Invalid confirmation ID"):
            services.confirm_change(self.raw, "invalid", True, False)
        pending = self.preview(
            "meal.draft_create", payload=self.draft_payload([self.food])
        )
        Confirmation.objects.filter(pk=pending["confirmation_id"]).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        with self.assertRaisesMessage(ValidationError, "expired, already used"):
            self.confirm(pending)
        meal = self.make_meal()
        pending = self.preview(
            "meal.draft_update", meal.pk, self.draft_payload([self.food])
        )
        meal.notes = "Website changed"
        meal.save()
        with self.assertRaisesMessage(ValidationError, "Target or catalog changed"):
            self.confirm(pending)
        meal.refresh_from_db()
        self.assertEqual(meal.notes, "Website changed")

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

    def test_foreign_food_and_changed_components_fail_draft_preview_without_writes(
        self,
    ):
        foreign = create_food_item(
            name="Private food",
            scope="personal",
            origin_type="generic",
            provider_name="",
            owner=self.other,
            definition=definition(),
            created_by=self.other,
        )
        with self.assertRaises(ValidationError):
            self.preview("meal.draft_create", payload=self.draft_payload([foreign]))
        food = self.composite()
        payload = self.draft_payload([food])
        payload["items"][0]["components"][0]["food_version_id"] = (
            self.food.current_version_id
        )
        with self.assertRaisesMessage(ValidationError, "matching components"):
            self.preview("meal.draft_create", payload=payload)
        self.assertFalse(MealEntry.objects.exists())
        self.assertFalse(Confirmation.objects.exists())

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
