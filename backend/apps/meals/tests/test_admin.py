"""Meal admin summaries and immutable logged-food inspection."""

from datetime import date
from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from apps.foods.models import FoodItem, FoodItemVersion
from apps.foods.services import (
    create_food_item,
)

from ..admin import MealEntryAdmin, MealItemAdmin, MealItemInline
from ..models import MealEntry, MealItem
from .helpers import User, definition


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
