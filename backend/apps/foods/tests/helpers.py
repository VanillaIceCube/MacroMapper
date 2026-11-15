"""Synthetic food definitions and fixture mixins without discoverable tests."""

from decimal import Decimal

from django.contrib.auth import get_user_model

from ..models import (
    FoodItem,
    FoodItemVersion,
)
from ..services import (
    create_food_item,
    publish_shared_food,
)

User = get_user_model()


def food_definition(*, calories="100", confidence="0.900", components=None):
    return {
        "serving_quantity": Decimal("1"),
        "serving_unit": FoodItemVersion.ServingUnit.ITEM,
        "serving_label": "one item",
        "provenance": FoodItemVersion.Provenance.USER_ENTERED,
        "confidence_score": (Decimal(confidence) if confidence is not None else None),
        "nutrients": {"calories": Decimal(calories)},
        "sources": [],
        "components": components or [],
    }


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


class FoodModelFixtures:
    def setUp(self):
        self.user = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="owner-password",
        )


class FoodApiFixtures:
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
        self.shared_food = create_food_item(
            name="Shared apple",
            scope=FoodItem.Scope.SHARED,
            origin_type=FoodItem.OriginType.BRANDED,
            provider_name="Example Orchard",
            owner=None,
            definition={
                **food_definition(calories="95", confidence="0.990"),
                "provenance": FoodItemVersion.Provenance.OFFICIAL,
                "sources": [
                    {
                        "title": "Official apple data",
                        "provider": "Example source",
                        "url": "https://example.com/apple",
                    }
                ],
            },
            created_by=self.owner,
        )
        self.personal_food = create_food_item(
            name="Owner smoothie",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.owner,
            definition=food_definition(calories="210", confidence=None),
            created_by=self.owner,
        )
        self.other_food = create_food_item(
            name="Other private food",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.other_user,
            definition=food_definition(calories="300", confidence=None),
            created_by=self.other_user,
        )

    def personal_food_payload(self, **overrides):
        payload = {
            "name": "Personal toast",
            "origin_type": FoodItem.OriginType.BRANDED,
            "provider_name": "Example Bakery",
            "definition": {
                "serving_quantity": "1",
                "serving_unit": FoodItemVersion.ServingUnit.ITEM,
                "serving_label": "one slice",
                "provenance": FoodItemVersion.Provenance.USER_ENTERED,
                "confidence_score": None,
                "nutrients": {"calories": "80", "fiber": "0"},
                "sources": [],
                "components": [],
            },
        }
        payload.update(overrides)
        return payload


class CanonicalIdentityFixtures:
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
