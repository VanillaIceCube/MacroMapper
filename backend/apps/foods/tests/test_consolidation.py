"""Conservative shared-food consolidation preserving every historical reference."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.estimates.models import MealProposal, MealProposalRevision
from apps.estimates.services import (
    _catalog_food,
    _materialize_item,
    _visible_catalog_versions_map,
)
from apps.meals.models import MealEntry, MealItem
from apps.meals.services import replace_meal_items

from ..models import (
    FoodComponent,
    FoodItem,
)
from ..services import (
    consolidate_shared_foods,
    create_food_item,
    create_food_version,
)
from .helpers import CanonicalIdentityFixtures, definition, source


class FoodConsolidationTests(CanonicalIdentityFixtures, TestCase):
    def test_consolidation_preserves_source_verification_and_retrieval_evidence(self):
        canonical = self.legacy()
        duplicate = self.legacy(calories="145")
        original = duplicate.current_version
        original.evidence = {
            "status": "partially_source_backed",
            "research_status": "found",
            "nutrients": {
                "calories": {
                    "status": "official_verified",
                    "source_urls": [source()["url"]],
                }
            },
        }
        original.save(update_fields=["evidence"])
        reference = original.sources.get()
        reference.is_official = True
        reference.evidence = {
            "retrieved": True,
            "retrieval_response_id": "historical-retrieval",
            "nutrients": {"calories": "145"},
        }
        reference.save(update_fields=["is_official", "evidence"])

        consolidate_shared_foods([canonical.pk, duplicate.pk], apply=True)

        copied = canonical.versions.get(derived_from=original)
        self.assertEqual(copied.evidence, original.evidence)
        self.assertIs(copied.sources.get().is_official, True)
        self.assertEqual(copied.sources.get().evidence, reference.evidence)
        original.refresh_from_db()
        self.assertEqual(original.food_item_id, duplicate.pk)

    def test_recipe_consolidation_uses_legacy_pinned_child_sources_not_current_version(
        self,
    ):
        us_child = self.legacy()
        uk_definition = definition(
            sources=[
                source("https://www.mcdonalds.com/gb/en-gb/product/hash-brown.html")
            ]
        )
        uk_child = create_food_item(
            name=us_child.name,
            scope="shared",
            origin_type=us_child.origin_type,
            provider_name=us_child.provider_name,
            owner=None,
            definition=uk_definition,
            created_by=None,
        )
        us_version = us_child.current_version
        uk_version = uk_child.current_version
        self.assertIsNone(us_child.canonical_identity)
        self.assertIsNone(uk_child.canonical_identity)
        self.assertEqual(us_version.content_fingerprint, uk_version.content_fingerprint)
        # A later current definition cannot replace the identity evidence attached
        # to the exact child version already pinned in the recipe.
        new_current = create_food_version(
            food_item=us_child, definition=uk_definition, created_by=None
        )
        self.assertNotEqual(new_current.pk, us_version.pk)
        us_recipe_definition = {
            **definition(),
            "components": [
                {
                    "food_item": us_child,
                    "food_version": us_version,
                    "servings": Decimal("1"),
                    "order": 0,
                }
            ],
        }
        uk_recipe_definition = {
            **definition(),
            "components": [
                {
                    "food_item": uk_child,
                    "food_version": uk_version,
                    "servings": Decimal("1"),
                    "order": 0,
                }
            ],
        }
        recipe_fields = {
            "name": "Legacy regional breakfast",
            "scope": "shared",
            "origin_type": "generic",
            "provider_name": "",
            "owner": None,
            "created_by": None,
        }
        canonical_recipe = create_food_item(
            **recipe_fields, definition=us_recipe_definition
        )
        duplicate_recipe = create_food_item(
            **recipe_fields, definition=uk_recipe_definition
        )
        original_us_recipe = canonical_recipe.current_version
        original_uk_recipe = duplicate_recipe.current_version
        self.assertNotEqual(
            original_us_recipe.content_fingerprint,
            original_uk_recipe.content_fingerprint,
        )

        consolidate_shared_foods([canonical_recipe.pk, duplicate_recipe.pk], apply=True)
        copied_uk_recipe = canonical_recipe.versions.get(
            derived_from=original_uk_recipe
        )
        repeated = create_food_version(
            food_item=canonical_recipe, definition=uk_recipe_definition, created_by=None
        )

        self.assertEqual(canonical_recipe.versions.count(), 2)
        self.assertEqual(repeated.pk, copied_uk_recipe.pk)
        self.assertEqual(
            original_us_recipe.components.get().child_version_id, us_version.pk
        )
        self.assertEqual(
            original_uk_recipe.components.get().child_version_id, uk_version.pk
        )
        self.assertEqual(
            copied_uk_recipe.components.get().child_version_id, uk_version.pk
        )

    def test_legacy_consolidation_preserves_meals_components_proposals_and_derivation(
        self,
    ):
        canonical = self.legacy(confidence="0.8")
        duplicate = self.legacy(
            name="Hash Brown", calories="145", confidence="0.95", origin_type="branded"
        )
        original = duplicate.current_version
        personal = create_food_item(
            name="My hash brown",
            scope="personal",
            origin_type="generic",
            provider_name="",
            owner=self.user,
            definition={**definition("150"), "derived_from": original},
            created_by=self.user,
        )
        composite = create_food_item(
            name="Breakfast",
            scope="shared",
            origin_type="generic",
            provider_name="",
            owner=None,
            definition={
                **definition("300"),
                "components": [
                    {
                        "food_item": duplicate,
                        "food_version": original,
                        "servings": Decimal("2"),
                        "order": 0,
                    }
                ],
            },
            created_by=None,
        )
        meal = MealEntry.objects.create(
            owner=self.user, name="Before consolidation", entry_date=date(2026, 11, 11)
        )
        replace_meal_items(
            meal_entry=meal,
            item_inputs=[
                {
                    "food_item": duplicate,
                    "food_version": original.pk,
                    "servings": Decimal("2"),
                    "order": 0,
                }
            ],
        )
        snapshot = MealItem.objects.get(meal_entry=meal)
        proposal_items = [_catalog_food(original)]
        proposal = MealProposal.objects.create(
            owner=self.user,
            description="hash browns",
            entry_date=date(2026, 11, 11),
            name="Old proposal",
            items=proposal_items,
        )
        revision = MealProposalRevision.objects.create(
            proposal=proposal,
            revision_number=1,
            kind="generated",
            name=proposal.name,
            items=proposal_items,
        )

        self.assertEqual(
            consolidate_shared_foods([canonical.pk, duplicate.pk]).pk, canonical.pk
        )
        duplicate.refresh_from_db()
        self.assertIsNone(duplicate.archived_at)
        consolidate_shared_foods([canonical.pk, duplicate.pk], apply=True)

        duplicate.refresh_from_db()
        canonical.refresh_from_db()
        self.assertEqual(duplicate.merged_into_id, canonical.pk)
        self.assertIsNotNone(duplicate.archived_at)
        self.assertEqual(canonical.versions.count(), 2)
        self.assertEqual(canonical.current_version.calories, Decimal("145"))
        original.refresh_from_db()
        self.assertEqual(original.food_item_id, duplicate.pk)
        self.assertEqual(original.calories, Decimal("145"))
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.calories, Decimal("290"))
        self.assertEqual(snapshot.food_version_id, original.pk)
        self.assertEqual(
            FoodComponent.objects.get(
                parent_version=composite.current_version
            ).child_version_id,
            original.pk,
        )
        self.assertEqual(personal.current_version.derived_from_id, original.pk)
        proposal.refresh_from_db()
        revision.refresh_from_db()
        self.assertEqual(proposal.items, proposal_items)
        self.assertEqual(revision.items, proposal_items)
        visible = _visible_catalog_versions_map(
            owner=self.user, pairs={(duplicate.pk, original.pk)}
        )
        self.assertIn((duplicate.pk, original.pk), visible)
        self.assertEqual(
            _materialize_item(owner=self.user, item=proposal_items[0])[1].pk,
            original.pk,
        )
        self.assertEqual(
            FoodItem.objects.active()
            .filter(scope="shared", name__startswith="Hash Brown")
            .count(),
            1,
        )
        client = APIClient()
        client.force_authenticate(self.user)
        alias_response = client.get(f"/api/foods/{duplicate.pk}/")
        self.assertEqual(alias_response.status_code, 200)
        self.assertEqual(alias_response.data["merged_into"], canonical.pk)

    def test_consolidation_deduplicates_equivalent_versions_and_keeps_evidence(self):
        canonical = self.legacy(confidence="0.8")
        duplicate = self.legacy(confidence="0.95")
        consolidate_shared_foods([canonical.pk, duplicate.pk], apply=True)
        self.assertEqual(canonical.versions.count(), 1)
        self.assertEqual(canonical.current_version.estimate_evidence.count(), 2)

    def test_consolidation_rejects_personal_foods_and_distinct_products(self):
        canonical = self.legacy()
        other = self.legacy()
        other.market = "GB"
        other.save()
        with self.assertRaises(ValidationError):
            consolidate_shared_foods([canonical.pk, other.pk], apply=True)
        other.scope = "personal"
        other.owner = self.user
        other.save()
        with self.assertRaises(ValidationError):
            consolidate_shared_foods([canonical.pk, other.pk], apply=True)
