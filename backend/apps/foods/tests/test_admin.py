"""Food admin privacy, immutable versions and display fields."""

from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from ..admin import (
    FoodComponentAdmin,
    FoodComponentInline,
    FoodItemAdmin,
    FoodItemVersionAdmin,
    SourceReferenceAdmin,
    SourceReferenceInline,
)
from ..models import (
    FoodComponent,
    FoodItem,
    FoodItemVersion,
    SourceReference,
)
from ..services import (
    create_food_item,
)
from .helpers import User, food_definition


class FoodAdminTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.request = RequestFactory().get("/admin/")

    def test_food_privacy_fields_cannot_change_after_creation_in_admin(self):
        food_admin = FoodItemAdmin(FoodItem, self.site)
        existing_food = FoodItem(
            name="Private food",
            scope=FoodItem.Scope.PERSONAL,
            owner_id=1,
        )

        add_readonly_fields = food_admin.get_readonly_fields(self.request)
        change_readonly_fields = food_admin.get_readonly_fields(
            self.request,
            existing_food,
        )

        self.assertIn("current_version", add_readonly_fields)
        self.assertNotIn("scope", add_readonly_fields)
        self.assertNotIn("owner", add_readonly_fields)
        self.assertIn("current_version", change_readonly_fields)
        self.assertIn("scope", change_readonly_fields)
        self.assertIn("owner", change_readonly_fields)
        self.assertNotIn(
            "current_version", food_admin.get_autocomplete_fields(self.request)
        )

    def test_version_and_related_records_are_immutable_in_admin(self):
        admin_classes = (
            (FoodItemVersionAdmin, FoodItemVersion),
            (FoodComponentAdmin, FoodComponent),
            (SourceReferenceAdmin, SourceReference),
        )

        for admin_class, model in admin_classes:
            with self.subTest(model=model.__name__):
                model_admin = admin_class(model, self.site)
                self.assertFalse(model_admin.has_add_permission(self.request))
                self.assertFalse(model_admin.has_change_permission(self.request))
                self.assertFalse(model_admin.has_delete_permission(self.request))

    def test_version_related_inlines_are_immutable_in_admin(self):
        inline_classes = (
            SourceReferenceInline,
            FoodComponentInline,
        )

        for inline_class in inline_classes:
            with self.subTest(inline=inline_class.__name__):
                inline = inline_class(FoodItemVersion, self.site)
                self.assertFalse(inline.has_add_permission(self.request))
                self.assertFalse(inline.has_change_permission(self.request))
                self.assertFalse(inline.has_delete_permission(self.request))

    def test_food_lists_show_current_nutrition_and_related_counts(self):
        owner = User.objects.create_user(
            username="catalog-owner",
            email="catalog@example.com",
            password="owner-password",
        )
        food = create_food_item(
            name="Chocolate Shake",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.RESTAURANT,
            provider_name="In-N-Out",
            owner=owner,
            definition={
                **food_definition(calories="610", confidence=None),
                "serving_quantity": Decimal("15"),
                "serving_unit": FoodItemVersion.ServingUnit.FLUID_OUNCE,
                "serving_label": "15 fl oz shake",
            },
            created_by=owner,
        )
        food_admin = FoodItemAdmin(FoodItem, self.site)

        listed_food = food_admin.get_queryset(self.request).get(pk=food.pk)
        summary = str(food_admin.current_version_summary(listed_food))

        self.assertIn("15 fl oz shake", summary)
        self.assertIn("610 kcal", summary)
        self.assertIn(
            f"/admin/foods/fooditemversion/{food.current_version_id}/change/",
            summary,
        )
        self.assertEqual(food_admin.version_count(listed_food), 1)
        self.assertEqual(food_admin.meal_log_count(listed_food), 0)

    def test_food_add_page_renders_grouped_fields(self):
        admin_user = User.objects.create_superuser(
            username="catalog-admin",
            email="catalog-admin@example.com",
            password="admin-password",
        )
        self.client.force_login(admin_user)

        response = self.client.get("/admin/foods/fooditem/add/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Food identity")
        self.assertContains(response, "Ownership and visibility")
        self.assertContains(response, "Available after the food is created.")
