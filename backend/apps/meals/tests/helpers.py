"""Synthetic meal definitions and owner-scoped diary fixtures."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status

from apps.foods.models import FoodItem, FoodItemVersion
from apps.foods.services import (
    create_food_item,
)

User = get_user_model()


def definition(*, calories="100", protein="5", components=None):
    return {
        "serving_quantity": Decimal("1"),
        "serving_unit": FoodItemVersion.ServingUnit.ITEM,
        "serving_label": "one item",
        "provenance": FoodItemVersion.Provenance.USER_ENTERED,
        "confidence_score": None,
        "nutrients": {
            "calories": Decimal(calories),
            "protein": Decimal(protein),
        },
        "sources": [],
        "components": components or [],
    }


class MealEntryFixtures:
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="owner-password",
        )
        self.other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="other-password",
        )
        self.apple = create_food_item(
            name="Apple",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.owner,
            definition=definition(calories="95", protein="0.5"),
            created_by=self.owner,
        )
        self.toast = create_food_item(
            name="Toast",
            scope=FoodItem.Scope.SHARED,
            origin_type=FoodItem.OriginType.BRANDED,
            provider_name="Example Bakery",
            owner=None,
            definition={
                **definition(calories="80", protein="3"),
                "provenance": FoodItemVersion.Provenance.OFFICIAL,
                "confidence_score": Decimal("0.990"),
            },
            created_by=self.owner,
        )
        self.other_food = create_food_item(
            name="Private pear",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.other_user,
            definition=definition(),
            created_by=self.other_user,
        )

    def payload(self, **overrides):
        payload = {
            "entry_date": "2026-08-16",
            "name": "Breakfast",
            "notes": "Before work",
            "item_inputs": [
                {"food_item": self.apple.id, "servings": "2", "order": 0},
                {"food_item": self.toast.id, "servings": "1", "order": 1},
            ],
        }
        payload.update(overrides)
        return payload

    def create_meal(self, **overrides):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            "/api/meals/", self.payload(**overrides), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response
