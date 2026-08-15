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
    readonly_fields = ("nutrient", "amount")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class SourceReferenceInline(admin.TabularInline):
    model = SourceReference
    extra = 0
    readonly_fields = ("title", "provider", "url", "accessed_on")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class FoodComponentInline(admin.TabularInline):
    model = FoodComponent
    fk_name = "parent_version"
    extra = 0
    readonly_fields = ("child_version", "servings", "order")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ImmutableAdminMixin:
    """Expose versioned catalog records without mutable admin forms."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
    autocomplete_fields = ("owner",)

    def get_readonly_fields(self, request, obj=None):
        fields = ["current_version"]
        if obj is not None:
            fields.extend(("scope", "owner"))
        return fields


@admin.register(FoodItemVersion)
class FoodItemVersionAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = (
        "food_item",
        "version_number",
        "provenance",
        "confidence_score",
        "created_at",
    )
    list_filter = ("provenance", "serving_unit")
    search_fields = ("food_item__name", "food_item__provider_name")
    readonly_fields = (
        "food_item",
        "version_number",
        "serving_quantity",
        "serving_unit",
        "serving_label",
        "provenance",
        "confidence_score",
        "created_by",
        "created_at",
    )
    inlines = (NutrientAmountInline, SourceReferenceInline, FoodComponentInline)


@admin.register(NutrientDefinition)
class NutrientDefinitionAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = ("name", "key", "unit", "is_core", "display_order")
    list_filter = ("unit", "is_core")
    search_fields = ("name", "key")
    ordering = ("display_order", "name")
    readonly_fields = ("key", "name", "unit", "is_core", "display_order")


@admin.register(FoodComponent)
class FoodComponentAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = ("parent_version", "child_version", "servings", "order")
    readonly_fields = ("parent_version", "child_version", "servings", "order")


@admin.register(NutrientAmount)
class NutrientAmountAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = ("food_version", "nutrient", "amount")
    readonly_fields = ("food_version", "nutrient", "amount")


@admin.register(SourceReference)
class SourceReferenceAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = ("food_version", "title", "provider", "accessed_on")
    readonly_fields = (
        "food_version",
        "title",
        "provider",
        "url",
        "accessed_on",
    )
