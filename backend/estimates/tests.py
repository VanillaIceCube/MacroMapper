from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from pydantic import ValidationError as PydanticValidationError
from rest_framework.test import APIClient

from foods.models import FoodItem, FoodItemVersion
from foods.nutrients import NUTRIENT_FIELDS
from foods.services import create_food_item
from meals.models import MealEntry

from .models import MealProposal
from .provider import (
    SYSTEM_PROMPT,
    EstimatedFood,
    EstimatedMeal,
    EstimatedNutrients,
    EstimatedSource,
    EstimationProviderError,
    OpenAIMealEstimationProvider,
)


def shared_food(*, name, provider_name="", origin_type="generic", components=None):
    return create_food_item(
        name=name,
        scope=FoodItem.Scope.SHARED,
        origin_type=origin_type,
        provider_name=provider_name,
        owner=None,
        definition={
            "serving_quantity": Decimal("1"),
            "serving_unit": FoodItemVersion.ServingUnit.ITEM,
            "serving_label": "one item",
            "provenance": FoodItemVersion.Provenance.OFFICIAL,
            "confidence_score": Decimal("0.990"),
            "nutrients": {
                "calories": Decimal("100"),
                "protein": Decimal("10"),
                "carbohydrates": Decimal("5"),
                "fat": Decimal("4"),
            },
            "sources": [
                {
                    "title": f"{name} nutrition",
                    "provider": provider_name or "Example source",
                    "url": f"https://example.com/{name.lower().replace(' ', '-')}",
                }
            ],
            "components": components or [],
        },
        created_by=None,
    )


def ai_estimate():
    source = {
        "title": "Restaurant nutrition",
        "provider": "Example Restaurant",
        "url": "https://example.com/nutrition",
        "accessed_on": None,
        "is_official": True,
    }
    component_nutrients = {
        "calories": "200",
        "protein": "12",
        "carbohydrates": "20",
        "fat": "8",
        "fiber": None,
        "sugar": None,
        "sodium": "300",
        "cholesterol": None,
    }
    component = {
        "key": "ai-0.0",
        "food_item_id": None,
        "food_version_id": None,
        "name": "Burger patty",
        "provider_name": "Example Restaurant",
        "origin_type": "restaurant",
        "servings": "2",
        "serving_quantity": "1",
        "serving_unit": "item",
        "serving_label": "one patty",
        "provenance": "ai_estimate",
        "source_kind": "ai_estimate",
        "confidence_score": "0.800",
        "nutrients": component_nutrients,
        "sources": [source],
        "components": [],
    }
    return {
        "name": "Estimated burger",
        "confidence_score": Decimal("0.800"),
        "provider_name": "OpenAI",
        "provider_model": "gpt-test",
        "provider_response_id": "resp_test",
        "items": [
            {
                "key": "ai-0",
                "food_item_id": None,
                "food_version_id": None,
                "name": "Restaurant burger",
                "provider_name": "Example Restaurant",
                "origin_type": "restaurant",
                "servings": "1",
                "serving_quantity": "1",
                "serving_unit": "item",
                "serving_label": "one burger",
                "provenance": "ai_estimate",
                "source_kind": "ai_estimate",
                "confidence_score": "0.800",
                "nutrients": {field: "0" for field in NUTRIENT_FIELDS},
                "sources": [source],
                "components": [component],
            }
        ],
    }


class MealProposalApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="owner", email="owner@example.com", password="secret-pass"
        )
        self.other_user = get_user_model().objects.create_user(
            username="other", email="other@example.com", password="secret-pass"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_catalog_match_bypasses_provider_and_retains_official_source(self):
        patty = shared_food(name="Beef patty")
        shared_food(
            name="Double-Double",
            provider_name="In-N-Out",
            origin_type=FoodItem.OriginType.RESTAURANT,
            components=[{"food_item": patty, "servings": Decimal("2"), "order": 0}],
        )

        with patch("estimates.services.get_estimation_provider") as provider:
            response = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "Double-Double from In-N-Out",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        provider.assert_not_called()
        self.assertEqual(response.data["generator"], MealProposal.Generator.CATALOG)
        self.assertEqual(response.data["items"][0]["source_kind"], "official_verified")
        self.assertEqual(
            response.data["items"][0]["components"][0]["name"], "Beef patty"
        )
        self.assertEqual(
            response.data["items"][0]["sources"][0]["url"],
            "https://example.com/double-double",
        )

    def test_ai_proposal_can_be_edited_and_accepted_as_private_snapshot(self):
        provider = Mock()
        provider.estimate.return_value = ai_estimate()
        with patch("estimates.services.get_estimation_provider", return_value=provider):
            created = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "A restaurant burger without cheese",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(created.status_code, 201)
        proposal_id = created.data["id"]
        item = created.data["items"][0]
        self.assertEqual(created.data["items"][0]["nutrients"]["calories"], "400")
        item["components"][0]["servings"] = "1"
        item["source_kind"] = "official_verified"
        item["provenance"] = "official"
        item["nutrients"]["calories"] = "1"
        updated = self.client.patch(
            f"/api/meal-proposals/{proposal_id}/",
            {"name": "Cheese-free burger", "items": [item]},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["items"][0]["nutrients"]["calories"], "200")
        self.assertEqual(updated.data["items"][0]["source_kind"], "ai_estimate")
        self.assertEqual(updated.data["items"][0]["provenance"], "ai_estimate")

        accepted = self.client.post(f"/api/meal-proposals/{proposal_id}/accept/")

        self.assertEqual(accepted.status_code, 201)
        proposal = MealProposal.objects.get(pk=proposal_id)
        self.assertEqual(proposal.provider_name, "OpenAI")
        self.assertEqual(proposal.provider_model, "gpt-test")
        self.assertEqual(proposal.provider_response_id, "resp_test")
        self.assertEqual(proposal.status, MealProposal.Status.ACCEPTED)
        meal = MealEntry.objects.get(pk=accepted.data["id"])
        self.assertEqual(meal.owner, self.user)
        self.assertEqual(meal.name, "Cheese-free burger")
        saved_item = meal.items.get()
        self.assertEqual(saved_item.calories, Decimal("200"))
        self.assertEqual(saved_item.component_snapshot[0]["food_name"], "Burger patty")
        self.assertEqual(saved_item.component_snapshot[0]["servings"], "1.0000")
        self.assertEqual(
            saved_item.food_version.food_item.scope, FoodItem.Scope.PERSONAL
        )
        self.assertEqual(
            saved_item.food_version.provenance, FoodItemVersion.Provenance.AI_ESTIMATE
        )
        self.assertEqual(
            saved_item.food_version.sources.get().url,
            "https://example.com/nutrition",
        )

        second_accept = self.client.post(f"/api/meal-proposals/{proposal_id}/accept/")
        self.assertEqual(second_accept.status_code, 400)
        edit_after_accept = self.client.patch(
            f"/api/meal-proposals/{proposal_id}/",
            {"name": "Changed"},
            format="json",
        )
        self.assertEqual(edit_after_accept.status_code, 400)

    def test_ai_proposal_rounds_provider_values_to_storage_precision(self):
        estimate = ai_estimate()
        item = estimate["items"][0]
        component = item["components"][0]
        item["servings"] = "1.23456"
        item["serving_quantity"] = "1.23456"
        item["confidence_score"] = "0.87654"
        component["servings"] = "1.23456"
        component["serving_quantity"] = "0.33333"
        component["confidence_score"] = "0.65432"
        component["nutrients"]["calories"] = "200.123456"
        provider = Mock()
        provider.estimate.return_value = estimate

        with patch("estimates.services.get_estimation_provider", return_value=provider):
            created = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "A precisely estimated restaurant burger",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(created.status_code, 201)
        accepted = self.client.post(f"/api/meal-proposals/{created.data['id']}/accept/")

        self.assertEqual(accepted.status_code, 201)
        saved_item = MealEntry.objects.get(pk=accepted.data["id"]).items.get()
        self.assertEqual(saved_item.servings, Decimal("1.2346"))
        self.assertEqual(saved_item.food_version.serving_quantity, Decimal("1.235"))
        self.assertEqual(saved_item.food_version.confidence_score, Decimal("0.877"))
        saved_component = saved_item.food_version.components.get()
        self.assertEqual(saved_component.servings, Decimal("1.2346"))
        self.assertEqual(
            saved_component.child_version.serving_quantity, Decimal("0.333")
        )
        self.assertEqual(
            saved_component.child_version.confidence_score, Decimal("0.654")
        )
        self.assertEqual(saved_component.child_version.calories, Decimal("200.1235"))

    def test_ai_proposal_accepts_reviewed_component_nutrients(self):
        provider = Mock()
        provider.estimate.return_value = ai_estimate()
        with patch("estimates.services.get_estimation_provider", return_value=provider):
            created = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "A restaurant burger with adjusted nutrition",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        item = created.data["items"][0]
        item["components"][0]["nutrients"]["calories"] = "175"
        item["components"][0]["nutrients"]["protein"] = "10"
        updated = self.client.patch(
            f"/api/meal-proposals/{created.data['id']}/",
            {"items": [item]},
            format="json",
        )

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["items"][0]["nutrients"]["calories"], "350")
        self.assertEqual(updated.data["items"][0]["nutrients"]["protein"], "20")
        accepted = self.client.post(f"/api/meal-proposals/{created.data['id']}/accept/")
        self.assertEqual(accepted.status_code, 201)
        saved_item = MealEntry.objects.get(pk=accepted.data["id"]).items.get()
        self.assertEqual(saved_item.calories, Decimal("350"))
        saved_component = saved_item.food_version.components.get()
        self.assertEqual(saved_component.child_version.calories, Decimal("175"))
        self.assertEqual(saved_component.child_version.protein, Decimal("10"))

    def test_catalog_nutrient_adjustment_creates_a_personal_copy(self):
        catalog_food = shared_food(name="Protein bar")
        created = self.client.post(
            "/api/meal-proposals/",
            {"description": "Protein bar", "entry_date": "2026-08-16"},
            format="json",
        )
        item = created.data["items"][0]
        item["nutrients"]["calories"] = "125"

        updated = self.client.patch(
            f"/api/meal-proposals/{created.data['id']}/",
            {"items": [item]},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        accepted = self.client.post(f"/api/meal-proposals/{created.data['id']}/accept/")

        self.assertEqual(accepted.status_code, 201)
        saved_version = (
            MealEntry.objects.get(pk=accepted.data["id"]).items.get().food_version
        )
        self.assertNotEqual(saved_version.food_item_id, catalog_food.pk)
        self.assertEqual(saved_version.food_item.scope, FoodItem.Scope.PERSONAL)
        self.assertEqual(
            saved_version.provenance, FoodItemVersion.Provenance.USER_ENTERED
        )
        self.assertEqual(saved_version.calories, Decimal("125"))
        catalog_food.refresh_from_db()
        self.assertEqual(catalog_food.current_version.calories, Decimal("100"))

    def test_proposals_are_owner_scoped(self):
        MealProposal.objects.create(
            owner=self.other_user,
            description="Private meal",
            entry_date=date(2026, 8, 16),
            name="Private meal",
            generator=MealProposal.Generator.CATALOG,
            items=[],
        )
        response = self.client.get("/api/meal-proposals/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_provider_failure_returns_safe_service_unavailable(self):
        provider = Mock()
        provider.estimate.side_effect = EstimationProviderError("Provider unavailable.")
        with patch("estimates.services.get_estimation_provider", return_value=provider):
            response = self.client.post(
                "/api/meal-proposals/",
                {"description": "Unknown meal", "entry_date": "2026-08-16"},
                format="json",
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["detail"], "Provider unavailable.")
        self.assertFalse(MealProposal.objects.exists())


@override_settings(
    OPENAI_API_KEY="test-key",
    OPENAI_MEAL_ESTIMATION_MODEL="gpt-test",
    OPENAI_MEAL_ESTIMATION_TIMEOUT=10,
)
class OpenAIProviderTests(TestCase):
    def test_source_url_schema_is_supported_and_still_validated(self):
        source_url_schema = EstimatedMeal.model_json_schema()["$defs"][
            "EstimatedSource"
        ]["properties"]["url"]

        self.assertEqual(source_url_schema["type"], "string")
        self.assertNotIn("format", source_url_schema)
        servings_schema = EstimatedMeal.model_json_schema()["$defs"]["EstimatedFood"][
            "properties"
        ]["servings"]
        self.assertEqual(servings_schema["type"], "number")
        self.assertNotIn("pattern", servings_schema)
        with self.assertRaises(PydanticValidationError):
            EstimatedSource(
                title="Unsafe source",
                provider="Example",
                url="ftp://example.com/label",
            )

    def test_provider_uses_web_search_structured_output_and_retains_metadata(self):
        parsed = EstimatedMeal(
            name="Toast",
            confidence_score=Decimal("0.7"),
            items=[
                EstimatedFood(
                    name="Toast",
                    confidence_score=Decimal("0.7"),
                    nutrients=EstimatedNutrients(calories=Decimal("80")),
                    sources=[
                        EstimatedSource(
                            title="Official label",
                            provider="Example",
                            url="https://example.com/label",
                            is_official=True,
                        )
                    ],
                )
            ],
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            id="resp_123", output_parsed=parsed
        )

        result = OpenAIMealEstimationProvider(client=client).estimate("toast")

        request = client.responses.parse.call_args.kwargs
        self.assertEqual(request["tools"], [{"type": "web_search"}])
        self.assertEqual(request["text_format"], EstimatedMeal)
        self.assertFalse(request["store"])
        self.assertEqual(result["provider_model"], "gpt-test")
        self.assertEqual(result["provider_response_id"], "resp_123")
        self.assertEqual(
            result["items"][0]["sources"][0]["url"], "https://example.com/label"
        )

    def test_prompt_forbids_medical_advice(self):
        self.assertIn("Do not provide dietary", SYSTEM_PROMPT)
        self.assertIn("medical", SYSTEM_PROMPT)
