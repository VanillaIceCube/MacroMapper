"""Nutrition completeness, source verification and immutable catalog lineage."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.foods.models import FoodItem, FoodItemVersion
from apps.foods.serializers import FoodItemVersionSerializer
from apps.foods.services import create_food_item
from apps.meals.models import MealEntry
from apps.meals.serializers import MealItemSerializer
from apps.meals.services import replace_meal_items

from ..provider import (
    EstimatedMeal,
    EstimatedNutrients,
    EstimatedSource,
    EstimationProviderError,
    NutritionResearch,
    OpenAIMealEstimationProvider,
    SourceEvidence,
)
from ..services import _shared_estimate_items, create_proposal
from .helpers import URL, estimate, pizza, sdk_food, simple_ai_estimate, web_response


@override_settings(OPENAI_API_KEY="mock-only", OPENAI_MEAL_ESTIMATION_TIMEOUT=10)
class CatalogIntegrityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="owner", email="owner@example.com"
        )
        cls.other = get_user_model().objects.create_user(
            username="other", email="other@example.com"
        )

    def test_null_parent_or_component_never_partially_publishes(self):
        for nested in (False, True):
            with self.subTest(nested=nested):
                item = pizza(components=nested)
                target = item["components"][0] if nested else item
                target["nutrients"] = {field: None for field in target["nutrients"]}
                with self.assertRaisesMessage(
                    EstimationProviderError, "no usable nutrition"
                ):
                    _shared_estimate_items(estimate(item))
                self.assertEqual(FoodItem.objects.count(), 0)

    def test_zero_and_partial_nutrition_remain_valid(self):
        for calories in ("0", "710"):
            result = _shared_estimate_items(
                estimate(simple_ai_estimate(calories=calories)["items"][0])
            )
            self.assertEqual(
                Decimal(result[0]["nutrients"]["calories"]), Decimal(calories)
            )
            self.assertIsNone(result[0]["nutrients"]["fiber"])

    def test_other_shared_publication_paths_reject_empty_definitions(self):
        with self.assertRaisesMessage(ValidationError, "usable nutrition"):
            create_food_item(
                name="Empty cheese",
                scope="shared",
                origin_type="generic",
                provider_name="",
                owner=None,
                created_by=None,
                definition={
                    "serving_quantity": Decimal("1"),
                    "serving_unit": "item",
                    "provenance": "ai_estimate",
                    "confidence_score": Decimal(".8"),
                    "nutrients": {"calories": None},
                },
            )
        self.assertEqual(FoodItem.objects.count(), 0)

    def test_new_evidence_is_not_deduplicated_into_an_unsourced_estimate(self):
        raw = pizza()
        raw["sources"] = []
        first = _shared_estimate_items(estimate(raw))[0]
        verified = _shared_estimate_items(estimate(pizza()))[0]
        self.assertNotEqual(first["food_version_id"], verified["food_version_id"])
        self.assertEqual(verified["provenance"], "official")
        again = pizza()
        again["confidence_score"] = "0.7"
        again["sources"][0]["evidence"]["retrieval_response_id"] = "different_request"
        self.assertEqual(
            _shared_estimate_items(estimate(again))[0]["food_version_id"],
            verified["food_version_id"],
        )

    def test_returned_source_without_tool_retrieval_cannot_verify(self):
        item = sdk_food(pizza()).model_copy(update={"provider_name": ""})
        source = EstimatedSource(
            title="Claimed label",
            provider="Costco",
            url=URL,
            is_official=True,
            evidence=SourceEvidence(
                product_name=item.name,
                brand="",
                region="US",
                serving_label="1 slice",
                serving_unit="item",
                serving_weight_grams=300,
                nutrients=EstimatedNutrients(calories=710),
            ),
        )
        item.sources = [source]
        for urls, status in (
            (["https://www.costco.com/unrelated"], "completed"),
            ([URL], "failed"),
        ):
            with self.subTest(status=status):
                client = Mock()
                client.responses.parse.return_value = web_response(
                    EstimatedMeal(name="Pizza", confidence_score=0.99, items=[item]),
                    urls=urls,
                    status=status,
                )
                result = OpenAIMealEstimationProvider(client=client).estimate("pizza")[
                    "items"
                ][0]
                self.assertEqual(result["provenance"], "ai_estimate")
                self.assertFalse(result["sources"][0]["evidence"]["retrieved"])
                self.assertEqual(
                    result["evidence"]["research_status"],
                    "failed" if status == "failed" else "no_source_found",
                )

    def test_official_parent_and_inferred_child_survive_publication_reuse_and_diary(
        self,
    ):
        item = _shared_estimate_items(estimate(pizza(components=True)))[0]
        self.assertEqual(item["provenance"], "official")
        self.assertEqual(item["evidence"]["status"], "source_backed_ai_components")
        self.assertEqual(item["nutrients"]["calories"], "710")
        self.assertEqual(item["components"][0]["provenance"], "ai_estimate")
        self.assertEqual(item["evidence"]["confidence"]["combined"], 0.5)
        with patch("apps.estimates.services.get_estimation_provider") as provider:
            proposal = create_proposal(
                owner=self.other,
                description="Cheese Pizza Slice from Costco Food Court",
                entry_date=date(2026, 11, 11),
            )
        provider.assert_not_called()
        self.assertEqual(proposal.items[0]["food_version_id"], item["food_version_id"])
        version = FoodItemVersion.objects.get(pk=item["food_version_id"])
        catalog = FoodItemVersionSerializer(version).data
        self.assertTrue(catalog["sources"][0]["is_official"])
        self.assertEqual(catalog["evidence"]["status"], "source_backed_ai_components")
        meal = MealEntry.objects.create(
            owner=self.owner, entry_date=date(2026, 11, 11), name="Pizza"
        )
        replace_meal_items(
            meal_entry=meal,
            item_inputs=[
                {"food_item": version.food_item, "servings": Decimal("2"), "order": 0}
            ],
        )
        saved = meal.items.get()
        self.assertEqual(saved.calories, Decimal("1420"))
        self.assertEqual(
            MealItemSerializer(saved).data["sources"][0]["evidence"]["nutrients"][
                "calories"
            ],
            "710",
        )
        self.assertEqual(
            saved.component_snapshot[0]["evidence"]["status"], "ai_estimate"
        )

    def test_source_product_brand_region_serving_and_unretrieved_mismatches(self):
        for field, value in (
            ("product_name", "Frozen Pizza"),
            ("brand", "Other Brand"),
            ("region", "UK"),
            ("serving_label", "whole pizza"),
            ("serving_unit", "g"),
            ("serving_quantity", "2"),
            ("serving_weight_grams", "600"),
            ("retrieved", False),
        ):
            with self.subTest(field=field):
                item = pizza()
                item["sources"][0]["evidence"][field] = value
                result = _shared_estimate_items(estimate(item))[0]
                self.assertEqual(result["provenance"], "ai_estimate")

    def test_partial_source_coverage_does_not_verify_sugar_or_fiber(self):
        item = pizza()
        item["nutrients"].update(sugar="3", fiber="2")
        result = _shared_estimate_items(estimate(item))[0]
        self.assertEqual(result["provenance"], "ai_estimate")
        self.assertEqual(result["evidence"]["status"], "partially_source_backed")
        self.assertEqual(
            result["evidence"]["nutrients"]["calories"]["status"], "official_verified"
        )
        self.assertEqual(
            result["evidence"]["nutrients"]["sugar"]["status"], "ai_estimate"
        )
        self.assertEqual(
            result["evidence"]["nutrients"]["fiber"]["status"], "ai_estimate"
        )

    def test_high_confidence_or_url_alone_never_verifies(self):
        item = pizza()
        item["provenance"] = "official"
        item["confidence_score"] = "0.999"
        item["sources"][0].pop("evidence")
        result = _shared_estimate_items(estimate(item))[0]
        self.assertEqual(result["provenance"], "ai_estimate")
        self.assertTrue(result["sources"][0]["is_official"])

    def test_user_edit_clears_verification_but_retains_immutable_lineage(self):
        version_item = _shared_estimate_items(estimate(pizza(components=True)))[0]
        with patch("apps.estimates.services.get_estimation_provider"):
            proposal = create_proposal(
                owner=self.owner,
                description="Cheese Pizza Slice from Costco Food Court",
                entry_date=date(2026, 11, 11),
            )
        before = deepcopy(proposal.revisions.get().items)
        client = APIClient()
        client.force_authenticate(self.owner)
        unchanged = client.patch(
            f"/api/meal-proposals/{proposal.pk}/",
            {"items": proposal.items},
            format="json",
        )
        self.assertEqual(unchanged.status_code, 200)
        self.assertEqual(unchanged.data["items"][0]["provenance"], "official")
        edited = deepcopy(unchanged.data["items"])
        edited[0]["components"][0]["nutrients"]["calories"] = "300"
        edited[0]["evidence"] = {"status": "official_verified"}
        response = client.patch(
            f"/api/meal-proposals/{proposal.pk}/", {"items": edited}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["items"][0]["provenance"], "user_modified_estimate"
        )
        self.assertEqual(response.data["items"][0]["nutrients"]["calories"], "300")
        self.assertEqual(
            response.data["items"][0]["evidence"]["status"], "user_modified_estimate"
        )
        self.assertEqual(
            proposal.revisions.order_by("revision_number").first().items, before
        )
        self.assertEqual(
            FoodItemVersion.objects.get(pk=version_item["food_version_id"]).calories,
            Decimal("710"),
        )

    def test_costco_pizza_gets_targeted_search_and_retains_exact_source(self):
        food = sdk_food(pizza())
        source = EstimatedSource(
            title="Costco nutrition",
            provider="Costco",
            url=URL,
            is_official=True,
            evidence=SourceEvidence(
                product_name=food.name,
                brand=food.provider_name,
                region="US",
                serving_label="1 slice",
                serving_quantity=1,
                serving_unit="item",
                serving_weight_grams=300,
                nutrients=EstimatedNutrients(calories=710),
            ),
        )
        muffin = food.model_copy(
            update={
                "name": "Chocolate Muffin",
                "sources": [
                    source.model_copy(
                        update={
                            "evidence": source.evidence.model_copy(
                                update={"product_name": "Chocolate Muffin"}
                            )
                        }
                    )
                ],
            }
        )
        client = Mock()
        client.responses.parse.side_effect = [
            web_response(
                EstimatedMeal(
                    name="Costco Pizza & Muffin",
                    confidence_score=0.9,
                    items=[food, muffin],
                ),
                urls=[URL],
            ),
            web_response(NutritionResearch(sources=[source]), urls=[URL]),
        ]
        result = OpenAIMealEstimationProvider(client=client).estimate(
            "Costco Pizza + some chocolate muffins"
        )
        self.assertEqual(client.responses.parse.call_count, 2)
        research = client.responses.parse.call_args.kwargs
        self.assertEqual(research["tool_choice"], "required")
        self.assertIn("Cheese Pizza Slice", research["input"][1]["content"])
        self.assertNotIn("Chocolate Muffin", research["input"][1]["content"])
        self.assertEqual(result["items"][0]["evidence"]["research_status"], "found")
        self.assertEqual(result["items"][0]["sources"][0]["url"], URL)
        self.assertEqual(
            result["items"][1]["sources"][0]["evidence"]["product_name"],
            "Chocolate Muffin",
        )

    def test_retrieval_failure_distinct_from_no_source_and_fallback_kept(self):
        food = sdk_food(pizza())
        for research_result, status in (
            (web_response(NutritionResearch()), "no_source_found"),
            (RuntimeError("offline"), "failed"),
        ):
            client = Mock()
            client.responses.parse.side_effect = [
                web_response(
                    EstimatedMeal(name="Pizza", confidence_score=0.9, items=[food])
                ),
                research_result,
            ]
            result = OpenAIMealEstimationProvider(client=client).estimate(
                "Costco pizza"
            )["items"][0]
            self.assertEqual(result["evidence"]["research_status"], status)
            self.assertEqual(result["provenance"], "ai_estimate")
            self.assertEqual(result["nutrients"]["calories"], 710)
