from django.contrib import admin

from .models import (
    FoodComponent,
    FoodItem,
    FoodItemVersion,
    NutrientAmount,
    NutrientDefinition,
    SourceReference,
)


class NutrientAmountInline(admin.TabularInline):
    model = NutrientAmount
    extra = 0


class SourceReferenceInline(admin.TabularInline):
    model = SourceReference
    extra = 0


class FoodComponentInline(admin.TabularInline):
    model = FoodComponent
    fk_name = "parent_version"
    extra = 0


@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "scope",
        "origin_type",
        "provider_name",
        "owner",
        "current_version",
        "archived_at",
    )
    list_filter = ("scope", "origin_type", "archived_at")
    search_fields = ("name", "provider_name", "owner__email")
    autocomplete_fields = ("owner", "current_version")


@admin.register(FoodItemVersion)
class FoodItemVersionAdmin(admin.ModelAdmin):
    list_display = (
        "food_item",
        "version_number",
        "provenance",
        "confidence_score",
        "created_at",
    )
    list_filter = ("provenance", "serving_unit")
    search_fields = ("food_item__name", "food_item__provider_name")
    autocomplete_fields = ("food_item", "created_by")
    inlines = (NutrientAmountInline, SourceReferenceInline, FoodComponentInline)


@admin.register(NutrientDefinition)
class NutrientDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "unit", "is_core", "display_order")
    list_filter = ("unit", "is_core")
    search_fields = ("name", "key")
    ordering = ("display_order", "name")


admin.site.register(FoodComponent)
admin.site.register(NutrientAmount)
admin.site.register(SourceReference)
