from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from estimates.provider import EstimationProviderError
from foods.models import FoodItem, FoodItemVersion
from foods.services import create_food_item, create_food_version

from .admin import MealEntryAdmin, MealItemAdmin, MealItemInline
from .models import MealEntry, MealItem

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

    def test_create_copies_food_and_nutrient_values(self):
        self.apple.current_version.serving_weight_grams = Decimal("182")
        self.apple.current_version.save(update_fields=["serving_weight_grams"])
        response = self.create_meal()

        self.assertEqual(response.data["name"], "Breakfast")
        self.assertIsNone(response.data["confidence_score"])
        self.assertEqual(len(response.data["items"]), 2)
        apple = response.data["items"][0]
        self.assertEqual(apple["food_name"], "Apple")
        self.assertEqual(apple["food_version_id"], self.apple.current_version_id)
        self.assertEqual(apple["provenance"], "user_entered")
        self.assertIsNone(apple["confidence_score"])
        self.assertEqual(
            {option["key"] for option in apple["portion_options"]},
            {"base", "g", "oz"},
        )
        toast = response.data["items"][1]
        self.assertEqual(toast["provenance"], "official")
        self.assertEqual(toast["confidence_score"], "0.990")
        nutrients = {item["key"]: item["amount"] for item in apple["nutrients"]}
        self.assertEqual(nutrients["calories"], "190.0000")
        self.assertEqual(nutrients["protein"], "1.0000")

    @patch("meals.services.get_estimation_provider")
    def test_create_generates_a_name_when_it_is_left_blank(self, get_provider):
        provider = Mock()
        provider.generate_name.return_value = "Example Bakery Toast & Apple"
        get_provider.return_value = provider

        response = self.create_meal(name="")

        self.assertEqual(response.data["name"], "Example Bakery Toast & Apple")
        provider.generate_name.assert_called_once_with(
            [
                {"name": "Apple", "provider_name": "", "servings": "2.0000"},
                {
                    "name": "Toast",
                    "provider_name": "Example Bakery",
                    "servings": "1.0000",
                },
            ]
        )

    @patch("meals.services.get_estimation_provider")
    def test_create_uses_numbered_names_when_generation_fails(self, get_provider):
        get_provider.side_effect = EstimationProviderError("Provider unavailable")

        first = self.create_meal(name="")
        second = self.create_meal(name="")

        self.assertEqual(first.data["name"], "Meal-00")
        self.assertEqual(second.data["name"], "Meal-01")

    def test_saved_meal_item_does_not_change_after_catalog_update(self):
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

    def test_archived_food_meal_item_can_reuse_its_saved_version(self):
        created = self.create_meal(
            item_inputs=[{"food_item": self.apple.id, "servings": "1", "order": 0}]
        )
        saved_version = created.data["items"][0]["food_version_id"]
        archive_response = self.client.delete(f"/api/foods/{self.apple.id}/")
        self.assertEqual(archive_response.status_code, status.HTTP_204_NO_CONTENT)

        edit_response = self.client.patch(
            f"/api/meals/{created.data['id']}/",
            {
                "item_inputs": [
                    {
                        "food_item": self.apple.id,
                        "food_version": saved_version,
                        "servings": "2",
                        "order": 0,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(edit_response.status_code, status.HTTP_200_OK)
        edited_item = edit_response.data["items"][0]
        self.assertEqual(edited_item["food_version_id"], saved_version)
        self.assertEqual(edited_item["servings"], "2.0000")
        self.assertEqual(edited_item["nutrients"][0]["amount"], "190.0000")

        new_meal_response = self.client.post(
            "/api/meals/",
            self.payload(
                item_inputs=[{"food_item": self.apple.id, "servings": "1", "order": 0}]
            ),
            format="json",
        )
        self.assertEqual(new_meal_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_composite_component_tree_is_copied_into_meal(self):
        composite = create_food_item(
            name="Apple toast",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.owner,
            definition=definition(
                calories="0",
                protein="0",
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
        nutrients = {
            item["key"]: item["amount"]
            for item in response.data["items"][0]["nutrients"]
        }
        self.assertEqual(nutrients["calories"], "270.0000")
        self.assertEqual(nutrients["protein"], "4.0000")
        components = {
            item["food_name"]: {
                nutrient["key"]: nutrient["amount"] for nutrient in item["nutrients"]
            }
            for item in response.data["items"][0]["component_snapshot"]
        }
        self.assertEqual(components["Apple"]["calories"], "95.0000")
        self.assertEqual(components["Toast"]["calories"], "80.0000")

    def test_legacy_component_snapshot_is_returned_with_nutrients(self):
        composite = create_food_item(
            name="Apple toast",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.owner,
            definition=definition(
                components=[
                    {"food_item": self.apple, "servings": Decimal("1"), "order": 0},
                    {"food_item": self.toast, "servings": Decimal("1"), "order": 1},
                ],
            ),
            created_by=self.owner,
        )
        created = self.create_meal(
            item_inputs=[{"food_item": composite.id, "servings": "1", "order": 0}]
        )
        saved_item = MealItem.objects.get(pk=created.data["items"][0]["id"])
        legacy_snapshot = saved_item.component_snapshot
        for component in legacy_snapshot:
            component.pop("nutrients", None)
        saved_item.component_snapshot = legacy_snapshot
        saved_item.save(update_fields=["component_snapshot"])

        response = self.client.get(f"/api/meals/{created.data['id']}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_components = response.data["items"][0]["component_snapshot"]
        self.assertTrue(returned_components)
        self.assertTrue(
            all(component["nutrients"] for component in returned_components)
        )

    def test_composite_reuses_descendant_across_independent_branches(self):
        branch_definition = {
            **definition(),
            "nutrients": {},
            "components": [
                {"food_item": self.apple, "servings": Decimal("1"), "order": 0}
            ],
        }
        first_branch = create_food_item(
            name="First apple branch",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.owner,
            definition=branch_definition,
            created_by=self.owner,
        )
        second_branch = create_food_item(
            name="Second apple branch",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.owner,
            definition={
                **branch_definition,
                "components": [
                    {
                        "food_item": self.apple,
                        "servings": Decimal("2"),
                        "order": 0,
                    }
                ],
            },
            created_by=self.owner,
        )
        composite = create_food_item(
            name="Shared descendant composite",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.owner,
            definition={
                **definition(),
                "nutrients": {},
                "components": [
                    {"food_item": first_branch, "servings": Decimal("1"), "order": 0},
                    {
                        "food_item": second_branch,
                        "servings": Decimal("1"),
                        "order": 1,
                    },
                ],
            },
            created_by=self.owner,
        )

        response = self.create_meal(
            item_inputs=[{"food_item": composite.id, "servings": "1", "order": 0}]
        )

        item = response.data["items"][0]
        nutrients = {value["key"]: value["amount"] for value in item["nutrients"]}
        nested_names = [
            nested["food_name"]
            for branch in item["component_snapshot"]
            for nested in branch["components"]
        ]
        self.assertEqual(nutrients["calories"], "285.0000")
        self.assertEqual(nutrients["protein"], "1.5000")
        self.assertEqual(nested_names, ["Apple", "Apple"])

    def test_daily_totals_sum_saved_meal_items(self):
        self.create_meal(name="Breakfast")
        self.create_meal(
            name="Snack",
            item_inputs=[{"food_item": self.apple.id, "servings": "0.5", "order": 0}],
        )
        known_sugar = MealItem.objects.order_by("id").first()
        known_sugar.sugar = Decimal("15")
        known_sugar.save(update_fields=["sugar"])

        response = self.client.get("/api/meals/daily/?date=2026-08-16")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["meals"]), 2)
        totals = {item["key"]: item["amount"] for item in response.data["totals"]}
        self.assertEqual(totals["calories"], Decimal("317.5000"))
        self.assertEqual(totals["protein"], Decimal("4.2500"))
        self.assertEqual(totals["sugar"], Decimal("15.0000"))
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

    def test_partial_edit_preserves_meal_items_when_they_are_omitted(self):
        created = self.create_meal()
        original_items = created.data["items"]

        response = self.client.patch(
            f"/api/meals/{created.data['id']}/",
            {"name": "Renamed breakfast", "notes": "Metadata only"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["name"], "Renamed breakfast")
        self.assertEqual(response.data["notes"], "Metadata only")
        self.assertEqual(response.data["items"], original_items)
        self.assertEqual(
            MealItem.objects.filter(meal_entry_id=created.data["id"]).count(), 2
        )

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

    def test_collection_endpoint_rejects_an_invalid_date(self):
        self.create_meal()

        for requested_date in ("not-a-date", ""):
            with self.subTest(requested_date=requested_date):
                response = self.client.get("/api/meals/", {"date": requested_date})

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(
                    response.data["date"],
                    "Supply a valid date in YYYY-MM-DD format.",
                )


class MealAdminTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.request = RequestFactory().get("/admin/")
        self.owner = User.objects.create_superuser(
            username="admin-owner",
            email="admin@example.com",
            password="admin-password",
        )
        self.shake = create_food_item(
            name="Chocolate Shake",
            scope=FoodItem.Scope.SHARED,
            origin_type=FoodItem.OriginType.RESTAURANT,
            provider_name="In-N-Out",
            owner=None,
            definition={
                **definition(calories="610", protein="16"),
                "provenance": FoodItemVersion.Provenance.OFFICIAL,
                "confidence_score": Decimal("0.990"),
                "nutrients": {
                    "calories": Decimal("610"),
                    "protein": Decimal("16"),
                    "carbohydrates": Decimal("74"),
                    "fat": Decimal("30"),
                },
            },
            created_by=self.owner,
        )
        self.meal = MealEntry.objects.create(
            owner=self.owner,
            entry_date=date(2026, 8, 10),
            name="Monday snack",
            notes="Chocolate shake from In-N-Out",
        )
        self.meal_item = MealItem.objects.create(
            meal_entry=self.meal,
            food_version=self.shake.current_version,
            servings=Decimal("1"),
            order=0,
            food_name="Chocolate Shake",
            provider_name="In-N-Out",
            serving_quantity=Decimal("15"),
            serving_unit=FoodItemVersion.ServingUnit.FLUID_OUNCE,
            serving_label="15 fl oz shake",
            calories=Decimal("610"),
            protein=Decimal("16"),
            carbohydrates=Decimal("74"),
            fat=Decimal("30"),
        )

    def test_meal_list_summarizes_items_and_nutrition(self):
        meal_admin = MealEntryAdmin(MealEntry, self.site)

        meal = meal_admin.get_queryset(self.request).get(pk=self.meal.pk)

        self.assertEqual(meal_admin.item_count(meal), 1)
        self.assertEqual(meal_admin.calorie_total(meal), "610 kcal")
        self.assertEqual(meal_admin.macro_totals(meal), "16g / 74g / 30g")
        self.assertIn(MealItemInline, meal_admin.inlines)

    def test_meal_item_admin_remains_read_only_and_links_related_records(self):
        meal_item_admin = MealItemAdmin(MealItem, self.site)

        self.assertFalse(meal_item_admin.has_add_permission(self.request))
        self.assertFalse(meal_item_admin.has_change_permission(self.request))
        self.assertFalse(meal_item_admin.has_delete_permission(self.request))
        self.assertIn(
            f"/admin/meals/mealentry/{self.meal.pk}/change/",
            str(meal_item_admin.meal_entry_link(self.meal_item)),
        )
        self.assertIn(
            f"/admin/foods/fooditemversion/{self.shake.current_version_id}/change/",
            str(meal_item_admin.food_version_link(self.meal_item)),
        )

    def test_meal_change_page_shows_logged_food_inline(self):
        self.client.force_login(self.owner)

        response = self.client.get(f"/admin/meals/mealentry/{self.meal.pk}/change/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Meal items")
        self.assertContains(response, "Chocolate Shake")
        self.assertContains(response, "610 kcal")
