"""Catalog-backed food and meal operations preserve REST schemas and validation."""

from copy import deepcopy
from datetime import date
from unittest import skipUnless

from django.conf import settings
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.estimates.models import MealProposal
from apps.estimates.services import _catalog_food
from apps.foods.models import FoodItem
from apps.meals.models import MealEntry

from .. import operations, queries
from .helpers import MCPToolFixtures, definition


@skipUnless(settings.MCP_ENABLED, "Run the enabled app-owned OAuth profile")
class MCPCatalogOperationTests(MCPToolFixtures, TestCase):
    def test_personal_food_create_update_archive_uses_rest_validation(self):
        payload = {
            "name": "Personal food",
            "origin_type": "generic",
            "provider_name": "",
            "definition": definition(),
        }
        food_id = self.execute(self.request("food.create", payload=payload))["result"][
            "data"
        ]["id"]
        food = FoodItem.objects.get(pk=food_id)
        self.assertEqual(food.owner_id, self.user.pk)
        self.execute(self.request("food.update", food_id, {"name": "Renamed"}))
        self.execute(self.request("food.archive", food_id, {}))
        food.refresh_from_db()
        self.assertIsNotNone(food.archived_at)

    def test_schema_exposes_typed_writable_fields_and_no_querysets(self):
        schema = operations.operation_schema(self.raw, "food.create")["data"]
        self.assertIn("definition", schema["fields"])
        self.assertTrue(schema["fields"]["definition"]["required"])
        self.assertNotIn("scope", schema["fields"])
        self.assertIn("nutrients", schema["fields"]["definition"]["fields"])
        self.assertNotIn("owner", schema["fields"])
        paid = operations.operation_schema(self.raw, "proposal.estimate")["data"]
        self.assertEqual(set(paid["fields"]), {"description", "entry_date"})
        self.assertTrue(paid["paid"])

    def test_meal_item_descriptors_match_food_identity_and_serving_serializer_bounds(
        self,
    ):
        from apps.estimates.serializers import MapYourMealItemsField, ProposalItemsField

        for action in (
            "meal.draft_create",
            "meal.draft_update",
            "proposal.update",
            "proposal.follow_up",
            "proposal.adjustment",
        ):
            descriptor = operations.operation_schema(self.raw, action)["data"][
                "fields"
            ]["items"]["items"]["fields"]
            for identity_field in ("market", "product_identifier", "identity_url"):
                self.assertEqual(descriptor[identity_field]["type"], "string")
            self.assertEqual(descriptor["natural_servings"]["type"], "array")
            self.assertEqual(descriptor["natural_servings"]["max_length"], 12)
            self.assertEqual(
                set(descriptor["natural_servings"]["items"]),
                {"key", "label", "weight_grams"},
            )
            self.assertEqual(descriptor["portion_options"]["max_length"], 20)
        definition_descriptor = operations.operation_schema(self.raw, "food.create")[
            "data"
        ]["fields"]["definition"]["fields"]["natural_servings"]
        self.assertEqual(definition_descriptor["type"], "array")
        self.assertEqual(definition_descriptor["max_length"], 12)

        item = _catalog_food(self.food.current_version)
        item["natural_servings"] = [
            {
                "key": f"size{index}",
                "label": f"Size {index}",
                "weight_grams": str(index + 1),
            }
            for index in range(12)
        ]
        item["portion_options"] = [
            {
                "key": f"portion{index}",
                "label": f"Portion {index}",
                "unit_label": "item",
                "serving_multiplier": "1",
            }
            for index in range(20)
        ]
        item["selected_portion_key"] = "portion0"
        for field_class in (MapYourMealItemsField, ProposalItemsField):
            validated = field_class().run_validation([item])[0]
            self.assertEqual(len(validated["natural_servings"]), 12)
            self.assertEqual(len(validated["portion_options"]), 20)
            for key, extra in (
                (
                    "natural_servings",
                    {"key": "extra", "label": "Extra", "weight_grams": "1"},
                ),
                (
                    "portion_options",
                    {
                        "key": "extra",
                        "label": "Extra",
                        "unit_label": "item",
                        "serving_multiplier": "1",
                    },
                ),
            ):
                oversized = deepcopy(item)
                oversized[key].append(extra)
                with self.assertRaises(ValidationError):
                    field_class().run_validation([oversized])

    def test_catalog_drafts_proposal_review_acceptance_and_bounded_reads(self):
        from apps.estimates.services import (
            create_builder_proposal,
            prepare_builder_proposal,
        )

        fields = dict(
            owner=self.user,
            entry_date=date(2026, 10, 30),
            name="Draft",
            notes="",
            items=[_catalog_food(self.food.current_version)],
        )
        # The extracted preparation helper is pure; the existing REST helper
        # still persists exactly the same proposal and initial revision policy.
        prepared = prepare_builder_proposal(**fields)
        self.assertFalse(MealProposal.objects.exists())
        proposal = create_builder_proposal(**fields)
        self.assertEqual(proposal.name, prepared["name"])
        updated = self.execute(
            self.request("proposal.update", proposal.pk, {"name": "Reviewed"})
        )
        self.assertEqual(updated["result"]["data"]["name"], "Reviewed")
        with self.assertRaises(ValidationError):
            self.execute(
                self.request(
                    "proposal.update", proposal.pk, {"description": "ignored by REST"}
                )
            )
        self.execute(self.request("proposal.delete", proposal.pk, {}))
        draft = self.execute(
            self.request(
                "meal.draft_create",
                payload={
                    "entry_date": "2026-10-30",
                    "name": "Catalog diary",
                    "notes": "",
                    "items": fields["items"],
                },
            )
        )
        meal_id = draft["result"]["data"]["id"]
        with self.assertRaises(ValidationError):
            self.execute(
                self.request(
                    "meal.draft_update",
                    meal_id,
                    {"entry_date": "2026-10-30", "notes": "", "items": fields["items"]},
                )
            )
        self.assertTrue(
            operations.operation_schema(self.raw, "meal.draft_update")["data"][
                "fields"
            ]["name"]["required"]
        )
        self.execute(
            self.request(
                "meal.draft_update",
                meal_id,
                {
                    "entry_date": "2026-10-30",
                    "name": "Renamed",
                    "notes": "",
                    "items": fields["items"],
                },
            )
        )
        listing = queries.list_records(self.raw, "meals", {"date": "2026-10-30"}, 1, 0)
        self.assertEqual(listing["data"][0]["name"], "Renamed")
        self.assertEqual(
            queries.nutrition_totals(self.raw, date(2026, 10, 30), date(2026, 10, 30))[
                "data"
            ]["meal_count"],
            1,
        )
        with self.assertRaises(ValidationError):
            queries.nutrition_totals(self.raw, date(2026, 1, 1), date(2026, 2, 1))
        self.assertEqual(
            queries.list_records(self.raw, "foods", {"search": "Apple"}, 10, 0)["data"][
                0
            ]["id"],
            self.food.pk,
        )
        # Build through the existing catalog service, then separately request
        # acceptance into the diary rather than treating estimates as meals.
        proposal = create_builder_proposal(
            **(fields | {"items": [_catalog_food(self.food.current_version)]})
        )
        accepted = self.execute(self.request("proposal.accept", proposal.pk, {}))
        self.assertTrue(
            MealEntry.objects.filter(
                pk=accepted["result"]["data"]["id"], owner=self.user
            ).exists()
        )
        with self.assertRaises(ValidationError):
            self.execute(
                self.request("proposal.update", proposal.pk, {"name": "Too late"})
            )
