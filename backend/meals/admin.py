import json

from django.contrib import admin
from django.db.models import Count, Sum
from django.urls import reverse
from django.utils.html import format_html

from .models import MealEntry, MealItem


def admin_change_link(obj, label=None):
    if obj is None:
        return "—"
    url = reverse(
        f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
        args=(obj.pk,),
    )
    return format_html('<a href="{}">{}</a>', url, label or str(obj))


def display_number(value):
    return format(value.normalize(), "f")


def macro_summary(obj):
    values = (obj.protein, obj.carbohydrates, obj.fat)
    return " / ".join(
        "—" if value is None else f"{display_number(value)}g" for value in values
    )


class MealItemInline(admin.TabularInline):
    model = MealItem
    extra = 0
    fields = (
        "order",
        "food_name",
        "servings_display",
        "portion",
        "calories_display",
        "macros",
        "food_version_link",
    )
    readonly_fields = fields
    show_change_link = True
    verbose_name = "meal item"
    verbose_name_plural = "Meal items"

    @admin.display(description="Portion")
    def portion(self, obj):
        if obj.serving_label:
            return obj.serving_label
        return f"{display_number(obj.serving_quantity)} {obj.serving_unit}"

    @admin.display(description="Servings")
    def servings_display(self, obj):
        return display_number(obj.servings)

    @admin.display(description="Calories")
    def calories_display(self, obj):
        return (
            f"{display_number(obj.calories)} kcal" if obj.calories is not None else "—"
        )

    @admin.display(description="Protein / carbs / fat")
    def macros(self, obj):
        return macro_summary(obj)

    @admin.display(description="Catalog version")
    def food_version_link(self, obj):
        return admin_change_link(obj.food_version)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MealEntry)
class MealEntryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "entry_date",
        "owner",
        "item_count",
        "calorie_total",
        "macro_totals",
        "notes_preview",
        "updated_at",
    )
    list_filter = ("entry_date",)
    search_fields = (
        "name",
        "notes",
        "owner__username",
        "owner__email",
        "items__food_name",
        "items__provider_name",
    )
    autocomplete_fields = ("owner",)
    date_hierarchy = "entry_date"
    list_select_related = ("owner",)
    list_per_page = 50
    save_on_top = True
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            "Meal",
            {"fields": ("owner", "entry_date", "name", "notes")},
        ),
        (
            "Record history",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )
    inlines = (MealItemInline,)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("owner")
            .annotate(
                _admin_item_count=Count("items", distinct=True),
                _admin_calorie_total=Sum("items__calories"),
                _admin_protein_total=Sum("items__protein"),
                _admin_carbohydrate_total=Sum("items__carbohydrates"),
                _admin_fat_total=Sum("items__fat"),
            )
        )

    @admin.display(description="Foods", ordering="_admin_item_count")
    def item_count(self, obj):
        return obj._admin_item_count

    @admin.display(description="Calories", ordering="_admin_calorie_total")
    def calorie_total(self, obj):
        value = obj._admin_calorie_total
        return f"{display_number(value)} kcal" if value is not None else "—"

    @admin.display(description="Protein / carbs / fat")
    def macro_totals(self, obj):
        values = (
            obj._admin_protein_total,
            obj._admin_carbohydrate_total,
            obj._admin_fat_total,
        )
        return " / ".join(
            "—" if value is None else f"{display_number(value)}g" for value in values
        )

    @admin.display(description="Notes")
    def notes_preview(self, obj):
        if not obj.notes:
            return "—"
        return obj.notes if len(obj.notes) <= 60 else f"{obj.notes[:57]}…"


@admin.register(MealItem)
class MealItemAdmin(admin.ModelAdmin):
    list_display = (
        "food_name",
        "meal_entry_link",
        "entry_date",
        "owner",
        "servings_display",
        "portion",
        "calories_display",
        "macros",
        "food_version_link",
    )
    list_display_links = ("food_name",)
    list_filter = ("meal_entry__entry_date", "serving_unit")
    search_fields = (
        "food_name",
        "provider_name",
        "meal_entry__name",
        "meal_entry__owner__username",
        "meal_entry__owner__email",
        "food_version__food_item__name",
    )
    list_select_related = (
        "meal_entry__owner",
        "food_version__food_item",
    )
    list_per_page = 50
    readonly_fields = (
        "meal_entry_link",
        "food_version_link",
        "servings",
        "order",
        "food_name",
        "provider_name",
        "serving_quantity",
        "serving_unit",
        "serving_label",
        "calories",
        "protein",
        "carbohydrates",
        "fat",
        "fiber",
        "sugar",
        "sodium",
        "cholesterol",
        "component_details",
    )
    fieldsets = (
        (
            "Diary context",
            {"fields": ("meal_entry_link", "food_version_link", "order")},
        ),
        (
            "Meal item",
            {
                "fields": (
                    "food_name",
                    "provider_name",
                    "servings",
                    ("serving_quantity", "serving_unit"),
                    "serving_label",
                )
            },
        ),
        (
            "Saved nutrition",
            {
                "fields": (
                    ("calories", "protein"),
                    ("carbohydrates", "fat"),
                    ("fiber", "sugar"),
                    ("sodium", "cholesterol"),
                )
            },
        ),
        (
            "Saved component breakdown",
            {"classes": ("collapse",), "fields": ("component_details",)},
        ),
    )

    @admin.display(description="Components")
    def component_details(self, obj):
        if not obj.component_snapshot:
            return "None"
        return format_html(
            "<pre>{}</pre>", json.dumps(obj.component_snapshot, indent=2)
        )

    @admin.display(description="Meal", ordering="meal_entry__name")
    def meal_entry_link(self, obj):
        return admin_change_link(obj.meal_entry)

    @admin.display(description="Catalog version")
    def food_version_link(self, obj):
        return admin_change_link(obj.food_version)

    @admin.display(description="Date", ordering="meal_entry__entry_date")
    def entry_date(self, obj):
        return obj.meal_entry.entry_date

    @admin.display(description="Owner", ordering="meal_entry__owner__email")
    def owner(self, obj):
        return obj.meal_entry.owner

    @admin.display(description="Portion")
    def portion(self, obj):
        if obj.serving_label:
            return obj.serving_label
        return f"{display_number(obj.serving_quantity)} {obj.serving_unit}"

    @admin.display(description="Servings", ordering="servings")
    def servings_display(self, obj):
        return display_number(obj.servings)

    @admin.display(description="Calories", ordering="calories")
    def calories_display(self, obj):
        return (
            f"{display_number(obj.calories)} kcal" if obj.calories is not None else "—"
        )

    @admin.display(description="Protein / carbs / fat")
    def macros(self, obj):
        return macro_summary(obj)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
