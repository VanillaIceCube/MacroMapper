"""Recipe portions, parent verification and regional publication evidence."""

from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.foods.models import FoodItem, FoodItemVersion

from ..models import MealProposal
from ..provider import (
    EstimationProviderError,
)
from ..services import (
    _catalog_food,
    _shared_estimate_items,
    accept_reviewed_proposal,
    apply_proposal_follow_up,
)
from .helpers import estimate as researched_estimate
from .helpers import pizza as researched_pizza
from .helpers import shared_food


class RecipeEvidenceIntegrationTests(TestCase):
    """Recipe instance edits retain exact-source nutrition evidence boundaries."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="recipe-evidence-owner", email="recipe-evidence@example.com"
        )

    def verified_recipe(self, *, fraction="1"):
        item = _shared_estimate_items(
            researched_estimate(researched_pizza(components=True))
        )[0]
        self.assertEqual(item["evidence"]["status"], "source_backed_ai_components")
        self.assertEqual(Decimal(item["nutrients"]["calories"]), Decimal("710"))
        self.assertEqual(
            Decimal(item["components"][0]["nutrients"]["calories"]), Decimal("400")
        )
        self.assertTrue(item["sources"][0]["is_official"])
        self.assertTrue(item["sources"][0]["evidence"]["retrieved"])
        item["servings"] = fraction
        addon = shared_food(name="Yogurt side")
        proposal = MealProposal.objects.create(
            owner=self.owner,
            entry_date=date(2026, 11, 11),
            name="Pizza and yogurt",
            description="A prepared recipe with separately consumed yogurt",
            items=[item, _catalog_food(addon.current_version, key="side")],
        )
        return proposal

    def test_fraction_preserves_verified_parent_values_over_inferred_component_sum(
        self,
    ):
        proposal = self.verified_recipe()
        original = deepcopy(proposal.items[0])
        version_id = original["food_version_id"]
        outcome = apply_proposal_follow_up(
            proposal=proposal,
            owner=self.owner,
            follow_up="I ate 75% of that recipe but all of the separate yogurt",
            items=deepcopy(proposal.items),
            result={
                "fraction_updates": [
                    {
                        "key": original["key"],
                        "fraction": "0.75",
                        "excluded_keys": ["side"],
                    }
                ]
            },
        )
        self.assertTrue(outcome["applied"])
        proposal.refresh_from_db()
        item = proposal.items[0]
        self.assertEqual(item["components"], original["components"])
        self.assertEqual(item["evidence"], original["evidence"])
        self.assertEqual(Decimal(item["nutrients"]["calories"]), Decimal("710"))
        self.assertEqual(Decimal(item["servings"]), Decimal("0.75"))
        self.assertEqual(Decimal(proposal.items[1]["servings"]), Decimal("1"))
        meal = accept_reviewed_proposal(self.owner, proposal)
        saved = meal.items.get(order=0)
        self.assertEqual(saved.food_version_id, version_id)
        self.assertEqual(saved.calories, Decimal("532.5"))
        self.assertEqual(
            sum(row.calories for row in meal.items.all()), Decimal("632.5")
        )
        self.assertEqual(Decimal(saved.component_snapshot[0]["servings"]), Decimal("1"))
        version = FoodItemVersion.objects.get(pk=version_id)
        self.assertEqual(version.calories, Decimal("710"))
        self.assertTrue(version.sources.get().is_official)
        self.assertEqual(FoodItem.objects.filter(scope="personal").count(), 0)

    def test_reparenting_invalidates_parent_verification_and_rolls_up_recipe_once(self):
        proposal = self.verified_recipe(fraction="0.75")
        original = deepcopy(proposal.items[0])
        version_id = original["food_version_id"]
        outcome = apply_proposal_follow_up(
            proposal=proposal,
            owner=self.owner,
            follow_up="Put the yogurt inside the recipe instead of keeping it separate",
            items=deepcopy(proposal.items),
            result={"reparentings": [{"key": "side", "parent_key": original["key"]}]},
        )
        self.assertTrue(outcome["applied"])
        proposal.refresh_from_db()
        self.assertEqual(len(proposal.items), 1)
        changed = proposal.items[0]
        self.assertEqual(len(changed["components"]), 2)
        self.assertEqual(Decimal(changed["servings"]), Decimal("0.75"))
        self.assertEqual(Decimal(changed["nutrients"]["calories"]), Decimal("500"))
        self.assertEqual(changed["provenance"], "user_modified_estimate")
        self.assertEqual(changed["evidence"]["status"], "user_modified_estimate")
        self.assertEqual(changed["evidence"]["nutrients"], {})
        self.assertEqual(changed["sources"], original["sources"])
        meal = accept_reviewed_proposal(self.owner, proposal)
        self.assertEqual(meal.items.get().calories, Decimal("375"))
        original_version = FoodItemVersion.objects.get(pk=version_id)
        self.assertEqual(original_version.calories, Decimal("710"))
        self.assertEqual(original_version.components.count(), 1)
        self.assertEqual(
            original_version.evidence["status"], "source_backed_ai_components"
        )
        self.assertEqual(meal.items.get().food_version.derived_from_id, version_id)

    def test_verified_publication_gets_version_without_splitting_canonical_food(self):
        raw = researched_pizza()
        raw["sources"] = []
        unverified = _shared_estimate_items(researched_estimate(raw))[0]
        verified = _shared_estimate_items(researched_estimate(researched_pizza()))[0]
        self.assertEqual(unverified["food_item_id"], verified["food_item_id"])
        self.assertNotEqual(unverified["food_version_id"], verified["food_version_id"])
        self.assertEqual(verified["provenance"], "official")
        repeated = researched_pizza()
        repeated["confidence_score"] = "0.7"
        repeated["sources"][0]["evidence"]["retrieval_response_id"] = (
            "another-retrieval"
        )
        reused = _shared_estimate_items(researched_estimate(repeated))[0]
        self.assertEqual(reused["food_version_id"], verified["food_version_id"])
        canonical = FoodItem.objects.get(pk=verified["food_item_id"])
        self.assertEqual(canonical.versions.count(), 2)
        self.assertEqual(canonical.current_version_id, verified["food_version_id"])
        version = FoodItemVersion.objects.get(pk=verified["food_version_id"])
        self.assertTrue(version.sources.get().is_official)
        self.assertTrue(version.sources.get().evidence["retrieved"])

    def test_conflicting_market_and_evidence_region_rejects_publication_atomically(
        self,
    ):
        item = researched_pizza(components=True)
        item["market"] = "GB"
        self.assertEqual(item["region"], "US")
        self.assertEqual(item["sources"][0]["evidence"]["region"], "US")
        with self.assertRaises(EstimationProviderError):
            _shared_estimate_items(researched_estimate(item))
        self.assertEqual(FoodItem.objects.count(), 0)
        self.assertEqual(FoodItemVersion.objects.count(), 0)

    def test_market_only_and_region_only_share_verified_regional_identity(self):
        region_only = _shared_estimate_items(researched_estimate(researched_pizza()))[0]
        canonical = FoodItem.objects.get(pk=region_only["food_item_id"])
        self.assertEqual(canonical.market, "US")
        market_item = researched_pizza()
        market_item.pop("region")
        market_item["evidence"] = {"research_status": "found"}
        market_item["market"] = "US"
        market_only = _shared_estimate_items(researched_estimate(market_item))[0]
        self.assertEqual(market_only["food_item_id"], region_only["food_item_id"])
        self.assertEqual(market_only["food_version_id"], region_only["food_version_id"])
        self.assertEqual(market_only["provenance"], "official")
        self.assertEqual(market_only["evidence"]["region"], "US")
        self.assertEqual(
            market_only["evidence"]["nutrients"]["calories"]["status"],
            "official_verified",
        )
        self.assertEqual(canonical.versions.count(), 1)
