from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    FoodComponent,
    FoodItem,
    FoodItemVersion,
    SourceReference,
)


def admin_change_link(obj, label=None):
    """Return a consistent link to another admin record."""
    if obj is None:
        return "—"
    url = reverse(
        f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
        args=(obj.pk,),
    )
    return format_html('<a href="{}">{}</a>', url, label or str(obj))


def display_number(value):
    return format(value.normalize(), "f")


class ArchiveStatusFilter(admin.SimpleListFilter):
    title = "status"
    parameter_name = "archive_status"

    def lookups(self, request, model_admin):
        return (("active", "Active"), ("archived", "Archived"))

    def queryset(self, request, queryset):
        if self.value() == "active":
            return queryset.filter(archived_at__isnull=True)
        if self.value() == "archived":
            return queryset.filter(archived_at__isnull=False)
        return queryset


class SourceReferenceInline(admin.TabularInline):
    model = SourceReference
    extra = 0
    fields = ("title", "provider", "source_link", "accessed_on")
    readonly_fields = fields
    verbose_name = "nutrition source"
    verbose_name_plural = "Nutrition sources"

    @admin.display(description="Source")
    def source_link(self, obj):
        if not obj.url:
            return "—"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Open source ↗</a>',
            obj.url,
        )

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
    fields = ("order", "child_version_link", "servings")
    readonly_fields = fields
    verbose_name = "component"
    verbose_name_plural = "Components"

    @admin.display(description="Food version")
    def child_version_link(self, obj):
        return admin_change_link(obj.child_version)

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
        "provider_name",
        "scope",
        "origin_type",
        "current_version_summary",
        "version_count",
        "meal_log_count",
        "is_active",
    )
    list_filter = (ArchiveStatusFilter, "scope", "origin_type")
    search_fields = ("name", "provider_name", "owner__username", "owner__email")
    autocomplete_fields = ("owner",)
    list_select_related = ("owner", "current_version")
    list_per_page = 50
    save_on_top = True
    fieldsets = (
        ("Food identity", {"fields": ("name", "provider_name", "origin_type")}),
        (
            "Ownership and visibility",
            {"fields": ("scope", "owner", "archived_at")},
        ),
        ("Current nutrition definition", {"fields": ("current_version_link",)}),
        (
            "Record history",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )
    readonly_fields = (
        "current_version",
        "current_version_link",
        "created_at",
        "updated_at",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("owner", "current_version")
            .annotate(
                _admin_version_count=Count("versions", distinct=True),
                _admin_meal_log_count=Count("versions__meal_items", distinct=True),
            )
        )

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if obj is not None:
            fields.extend(("scope", "owner"))
        return fields

    @admin.display(description="Current version")
    def current_version_link(self, obj):
        if obj is None or obj.pk is None:
            return "Available after the food is created."
        return admin_change_link(obj.current_version)

    @admin.display(
        description="Current nutrition", ordering="current_version__version_number"
    )
    def current_version_summary(self, obj):
        version = obj.current_version
        if version is None:
            return "—"
        serving = version.serving_label or (
            f"{display_number(version.serving_quantity)} "
            f"{version.get_serving_unit_display()}"
        )
        calories = (
            f"{display_number(version.calories)} kcal"
            if version.calories is not None
            else "unknown kcal"
        )
        label = f"v{version.version_number} · {serving} · {calories}"
        return admin_change_link(version, label)

    @admin.display(description="Versions", ordering="_admin_version_count")
    def version_count(self, obj):
        return obj._admin_version_count

    @admin.display(description="Meal logs", ordering="_admin_meal_log_count")
    def meal_log_count(self, obj):
        return obj._admin_meal_log_count

    @admin.display(boolean=True, description="Active", ordering="archived_at")
    def is_active(self, obj):
        return obj.archived_at is None


@admin.register(FoodItemVersion)
class FoodItemVersionAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = (
        "food_item_link",
        "version_number",
        "is_current",
        "serving_summary",
        "calories_display",
        "macro_summary",
        "provenance",
        "source_count",
        "component_count",
        "created_at",
    )
    list_display_links = ("version_number",)
    list_filter = ("provenance", "serving_unit", "created_at")
    search_fields = (
        "food_item__name",
        "food_item__provider_name",
        "created_by__username",
        "created_by__email",
    )
    date_hierarchy = "created_at"
    list_select_related = ("food_item", "created_by")
    list_per_page = 50
    readonly_fields = (
        "food_item_link",
        "version_number",
        "serving_quantity",
        "serving_unit",
        "serving_label",
        "provenance",
        "confidence_score",
        "calories",
        "protein",
        "carbohydrates",
        "fat",
        "fiber",
        "sugar",
        "sodium",
        "cholesterol",
        "created_by",
        "created_at",
    )
    fieldsets = (
        ("Food version", {"fields": ("food_item_link", "version_number")}),
        (
            "Serving",
            {"fields": ("serving_quantity", "serving_unit", "serving_label")},
        ),
        (
            "Nutrition per serving",
            {
                "fields": (
                    ("calories", "protein"),
                    ("carbohydrates", "fat"),
                    ("fiber", "sugar"),
                    ("sodium", "cholesterol"),
                )
            },
        ),
        ("Data quality", {"fields": ("provenance", "confidence_score")}),
        (
            "Record history",
            {
                "classes": ("collapse",),
                "fields": ("created_by", "created_at"),
            },
        ),
    )
    inlines = (SourceReferenceInline, FoodComponentInline)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("food_item", "created_by")
            .annotate(
                _admin_source_count=Count("sources", distinct=True),
                _admin_component_count=Count("components", distinct=True),
            )
        )

    @admin.display(description="Food", ordering="food_item__name")
    def food_item_link(self, obj):
        return admin_change_link(obj.food_item)

    @admin.display(boolean=True, description="Current")
    def is_current(self, obj):
        return obj.food_item.current_version_id == obj.pk

    @admin.display(description="Serving", ordering="serving_quantity")
    def serving_summary(self, obj):
        if obj.serving_label:
            return obj.serving_label
        return (
            f"{display_number(obj.serving_quantity)} {obj.get_serving_unit_display()}"
        )

    @admin.display(description="Calories", ordering="calories", empty_value="—")
    def calories_display(self, obj):
        return (
            f"{display_number(obj.calories)} kcal" if obj.calories is not None else None
        )

    @admin.display(description="Protein / carbs / fat")
    def macro_summary(self, obj):
        values = (obj.protein, obj.carbohydrates, obj.fat)
        return " / ".join(
            "—" if value is None else f"{display_number(value)}g" for value in values
        )

    @admin.display(description="Sources", ordering="_admin_source_count")
    def source_count(self, obj):
        return obj._admin_source_count

    @admin.display(description="Components", ordering="_admin_component_count")
    def component_count(self, obj):
        return obj._admin_component_count


@admin.register(FoodComponent)
class FoodComponentAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = (
        "parent_version_link",
        "child_version_link",
        "servings",
        "order",
    )
    list_display_links = ("servings",)
    search_fields = (
        "parent_version__food_item__name",
        "child_version__food_item__name",
    )
    list_select_related = (
        "parent_version__food_item",
        "child_version__food_item",
    )
    readonly_fields = (
        "parent_version_link",
        "child_version_link",
        "servings",
        "order",
    )
    fields = readonly_fields

    @admin.display(description="Composite food")
    def parent_version_link(self, obj):
        return admin_change_link(obj.parent_version)

    @admin.display(description="Component food")
    def child_version_link(self, obj):
        return admin_change_link(obj.child_version)


@admin.register(SourceReference)
class SourceReferenceAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = (
        "title",
        "food_version_link",
        "provider",
        "source_link",
        "accessed_on",
    )
    list_display_links = ("title",)
    list_filter = ("provider", "accessed_on")
    search_fields = (
        "title",
        "provider",
        "url",
        "food_version__food_item__name",
        "food_version__food_item__provider_name",
    )
    date_hierarchy = "accessed_on"
    list_select_related = ("food_version__food_item",)
    readonly_fields = (
        "food_version_link",
        "title",
        "provider",
        "source_link",
        "accessed_on",
    )
    fields = readonly_fields

    @admin.display(description="Food version")
    def food_version_link(self, obj):
        return admin_change_link(obj.food_version)

    @admin.display(description="Source")
    def source_link(self, obj):
        if not obj.url:
            return "—"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Open source ↗</a>',
            obj.url,
        )
