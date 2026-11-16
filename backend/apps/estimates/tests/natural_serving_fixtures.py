"""Catalog food and portion fixtures for natural serving behavior."""

from decimal import Decimal

from django.contrib.auth import get_user_model

from apps.foods.models import FoodItem
from apps.foods.services import create_food_item

from ..provider import EstimatedFood, _serialize_food
from ..services import (
    _shared_estimate_items,
)


class NaturalServingFixtures:
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="size-owner")
        cls.sizes = [
            {"key": key, "label": key.title(), "weight_grams": weight}
            for key, weight in (("small", "150"), ("medium", "180"), ("large", "225"))
        ]
        cls.apple = create_food_item(
            name="Red apple",
            scope="shared",
            origin_type="generic",
            provider_name="",
            owner=None,
            created_by=None,
            definition={
                "serving_quantity": Decimal("1"),
                "serving_unit": "item",
                "serving_label": "1 small apple",
                "serving_weight_grams": Decimal("150"),
                "natural_servings": cls.sizes,
                "provenance": "ai_estimate",
                "confidence_score": Decimal("0.8"),
                "nutrients": {"calories": Decimal("80")},
                "sources": [],
                "components": [],
            },
        )

    def small_only_catalog_apple(self):
        serialized = _serialize_food(
            EstimatedFood(
                name="Yellow apple",
                serving_unit="item",
                serving_label="1 small apple",
                serving_weight_grams=150,
                confidence_score=0.8,
                nutrients={"calories": 80},
            ),
            key="small-yellow-apple",
        )
        item = _shared_estimate_items(self.size_estimate(serialized))[0]
        food = FoodItem.objects.get(pk=item["food_item_id"])
        return food, item

    def size_estimate(self, item):
        return {
            "name": "Yellow apples",
            "confidence_score": Decimal("0.8"),
            "provider_name": "OpenAI",
            "provider_model": "mock-only",
            "provider_response_id": "mock-size-response",
            "items": [item],
        }

    def large_yellow_apple(self, *, servings=1):
        return _serialize_food(
            EstimatedFood(
                name="Large yellow apple",
                servings=servings,
                serving_unit="item",
                serving_label="1 item",
                serving_weight_grams=225,
                natural_servings=[
                    {"key": "large", "label": "Large", "weight_grams": 225}
                ],
                confidence_score=0.8,
                nutrients={"calories": 120},
            ),
            key="large-yellow-apple",
        )

    def weightless_medium_personal_apple(self):
        return create_food_item(
            name="Yellow apple",
            scope="personal",
            origin_type="generic",
            provider_name="",
            owner=self.user,
            created_by=self.user,
            definition={
                "serving_quantity": Decimal("1"),
                "serving_unit": "item",
                "serving_label": "1 medium apple",
                "serving_weight_grams": None,
                "natural_servings": [
                    {"key": "large", "label": "Large", "weight_grams": "225"}
                ],
                "provenance": "user_entered",
                "confidence_score": None,
                "nutrients": {"calories": Decimal("80")},
                "sources": [],
                "components": [],
            },
        )
