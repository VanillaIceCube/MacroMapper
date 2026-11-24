"""Personal food mutation validation, versioning and shared-food immutability."""

from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from ..models import (
    FoodItem,
)
from .helpers import FoodApiFixtures


class FoodMutationTests(FoodApiFixtures, APITestCase):
    def test_user_can_create_a_personal_food_with_unknown_and_zero_nutrients(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            "/api/foods/",
            self.personal_food_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        created = FoodItem.objects.get(pk=response.data["id"])
        self.assertEqual(created.owner, self.owner)
        self.assertEqual(created.scope, FoodItem.Scope.PERSONAL)
        nutrient_values = {
            item["key"]: item["amount"]
            for item in response.data["current_version"]["nutrients"]
        }
        self.assertEqual(nutrient_values["fiber"], "0.0000")
        self.assertNotIn("sugar", nutrient_values)

    def test_personal_food_rejects_an_unsupported_nutrient(self):
        payload = self.personal_food_payload()
        payload["definition"]["nutrients"]["potassium"] = "120"
        self.client.force_authenticate(user=self.owner)

        response = self.client.post("/api/foods/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nutrients", response.data["definition"])

    def test_natural_servings_are_normalized_in_saved_food_and_readback(self):
        self.client.force_authenticate(user=self.owner)
        payload = self.personal_food_payload()
        payload["definition"]["natural_servings"] = [
            {"key": "small", "label": "  Small  ", "weight_grams": 40.0},
            {"key": "large", "label": " Large ", "weight_grams": " 80.500 "},
        ]
        expected = [
            {"key": "small", "label": "Small", "weight_grams": "40"},
            {"key": "large", "label": "Large", "weight_grams": "80.5"},
        ]

        created = self.client.post("/api/foods/", payload, format="json")

        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertEqual(created.data["current_version"]["natural_servings"], expected)
        food = FoodItem.objects.get(pk=created.data["id"])
        self.assertEqual(food.current_version.natural_servings, expected)
        readback = self.client.get(f"/api/foods/{food.pk}/")
        self.assertEqual(readback.status_code, status.HTTP_200_OK)
        self.assertEqual(readback.data["current_version"]["natural_servings"], expected)

    def test_natural_servings_reject_unsupported_extra_fields_without_saving(self):
        self.client.force_authenticate(user=self.owner)
        payload = self.personal_food_payload()
        payload["definition"]["natural_servings"] = [
            {
                "key": "small",
                "label": "Small",
                "weight_grams": "40",
                "unsupported": "discard me",
            }
        ]
        previous_count = FoodItem.objects.count()

        response = self.client.post("/api/foods/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("natural_servings", response.data["definition"])
        self.assertEqual(FoodItem.objects.count(), previous_count)

    def test_personal_foods_are_private_for_retrieve_update_and_delete(self):
        self.client.force_authenticate(user=self.owner)
        url = f"/api/foods/{self.other_food.id}/"

        retrieve_response = self.client.get(url)
        update_response = self.client.patch(url, {"name": "Changed"}, format="json")
        delete_response = self.client.delete(url)

        self.assertEqual(retrieve_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_component_requires_the_canonical_food_reference_field(self):
        self.client.force_authenticate(user=self.owner)
        count = FoodItem.objects.count()
        payload = self.personal_food_payload()
        payload["definition"]["components"] = [
            {
                "food_item": self.shared_food.pk,
                "food_item_id": self.shared_food.pk,
                "servings": "1",
                "order": 0,
            }
        ]

        response = self.client.post("/api/foods/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("food_item_id", response.data["definition"]["components"][0])
        self.assertEqual(FoodItem.objects.count(), count)

    def test_composite_cannot_reference_another_users_personal_food(self):
        payload = self.personal_food_payload()
        payload["definition"]["components"] = [
            {"food_item_id": self.other_food.id, "servings": "1", "order": 0}
        ]
        self.client.force_authenticate(user=self.owner)

        response = self.client.post("/api/foods/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("components", response.data["definition"])

    def test_shared_foods_are_read_only_for_normal_users(self):
        self.client.force_authenticate(user=self.owner)
        url = f"/api/foods/{self.shared_food.id}/"

        update_response = self.client.patch(url, {"name": "Changed"}, format="json")
        delete_response = self.client.delete(url)

        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_updating_a_definition_creates_a_new_version(self):
        self.client.force_authenticate(user=self.owner)
        old_version = self.personal_food.current_version
        payload = self.personal_food_payload()["definition"]
        payload["nutrients"] = {"calories": "225"}

        response = self.client.patch(
            f"/api/foods/{self.personal_food.id}/",
            {"definition": payload},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.personal_food.refresh_from_db()
        self.assertEqual(self.personal_food.current_version.version_number, 2)
        self.assertNotEqual(self.personal_food.current_version_id, old_version.id)
        self.assertEqual(
            old_version.calories,
            Decimal("210"),
        )

    def test_composite_food_keeps_the_exact_child_version(self):
        self.client.force_authenticate(user=self.owner)
        old_child_version = self.personal_food.current_version
        definition = self.personal_food_payload()["definition"]
        definition["components"] = [
            {
                "food_item_id": self.personal_food.id,
                "servings": "0.5",
                "order": 0,
            }
        ]
        parent_response = self.client.post(
            "/api/foods/",
            self.personal_food_payload(name="Composite snack", definition=definition),
            format="json",
        )
        self.assertEqual(
            parent_response.status_code,
            status.HTTP_201_CREATED,
            parent_response.data,
        )

        updated_definition = self.personal_food_payload()["definition"]
        updated_definition["nutrients"] = {"calories": "250"}
        update_response = self.client.patch(
            f"/api/foods/{self.personal_food.id}/",
            {"definition": updated_definition},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)

        parent_detail = self.client.get(f"/api/foods/{parent_response.data['id']}/")
        component = parent_detail.data["current_version"]["components"][0]
        self.assertEqual(component["food_version_id"], old_child_version.id)
        self.assertEqual(component["food_item_name"], "Owner smoothie")
        self.assertEqual(component["provenance"], old_child_version.provenance)
        self.assertEqual(
            {item["key"]: item["amount"] for item in component["nutrients"]},
            {"calories": "210.0000"},
        )
        self.assertEqual(component["components"], [])

    def test_catalog_serializes_nested_component_nutrition(self):
        self.client.force_authenticate(user=self.owner)
        child_definition = self.personal_food_payload()["definition"]
        child_definition["components"] = [
            {"food_item_id": self.personal_food.id, "servings": "0.5", "order": 0}
        ]
        child_response = self.client.post(
            "/api/foods/",
            self.personal_food_payload(
                name="Smoothie cup", definition=child_definition
            ),
            format="json",
        )
        self.assertEqual(child_response.status_code, status.HTTP_201_CREATED)

        parent_definition = self.personal_food_payload()["definition"]
        parent_definition["components"] = [
            {"food_item_id": child_response.data["id"], "servings": "1", "order": 0}
        ]
        parent_response = self.client.post(
            "/api/foods/",
            self.personal_food_payload(
                name="Breakfast combo", definition=parent_definition
            ),
            format="json",
        )
        self.assertEqual(parent_response.status_code, status.HTTP_201_CREATED)

        component = parent_response.data["current_version"]["components"][0]
        nested_component = component["components"][0]
        self.assertEqual(component["food_item_name"], "Smoothie cup")
        self.assertEqual(component["nutrients"][0]["amount"], "80.0000")
        self.assertEqual(nested_component["food_item_name"], "Owner smoothie")
        self.assertEqual(nested_component["nutrients"][0]["amount"], "210.0000")

    def test_delete_archives_an_owned_personal_food(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.delete(f"/api/foods/{self.personal_food.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.personal_food.refresh_from_db()
        self.assertIsNotNone(self.personal_food.archived_at)
        list_response = self.client.get("/api/foods/")
        self.assertNotIn(
            self.personal_food.id,
            [item["id"] for item in list_response.data],
        )
