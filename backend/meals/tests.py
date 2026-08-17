from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from foods.models import FoodItem, FoodItemVersion
from foods.services import create_food_item, create_food_version

from .models import MealEntry

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


class MealEntryApiTests(APITestCase):
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

    def test_meal_endpoints_require_authentication(self):
        list_response = self.client.get("/api/meals/")
        create_response = self.client.post("/api/meals/", self.payload(), format="json")

        self.assertEqual(list_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(create_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_copies_food_and_nutrient_snapshots(self):
        response = self.create_meal()

        self.assertEqual(response.data["name"], "Breakfast")
        self.assertEqual(len(response.data["items"]), 2)
        apple = response.data["items"][0]
        self.assertEqual(apple["food_name"], "Apple")
        self.assertEqual(apple["food_version_id"], self.apple.current_version_id)
        nutrients = {item["key"]: item["amount"] for item in apple["nutrients"]}
        self.assertEqual(nutrients["calories"], "190.0000")
        self.assertEqual(nutrients["protein"], "1.0000")

    def test_saved_snapshot_does_not_change_after_catalog_update(self):
        response = self.create_meal(
            item_inputs=[{"food_item": self.apple.id, "servings": "1", "order": 0}]
        )
        saved_version = response.data["items"][0]["food_version_id"]

        create_food_version(
            food_item=self.apple,
            definition=definition(calories="120", protein="1"),
            created_by=self.owner,
        )
        detail = self.client.get(f"/api/meals/{response.data['id']}/")

        item = detail.data["items"][0]
        self.assertEqual(item["food_version_id"], saved_version)
        self.assertEqual(item["nutrients"][0]["amount"], "95.0000")

        edit_response = self.client.patch(
            f"/api/meals/{response.data['id']}/",
            self.payload(
                item_inputs=[
                    {
                        "food_item": self.apple.id,
                        "food_version": saved_version,
                        "servings": "2",
                        "order": 0,
                    }
                ]
            ),
            format="json",
        )
        edited_item = edit_response.data["items"][0]
        self.assertEqual(edited_item["food_version_id"], saved_version)
        self.assertEqual(edited_item["nutrients"][0]["amount"], "190.0000")

    def test_composite_component_tree_is_copied_into_meal(self):
        composite = create_food_item(
            name="Apple toast",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.owner,
            definition=definition(
                calories="270",
                protein="4",
                components=[
                    {"food_item": self.apple, "servings": Decimal("2"), "order": 0},
                    {"food_item": self.toast, "servings": Decimal("1"), "order": 1},
                ],
            ),
            created_by=self.owner,
        )

        response = self.create_meal(
            item_inputs=[{"food_item": composite.id, "servings": "1", "order": 0}]
        )

        component_names = {
            item["food_name"]
            for item in response.data["items"][0]["component_snapshot"]
        }
        self.assertEqual(component_names, {"Apple", "Toast"})

    def test_daily_totals_sum_saved_meal_snapshots(self):
        self.create_meal(name="Breakfast")
        self.create_meal(
            name="Snack",
            item_inputs=[{"food_item": self.apple.id, "servings": "0.5", "order": 0}],
        )

        response = self.client.get("/api/meals/daily/?date=2026-08-16")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["meals"]), 2)
        totals = {item["key"]: item["amount"] for item in response.data["totals"]}
        self.assertEqual(totals["calories"], Decimal("317.5000"))
        self.assertEqual(totals["protein"], Decimal("4.2500"))
        self.assertIsNone(totals["fiber"])

    def test_edit_replaces_components_and_updates_daily_totals(self):
        created = self.create_meal()

        response = self.client.patch(
            f"/api/meals/{created.data['id']}/",
            self.payload(
                name="Updated breakfast",
                item_inputs=[{"food_item": self.toast.id, "servings": "2", "order": 0}],
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["name"], "Updated breakfast")
        self.assertEqual(len(response.data["items"]), 1)
        totals_response = self.client.get("/api/meals/daily/?date=2026-08-16")
        totals = {
            item["key"]: item["amount"] for item in totals_response.data["totals"]
        }
        self.assertEqual(totals["calories"], Decimal("160.0000"))

    def test_users_cannot_read_edit_or_delete_another_users_meal(self):
        created = self.create_meal()
        self.client.force_authenticate(user=self.other_user)
        url = f"/api/meals/{created.data['id']}/"

        retrieve_response = self.client.get(url)
        edit_response = self.client.patch(url, self.payload(), format="json")
        delete_response = self.client.delete(url)
        list_response = self.client.get("/api/meals/?date=2026-08-16")

        self.assertEqual(retrieve_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(edit_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(list_response.data, [])
        self.assertTrue(MealEntry.objects.filter(pk=created.data["id"]).exists())

    def test_meal_rejects_another_users_personal_food(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            "/api/meals/",
            self.payload(
                item_inputs=[
                    {"food_item": self.other_food.id, "servings": "1", "order": 0}
                ]
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("item_inputs", response.data)

    def test_owner_can_delete_a_meal(self):
        created = self.create_meal()

        response = self.client.delete(f"/api/meals/{created.data['id']}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(MealEntry.objects.filter(pk=created.data["id"]).exists())

    def test_daily_endpoint_validates_date(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get("/api/meals/daily/?date=not-a-date")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(date.fromisoformat("2026-08-16").year, 2026)
