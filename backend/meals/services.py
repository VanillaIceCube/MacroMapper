from decimal import Decimal

from django.db import transaction

from estimates.provider import EstimationProviderError, get_estimation_provider
from foods.models import FoodItemVersion
from foods.nutrients import NUTRIENT_FIELDS, NUTRIENT_METADATA

from .models import MealEntry, MealItem


def generate_meal_name(*, owner, entry_date, item_inputs):
    meal_number = MealEntry.objects.filter(
        owner=owner,
        entry_date=entry_date,
    ).count()
    fallback_name = f"Meal-{meal_number:02d}"
    selected_foods = [
        {
            "name": item["food_item"].name,
            "provider_name": item["food_item"].provider_name,
            "servings": str(item["servings"]),
        }
        for item in sorted(item_inputs, key=lambda item: item["order"])
    ]
    try:
        generated_name = get_estimation_provider().generate_name(selected_foods)
    except EstimationProviderError:
        return fallback_name
    normalized_name = " ".join(str(generated_name or "").split()).strip()
    return normalized_name[:120] or fallback_name


def _effective_nutrients(version, visited=None):
    visited = set(visited or ())
    if version.pk in visited:
        return {field: None for field in NUTRIENT_FIELDS}
    path = visited | {version.pk}

    direct = {field: getattr(version, field) for field in NUTRIENT_FIELDS}
    components = list(
        version.components.select_related("child_version__food_item").all()
    )
    if not components:
        return direct

    # A composite food is a container for its component values. Prefer the
    # recursive component rollup even when a parent version contains stale,
    # partial, or zero direct nutrient columns; otherwise a zero parent value
    # masks the nutrition that should be shown and saved for the meal.
    totals = {field: Decimal("0") for field in NUTRIENT_FIELDS}
    has_known_value = {field: False for field in NUTRIENT_FIELDS}
    for component in components:
        child_nutrients = _effective_nutrients(component.child_version, path)
        for field, amount in child_nutrients.items():
            if amount is not None:
                has_known_value[field] = True
                totals[field] += amount * component.servings
    return {
        field: totals[field] if has_known_value[field] else None
        for field in NUTRIENT_FIELDS
    }


def _component_tree(version, visited=None):
    visited = set(visited or ())
    if version.pk in visited:
        return []
    path = visited | {version.pk}

    snapshots = []
    for component in version.components.select_related(
        "child_version__food_item"
    ).order_by("order", "id"):
        child = component.child_version
        child_nutrients = _effective_nutrients(child, path)
        snapshots.append(
            {
                "food_item_id": child.food_item_id,
                "food_version_id": child.id,
                "food_name": child.food_item.name,
                "provider_name": child.food_item.provider_name,
                "servings": str(component.servings),
                "serving_quantity": str(child.serving_quantity),
                "serving_unit": child.serving_unit,
                "serving_label": child.serving_label,
                "nutrients": [
                    {
                        "key": key,
                        "name": NUTRIENT_METADATA[key]["name"],
                        "unit": NUTRIENT_METADATA[key]["unit"],
                        "amount": f"{amount:.4f}",
                    }
                    for key, amount in child_nutrients.items()
                    if amount is not None
                ],
                "components": _component_tree(child, path),
            }
        )
    return snapshots


@transaction.atomic
def replace_meal_items(*, meal_entry, item_inputs):
    requested_version_ids = [
        item["food_version"] for item in item_inputs if "food_version" in item
    ]
    pinned_versions = {
        version.pk: version
        for version in FoodItemVersion.objects.filter(
            pk__in=requested_version_ids
        ).select_related("food_item")
    }
    current_versions = {
        version.food_item_id: version
        for version in FoodItemVersion.objects.filter(
            food_item_id__in=[item["food_item"].pk for item in item_inputs],
            current_for_food_item__isnull=False,
        ).select_related("food_item")
    }
    meal_entry.items.all().delete()

    for item_input in item_inputs:
        food_item = item_input["food_item"]
        version_id = item_input.get("food_version")
        version = pinned_versions.get(version_id) or current_versions[food_item.pk]
        servings = item_input["servings"]
        MealItem.objects.create(
            meal_entry=meal_entry,
            food_version=version,
            servings=servings,
            order=item_input["order"],
            food_name=food_item.name,
            provider_name=food_item.provider_name,
            serving_quantity=version.serving_quantity,
            serving_unit=version.serving_unit,
            serving_label=version.serving_label,
            component_snapshot=_component_tree(version),
            **{
                field: amount * servings if amount is not None else None
                for field, amount in _effective_nutrients(version).items()
            },
        )


def daily_totals(meals):
    items = [item for meal in meals for item in meal.items.all()]
    return [
        {
            "key": key,
            "name": metadata["name"],
            "unit": metadata["unit"],
            "amount": (
                sum(
                    (
                        getattr(item, key)
                        for item in items
                        if getattr(item, key) is not None
                    ),
                    Decimal("0"),
                )
                if any(getattr(item, key) is not None for item in items)
                else None
            ),
        }
        for key, metadata in NUTRIENT_METADATA.items()
    ]
