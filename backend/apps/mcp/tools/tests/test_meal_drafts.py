"""MCP draft preview, committed receipts, rollback and stale-state rejection."""

from datetime import timedelta
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.estimates.models import MealProposal
from apps.foods.models import FoodItem
from apps.foods.services import create_food_item
from apps.meals.models import MealEntry, MealItem
from apps.meals.serializers import MealEntrySerializer

from .. import services
from ..models import Confirmation
from .helpers import MealToolFixtures, definition


@skipUnless(settings.MCP_ENABLED, "Run the enabled app-owned OAuth profile")
class MCPMealDraftTests(MealToolFixtures, TestCase):
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
            "apps.estimates.services.get_estimation_provider",
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

        with patch("apps.meals.serializers.replace_meal_items", fail_after_delete):
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
            "apps.estimates.services.replace_meal_items",
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
