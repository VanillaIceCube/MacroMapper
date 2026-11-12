from copy import deepcopy
from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from estimates.models import MealProposal, MealProposalRevision
from estimates.services import (
    _catalog_food,
    _materialize_item,
    _visible_catalog_versions_map,
    resolve_catalog_matches,
)
from meals.models import MealEntry, MealItem
from meals.services import replace_meal_items

from .identity import canonical_food_identity
from .models import FoodComponent, FoodItem
from .services import (
    consolidate_shared_foods,
    create_food_item,
    create_food_version,
    publish_shared_food,
)


def definition(
    calories="140", *, confidence="0.9", provenance="ai_estimate", sources=None
):
    return {
        "serving_quantity": Decimal("1"),
        "serving_unit": "item",
        "serving_label": "1 hash brown",
        "serving_weight_grams": Decimal("53"),
        "provenance": provenance,
        "confidence_score": Decimal(confidence),
        "nutrients": {"calories": Decimal(calories)},
        "sources": sources or [],
        "components": [],
        "estimation_provider": "OpenAI",
        "estimation_model": "mock-model",
        "estimation_response_id": "mock-response",
    }


def source(url="https://www.mcdonalds.com/us/en-us/product/hash-browns.html"):
    return {"title": "Product information", "provider": "McDonald's", "url": url}


class CanonicalFoodIdentityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="identity-owner")
        self.item = {
            "name": "Hash Browns",
            "provider_name": "McDonald's",
            "origin_type": "restaurant",
        }

    def publish(self, *, item=None, **kwargs):
        return publish_shared_food(
            item=item or self.item, definition=definition(**kwargs)
        )

    def legacy(
        self,
        *,
        name="Hash Browns",
        calories="140",
        confidence="0.9",
        origin_type="restaurant",
    ):
        return create_food_item(
            name=name,
            scope="shared",
            origin_type=origin_type,
            provider_name="McDonald's",
            owner=None,
            definition=definition(calories, confidence=confidence, sources=[source()]),
            created_by=None,
        )

    def test_provider_punctuation_pluralization_and_classification_share_identity(self):
        food, original = self.publish()
        variant = {
            "name": "Hash Brown",
            "provider_name": "McDonalds",
            "origin_type": "branded",
        }
        second_food, alternative = self.publish(
            item=variant, calories="145", confidence="0.95"
        )
        self.assertEqual(food.pk, second_food.pk)
        self.assertNotEqual(original.pk, alternative.pk)
        original.refresh_from_db()
        self.assertEqual(original.calories, Decimal("140"))
        self.assertEqual(food.versions.count(), 2)
        food.refresh_from_db()
        self.assertEqual(food.current_version_id, alternative.pk)

    def test_equivalent_definition_reuses_version_and_preserves_estimate_evidence(self):
        food, original = self.publish(confidence="0.8", sources=[source()])
        _, repeated = self.publish(
            confidence="0.95",
            sources=[source(), source("https://example.com/independent-nutrition")],
        )
        self.assertEqual(original.pk, repeated.pk)
        self.assertEqual(food.versions.count(), 1)
        self.assertEqual(repeated.sources.count(), 2)
        self.assertEqual(repeated.estimate_evidence.count(), 2)
        original.refresh_from_db()
        self.assertEqual(original.confidence_score, Decimal("0.8"))

    def test_official_evidence_wins_over_more_recent_high_confidence_ai(self):
        food, official = self.publish(
            provenance="official", confidence="0.8", sources=[source()]
        )
        _, ai = self.publish(calories="142", confidence="1", sources=[source()])
        food.refresh_from_db()
        self.assertNotEqual(official.pk, ai.pk)
        self.assertEqual(food.current_version_id, official.pk)

    def test_new_verified_evidence_creates_a_version_in_the_same_canonical_food(self):
        original_definition = definition(
            provenance="official", confidence="1", sources=[source()]
        )
        food, original = publish_shared_food(
            item=self.item, definition=original_definition
        )
        verified_definition = deepcopy(original_definition)
        verified_definition["confidence_score"] = Decimal("0.5")
        verified_definition["evidence"] = {
            "status": "official_verified",
            "research_status": "found",
            "region": "US",
            "nutrients": {
                "calories": {
                    "status": "official_verified",
                    "source_urls": [source()["url"]],
                }
            },
            "confidence": {"model": 0.5, "combined": 0.5, "evidence": None},
        }
        verified_definition["sources"][0].update(
            is_official=True,
            evidence={
                "retrieved": True,
                "retrieval_response_id": "retrieval-first",
                "product_name": "Hash Browns",
                "brand": "McDonald's",
                "region": "US",
                "serving_quantity": "1",
                "serving_unit": "item",
                "serving_label": "1 hash brown",
                "serving_weight_grams": "53",
                "nutrients": {"calories": "140"},
            },
        )

        same_food, verified = publish_shared_food(
            item=self.item, definition=verified_definition
        )

        self.assertEqual(food.pk, same_food.pk)
        self.assertNotEqual(original.pk, verified.pk)
        food.refresh_from_db()
        self.assertEqual(food.current_version_id, verified.pk)
        original.refresh_from_db()
        self.assertEqual(original.evidence, {})
        self.assertIsNone(original.sources.get().is_official)
        repeated_definition = deepcopy(verified_definition)
        repeated_definition["evidence"]["confidence"]["model"] = 0.8
        repeated_definition["sources"][0]["evidence"]["retrieval_response_id"] = (
            "retrieval-second"
        )
        repeated = create_food_version(
            food_item=food, definition=repeated_definition, created_by=None
        )
        self.assertEqual(repeated.pk, verified.pk)
        retrieval_ids = {
            entry.metadata["sources"][0]["evidence"]["retrieval_response_id"]
            for entry in repeated.estimate_evidence.all()
        }
        self.assertEqual(retrieval_ids, {"retrieval-first", "retrieval-second"})

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

    def test_version_reuse_preserves_confidence_and_source_validation_gates(self):
        food, original = self.publish()
        for invalid in (
            {**definition(), "confidence_score": Decimal("2")},
            {**definition(), "sources": [{"title": "Bad URL", "url": "not-a-url"}]},
        ):
            with self.assertRaises(ValidationError):
                create_food_version(food_item=food, definition=invalid, created_by=None)
        self.assertEqual(food.versions.count(), 1)
        self.assertEqual(original.estimate_evidence.count(), 1)

    def test_current_version_tie_uses_earliest_version(self):
        food, original = self.publish()
        self.publish(calories="141")
        food.refresh_from_db()
        self.assertEqual(food.current_version_id, original.pk)

    def test_market_product_identifiers_and_provider_urls_keep_distinct_products(self):
        base = canonical_food_identity(
            **self.item, market="US", product_identifier="101"
        )
        variants = [
            {"market": "UK", "product_identifier": "101"},
            {"market": "US", "product_identifier": "102"},
        ]
        for variant in variants:
            self.assertNotEqual(base, canonical_food_identity(**self.item, **variant))
        self.assertNotEqual(
            canonical_food_identity(**self.item, sources=[source()]),
            canonical_food_identity(
                **self.item,
                sources=[
                    source("https://www.mcdonalds.com/gb/en-gb/product/hash-brown.html")
                ],
            ),
        )

    def test_generic_sizes_share_identity_but_branded_size_variants_do_not(self):
        self.assertEqual(
            canonical_food_identity(name="Small red apples"),
            canonical_food_identity(name="Large red apple"),
        )
        self.assertNotEqual(
            canonical_food_identity(
                name="Small shake", provider_name="Brand", origin_type="branded"
            ),
            canonical_food_identity(
                name="Large shake", provider_name="Brand", origin_type="branded"
            ),
        )

    def test_serving_definition_changes_are_versions(self):
        food, original = self.publish()
        revised = definition()
        revised["serving_weight_grams"] = Decimal("60")
        changed = create_food_version(
            food_item=food, definition=revised, created_by=None
        )
        self.assertNotEqual(original.pk, changed.pk)
        self.assertEqual(food.versions.count(), 2)

    def test_natural_servings_validate_and_participate_in_definition_fingerprint(self):
        food, original = self.publish()
        revised = definition()
        revised["natural_servings"] = [
            {"key": "small", "label": "Small", "weight_grams": "40"}
        ]
        changed = create_food_version(
            food_item=food, definition=revised, created_by=None
        )
        self.assertNotEqual(original.pk, changed.pk)
        revised["natural_servings"][0]["weight_grams"] = "NaN"
        with self.assertRaises(ValidationError):
            create_food_version(food_item=food, definition=revised, created_by=None)

    def test_no_op_materialization_retains_shared_but_material_override_stays_private(
        self,
    ):
        food, original = self.publish()
        item = _catalog_food(original, servings="4")
        saved_food, saved_version = _materialize_item(owner=self.user, item=item)
        self.assertEqual((saved_food.pk, saved_version.pk), (food.pk, original.pk))
        changed = deepcopy(item)
        changed["nutrients"]["calories"] = "155"
        personal, version = _materialize_item(owner=self.user, item=changed)
        self.assertEqual(personal.owner, self.user)
        self.assertEqual(personal.scope, "personal")
        self.assertEqual(version.derived_from_id, original.pk)
        self.assertEqual(FoodItem.objects.active().filter(scope="shared").count(), 1)

    def test_normalized_serving_definitions_reuse_the_same_shared_version(self):
        from .serializers import FoodDefinitionInputSerializer

        original = definition()
        original["natural_servings"] = [
            {"key": "small", "label": "Small", "weight_grams": "40"}
        ]
        food, first = publish_shared_food(item=self.item, definition=original)
        incoming = deepcopy(original)
        incoming["natural_servings"] = [
            {"key": "small", "label": "  Small  ", "weight_grams": 40.0}
        ]
        # Exercise the API normalization boundary before the shared version service.
        serializer = FoodDefinitionInputSerializer(data=incoming)
        serializer.is_valid(raise_exception=True)

        repeated = create_food_version(
            food_item=food, definition=serializer.validated_data, created_by=None
        )

        self.assertEqual(repeated.pk, first.pk)
        self.assertEqual(repeated.natural_servings, original["natural_servings"])
        self.assertEqual(food.versions.count(), 1)

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

    def test_management_command_dry_run_does_not_mutate_records(self):
        first = self.legacy()
        second = self.legacy()
        output = StringIO()
        call_command("consolidate_foods", first.pk, second.pk, stdout=output)
        self.assertIn("Dry run", output.getvalue())
        self.assertEqual(FoodItem.objects.active().count(), 2)
        self.assertFalse(FoodItem.objects.exclude(canonical_identity=None).exists())

    def test_existing_no_op_personal_copy_does_not_shadow_shared_for_its_owner(self):
        shared, original = self.publish()
        personal = create_food_item(
            name=shared.name,
            scope="personal",
            origin_type=shared.origin_type,
            provider_name=shared.provider_name,
            owner=self.user,
            definition={**definition(), "derived_from": original},
            created_by=self.user,
        )
        for user in (
            self.user,
            get_user_model().objects.create_user(
                username="other-identity-owner", email="other-identity@example.com"
            ),
        ):
            resolution = resolve_catalog_matches(
                description="4 hash browns mcdonalds", user=user
            )
            self.assertEqual(resolution["matches"][0]["food"].pk, shared.pk)
            self.assertEqual(resolution["matches"][0]["servings"], Decimal("4"))
        create_food_version(
            food_item=personal,
            definition={**definition("200"), "derived_from": original},
            created_by=self.user,
        )
        resolution = resolve_catalog_matches(
            description="4 hash browns mcdonalds", user=self.user
        )
        self.assertEqual(resolution["matches"][0]["food"].pk, personal.pk)
