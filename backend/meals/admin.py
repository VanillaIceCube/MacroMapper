from django.contrib import admin

from .models import MealEntry, MealItemSnapshot


@admin.register(MealEntry)
class MealEntryAdmin(admin.ModelAdmin):
    list_display = ("name", "entry_date", "owner", "updated_at")
    list_filter = ("entry_date",)
    search_fields = ("name", "owner__email")


@admin.register(MealItemSnapshot)
class MealItemSnapshotAdmin(admin.ModelAdmin):
    list_display = ("food_name", "meal_entry", "servings", "order")
    readonly_fields = (
        "meal_entry",
        "food_version",
        "servings",
        "order",
        "food_name",
        "provider_name",
        "serving_quantity",
        "serving_unit",
        "serving_label",
        "component_snapshot",
        "calories",
        "protein",
        "carbohydrates",
        "fat",
        "fiber",
        "sugar",
        "sodium",
        "cholesterol",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
