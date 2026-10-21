from decimal import Decimal

from foods.models import FoodItem, FoodItemVersion
from foods.nutrients import NUTRIENT_FIELDS
from foods.services import create_food_item


def shared_food(
    *,
    name,
    provider_name="",
    origin_type="generic",
    components=None,
    provenance=FoodItemVersion.Provenance.OFFICIAL,
    confidence="0.990",
):
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
            "provenance": provenance,
            "confidence_score": Decimal(confidence),
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


def simple_ai_estimate(*, name="Apple", calories="95"):
    estimate = ai_estimate()
    estimate["name"] = name
    item = estimate["items"][0]
    item.update(
        {
            "name": name,
            "provider_name": "",
            "origin_type": "generic",
            "servings": "1",
            "serving_label": f"one {name.lower()}",
            "serving_weight_grams": "182",
            "serving_volume_ml": None,
            "nutrients": {
                field: calories if field == "calories" else None
                for field in NUTRIENT_FIELDS
            },
            "components": [],
        }
    )
    return estimate
