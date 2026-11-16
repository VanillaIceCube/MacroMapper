"""Version reuse, verification coverage and deterministic current versions."""

from copy import deepcopy
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.estimates.services import (
    _shared_estimate_items,
)

from ..models import (
    FoodItemVersion,
)
from ..services import (
    create_food_version,
    publish_shared_food,
)
from .helpers import (
    CanonicalIdentityFixtures,
    definition,
    source,
)


class FoodVersionPublicationTests(CanonicalIdentityFixtures, TestCase):
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

    def test_publication_merges_ordinary_citations_without_splitting_versions(self):
        from apps.estimates.tests.helpers import simple_ai_estimate

        estimate = simple_ai_estimate(name="Synthetic fruit")
        item = estimate["items"][0]
        item["region"] = "US"
        item["sources"] = [
            {
                "title": "Ordinary citation",
                "provider": "Example",
                "url": "https://example.com/nutrition-one",
                "is_official": False,
                "evidence": {},
            }
        ]
        original_item = _shared_estimate_items(estimate)[0]
        item["sources"].append(
            {
                "title": "Another citation",
                "provider": "Example",
                "url": "https://example.com/nutrition-two",
                "is_official": False,
                "evidence": {},
            }
        )

        repeated_item = _shared_estimate_items(estimate)[0]

        self.assertEqual(repeated_item["food_item_id"], original_item["food_item_id"])
        self.assertEqual(
            repeated_item["food_version_id"], original_item["food_version_id"]
        )
        version = FoodItemVersion.objects.get(pk=original_item["food_version_id"])
        self.assertEqual(version.food_item.versions.count(), 1)
        self.assertEqual(version.sources.count(), 2)
        self.assertEqual(version.estimate_evidence.count(), 2)
        recorded_sources = [
            entry.metadata["sources"] for entry in version.estimate_evidence.all()
        ]
        self.assertEqual(sorted(len(sources) for sources in recorded_sources), [1, 2])
        self.assertTrue(
            all(
                reference.is_official is False and reference.evidence == {}
                for reference in version.sources.all()
            )
        )

        # A first-party flag is retained as new immutable source content, but a
        # bare flag still cannot establish verified nutrient coverage.
        item["sources"][0]["is_official"] = True
        first_party_item = _shared_estimate_items(estimate)[0]
        self.assertEqual(
            first_party_item["food_item_id"], original_item["food_item_id"]
        )
        self.assertNotEqual(
            first_party_item["food_version_id"], original_item["food_version_id"]
        )
        self.assertEqual(first_party_item["evidence"]["status"], "ai_estimate")
        self.assertIs(
            version.sources.get(url=item["sources"][0]["url"]).is_official, False
        )

        item["sources"][0]["evidence"] = {
            "retrieved": True,
            "retrieval_response_id": "retrieved-fruit",
            "product_name": item["name"],
            "brand": "",
            "region": "US",
            "serving_quantity": item["serving_quantity"],
            "serving_unit": item["serving_unit"],
            "serving_label": item["serving_label"],
            "serving_weight_grams": item["serving_weight_grams"],
            "nutrients": {"calories": item["nutrients"]["calories"]},
        }
        verified_item = _shared_estimate_items(estimate)[0]
        self.assertEqual(verified_item["food_item_id"], original_item["food_item_id"])
        self.assertNotEqual(
            verified_item["food_version_id"], first_party_item["food_version_id"]
        )
        self.assertEqual(verified_item["evidence"]["status"], "official_verified")

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
