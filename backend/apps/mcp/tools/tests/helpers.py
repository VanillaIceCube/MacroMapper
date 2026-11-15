"""Synthetic local OAuth, catalog and meal fixtures for app-owned MCP tests."""

from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken as JWTToken

from apps.estimates.services import _catalog_food
from apps.foods.nutrients import NUTRIENT_FIELDS
from apps.foods.services import create_food_item
from apps.meals.models import MealEntry

from .. import operations, services
from ..permissions import ESTIMATE, READ, WRITE


def definition(calories="100"):
    return {
        "serving_quantity": "1",
        "serving_unit": "item",
        "serving_label": "one item",
        "provenance": "user_entered",
        "confidence_score": "0.900",
        "nutrients": {"calories": calories},
        "sources": [],
        "components": [],
    }


class MCPToolFixtures:
    def setUp(self):
        from oauth2_provider.models import AccessToken, Application

        self.user = get_user_model().objects.create_user(
            "mcp-owner", email="mcp-owner@example.test"
        )
        self.other = get_user_model().objects.create_user(
            "mcp-other", email="mcp-other@example.test"
        )
        self.application = Application.objects.create(
            name="MCP fixture",
            client_id="mcp-fixture",
            client_type="public",
            authorization_grant_type="authorization-code",
            redirect_uris="https://client.example/callback",
        )
        self.token = AccessToken.objects.create(
            user=self.user,
            application=self.application,
            token="fixture-local-token",
            scope=" ".join([READ, WRITE, ESTIMATE]),
            expires=timezone.now() + timedelta(hours=1),
            resource=[settings.MCP_RESOURCE_URL],
        )
        self.raw = "fixture-local-token"
        self.food = create_food_item(
            name="Apple",
            scope="shared",
            origin_type="generic",
            provider_name="",
            owner=None,
            definition=definition(),
            created_by=None,
        )

    def meal_payload(self):
        return {
            "entry_date": "2026-10-30",
            "name": "Lunch",
            "notes": "exact requested change",
            "item_inputs": [{"food_item": self.food.pk, "servings": "1", "order": 0}],
        }

    def request(self, action="meal.create", target=None, payload=None, request_id=None):
        return {
            "request_id": request_id or str(uuid4()),
            "action": action,
            "target_id": target,
            "payload": payload if payload is not None else self.meal_payload(),
            "authorized_paid": operations.OPERATIONS[action].paid,
        }

    def arguments(self, request):
        return tuple(
            request[key]
            for key in (
                "request_id",
                "action",
                "target_id",
                "payload",
                "authorized_paid",
            )
        )

    def prepare(self, request, raw=None):
        return services.prepare_change(raw or self.raw, *self.arguments(request))

    def approval_client(self, user=None):
        return Client(
            HTTP_AUTHORIZATION=f"Bearer {JWTToken.for_user(user or self.user)}"
        )

    def approve(self, reference, decision="allow"):
        client = self.approval_client()
        preview = client.get("/auth/mcp/action-approval/", {"approval_id": reference})
        self.assertEqual(preview.status_code, 200, preview.content)
        decided = client.post(
            "/auth/mcp/action-approval/",
            {"ticket": preview.json()["ticket"], "decision": decision},
        )
        self.assertEqual(decided.status_code, 200, decided.content)
        return decided.json()

    def prepare_approved(self, request):
        prepared = self.prepare(request)
        reference = prepared["result"]["data"]["confirmation_id"]
        self.approve(reference)
        return (request["request_id"], reference, request["authorized_paid"])

    def execute(self, request, raw=None):
        prepared = self.prepare(request, raw=raw)
        if prepared["status"] not in {"prepared", "approved"}:
            return prepared
        reference = prepared["result"]["data"]["confirmation_id"]
        self.approve(reference)
        return services.confirm_change(
            raw or self.raw,
            request["request_id"],
            reference,
            request["authorized_paid"],
        )

    def make_meal(self):
        return MealEntry.objects.get(
            pk=self.execute(self.request())["result"]["data"]["id"]
        )


class MealToolFixtures(MCPToolFixtures):
    def composite(self):
        children = []
        for index in range(6):
            data = definition()
            data["nutrients"] = dict.fromkeys(NUTRIENT_FIELDS, "1")
            child = create_food_item(
                name=f"Synthetic ingredient {index}",
                scope="shared",
                origin_type="generic",
                provider_name="",
                owner=None,
                definition=data,
                created_by=None,
            )
            children.append({"food_item": child, "servings": "1", "order": index})
        data = definition()
        data["components"] = children
        return create_food_item(
            name="Synthetic composite",
            scope="shared",
            origin_type="generic",
            provider_name="",
            owner=None,
            definition=data,
            created_by=None,
        )

    def draft_payload(self, foods):
        return {
            "entry_date": "2026-10-30",
            "name": "Synthetic draft",
            "notes": "",
            "items": [
                _catalog_food(food.current_version, key=f"fixture-{index}")
                for index, food in enumerate(foods)
            ],
        }
