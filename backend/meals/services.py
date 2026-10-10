from decimal import Decimal

from django.db import transaction

from estimates.provider import EstimationProviderError, get_estimation_provider
from foods.models import FoodItemVersion
from foods.nutrients import NUTRIENT_FIELDS, NUTRIENT_METADATA
from foods.portions import portion_options_for_serving
from foods.services import build_component_map

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


def _effective_nutrients(
    version, visited=None, *, component_map=None, nutrient_cache=None
):
    visited = set(visited or ())
    if version.pk in visited:
        return {field: None for field in NUTRIENT_FIELDS}
    if component_map is None:
        component_map = build_component_map([version.pk])
    if nutrient_cache is None:
        nutrient_cache = {}
    cache_key = (version.pk, frozenset(visited))
    if cache_key in nutrient_cache:
        return nutrient_cache[cache_key]
    path = visited | {version.pk}

    direct = {field: getattr(version, field) for field in NUTRIENT_FIELDS}
    components = component_map.get(version.pk, ())
    if not components:
        nutrient_cache[cache_key] = direct
        return direct

    # A composite food is a container for its component values. Prefer the
    # recursive component rollup even when a parent version contains stale,
    # partial, or zero direct nutrient columns; otherwise a zero parent value
    # masks the nutrition that should be shown and saved for the meal.
    totals = {field: Decimal("0") for field in NUTRIENT_FIELDS}
    has_known_value = {field: False for field in NUTRIENT_FIELDS}
    for component in components:
        child_nutrients = _effective_nutrients(
            component.child_version,
            path,
            component_map=component_map,
            nutrient_cache=nutrient_cache,
        )
        for field, amount in child_nutrients.items():
            if amount is not None:
                has_known_value[field] = True
                totals[field] += amount * component.servings
    result = {
        field: totals[field] if has_known_value[field] else None
        for field in NUTRIENT_FIELDS
    }
    nutrient_cache[cache_key] = result
    return result


def _component_tree(version, visited=None, *, component_map=None, nutrient_cache=None):
    visited = set(visited or ())
    if version.pk in visited:
        return []
    if component_map is None:
        component_map = build_component_map([version.pk])
    if nutrient_cache is None:
        nutrient_cache = {}
    path = visited | {version.pk}

    snapshots = []
    for component in component_map.get(version.pk, ()):
        child = component.child_version
        child_nutrients = _effective_nutrients(
            child,
            path,
            component_map=component_map,
            nutrient_cache=nutrient_cache,
        )
        snapshots.append(
            {
                "food_item_id": child.food_item_id,
                "food_version_id": child.id,
                "food_name": child.food_item.name,
                "provider_name": child.food_item.provider_name,
                "origin_type": child.food_item.origin_type,
                "servings": str(component.servings),
                "serving_quantity": str(child.serving_quantity),
                "serving_unit": child.serving_unit,
                "serving_label": child.serving_label,
                "serving_weight_grams": (
                    str(child.serving_weight_grams)
                    if child.serving_weight_grams is not None
                    else None
                ),
                "serving_volume_ml": (
                    str(child.serving_volume_ml)
                    if child.serving_volume_ml is not None
                    else None
                ),
                "portion_options": portion_options_for_serving(
                    quantity=child.serving_quantity,
                    unit=child.serving_unit,
                    label=child.serving_label,
                    weight_grams=child.serving_weight_grams,
                    volume_milliliters=child.serving_volume_ml,
                ),
                "provenance": child.provenance,
                "confidence_score": (
                    str(child.confidence_score)
                    if child.confidence_score is not None
                    else None
                ),
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
                "sources": [
                    {
                        "title": source.title,
                        "provider": source.provider,
                        "url": source.url,
                        "accessed_on": (
                            source.accessed_on.isoformat()
                            if source.accessed_on
                            else None
                        ),
                        "is_official": child.provenance
                        == FoodItemVersion.Provenance.OFFICIAL,
                    }
                    for source in child.sources.all()
                ],
                "components": _component_tree(
                    child,
                    path,
                    component_map=component_map,
                    nutrient_cache=nutrient_cache,
                ),
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
    component_map = build_component_map(
        [
            version.pk
            for version in [*pinned_versions.values(), *current_versions.values()]
        ]
    )
    nutrient_cache = {}

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
            component_snapshot=_component_tree(
                version,
                component_map=component_map,
                nutrient_cache=nutrient_cache,
            ),
            **{
                field: amount * servings if amount is not None else None
                for field, amount in _effective_nutrients(
                    version,
                    component_map=component_map,
                    nutrient_cache=nutrient_cache,
                ).items()
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
