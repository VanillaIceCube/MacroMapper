"""Diary, nutrition and actor-scoped meal services shared by REST and MCP."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch
from django.utils.dateparse import parse_date
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as APIValidationError

from apps.estimates.provider import EstimationProviderError, get_estimation_provider
from apps.foods.evidence import source_data, version_evidence
from apps.foods.models import FoodItem, FoodItemVersion
from apps.foods.nutrients import NUTRIENT_FIELDS, NUTRIENT_METADATA
from apps.foods.portions import portion_options_for_serving
from apps.foods.services import build_component_map

from .models import MealEntry, MealItem


def generate_meal_name(*, owner, entry_date, item_inputs=(), selected_foods=None):
    meal_number = MealEntry.objects.filter(
        owner=owner,
        entry_date=entry_date,
    ).count()
    fallback_name = f"Meal-{meal_number:02d}"
    if selected_foods is None:
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
    for field, coverage in version.evidence.get("nutrients", {}).items():
        if (
            coverage.get("status") == "official_verified"
            and direct.get(field) is not None
        ):
            result[field] = direct[field]
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
                    natural_servings=child.natural_servings,
                ),
                "provenance": child.provenance,
                "evidence": version_evidence(child),
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
                "sources": [source_data(source) for source in child.sources.all()],
                "components": _component_tree(
                    child,
                    path,
                    component_map=component_map,
                    nutrient_cache=nutrient_cache,
                ),
            }
        )
    return snapshots


def _snapshot_portions(snapshot, requested):
    for index, component in enumerate(snapshot):
        if index >= len(requested):
            continue
        selected = requested[index].get("selected_portion_key", "base")
        if selected in {
            option["key"] for option in component.get("portion_options", [])
        }:
            component["selected_portion_key"] = selected
        _snapshot_portions(
            component.get("components", []), requested[index].get("components", [])
        )
    return snapshot


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
            selected_portion_key=item_input.get("selected_portion_key", "base"),
            component_snapshot=_snapshot_portions(
                _component_tree(
                    version, component_map=component_map, nutrient_cache=nutrient_cache
                ),
                item_input.get("portion_selections", {}).get("components", []),
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


def meals_for(actor, query=None):
    query = query or {}
    queryset = (
        MealEntry.objects.filter(owner=actor)
        .prefetch_related(
            Prefetch(
                "items",
                queryset=MealItem.objects.select_related(
                    "food_version",
                    "food_version__food_item",
                ).prefetch_related("food_version__sources"),
            )
        )
        .select_related("owner", "accepted_proposal")
    )
    requested_date = query.get("date")
    if requested_date is not None:
        parsed_date = parse_date(requested_date)
        if parsed_date is None:
            raise APIValidationError(
                {"date": "Supply a valid date in YYYY-MM-DD format."}
            )
        queryset = queryset.filter(entry_date=parsed_date)
    return queryset


def require_meal_owner(actor, meal):
    if not MealEntry.objects.filter(pk=meal.pk, owner=actor).exists():
        raise PermissionDenied("Meal unavailable.")


def create_meal(actor, data):
    data = validate_meal_data(actor, dict(data), partial=False)
    item_inputs = data.pop("items")
    if not data.get("name"):
        data["name"] = generate_meal_name(
            owner=actor, entry_date=data["entry_date"], item_inputs=item_inputs
        )
    # Automatic naming may use the provider. Acquire the write transaction only
    # after it finishes, then recheck catalog access before persisting snapshots.
    with transaction.atomic():
        validate_meal_data(actor, {**data, "items": item_inputs}, partial=False)
        meal = MealEntry.objects.create(owner=actor, **data)
        replace_meal_items(meal_entry=meal, item_inputs=item_inputs)
        return meal


@transaction.atomic
def update_meal(actor, meal, data):
    meal = MealEntry.objects.select_for_update().get(pk=meal.pk)
    require_meal_owner(actor, meal)
    data = validate_meal_data(actor, dict(data), meal)
    item_inputs = data.pop("items", None)
    for field, value in data.items():
        setattr(meal, field, value)
    meal.save()
    if item_inputs is not None:
        replace_meal_items(meal_entry=meal, item_inputs=item_inputs)
    return meal


@transaction.atomic
def delete_meal(actor, meal):
    meal = MealEntry.objects.select_for_update().get(pk=meal.pk)
    require_meal_owner(actor, meal)
    meal.delete()


def validate_meal_data(actor, attrs, instance=None, *, partial=True):
    name = attrs.get("name", getattr(instance, "name", "")).strip()
    if not name and instance is not None:
        raise APIValidationError({"name": "This field may not be blank."})
    attrs["name"] = name

    item_inputs = attrs.get("items")
    if item_inputs is None:
        if instance is None or not partial:
            raise APIValidationError({"item_inputs": "Meal items are required."})
        return attrs
    if not item_inputs:
        raise APIValidationError({"item_inputs": "Add at least one food to the meal."})
    existing_versions = set()
    if instance is not None:
        existing_versions = set(
            instance.items.values_list("food_version__food_item_id", "food_version_id")
        )

    available_food_ids = set()
    if actor:
        available_food_ids = set(
            FoodItem.objects.active()
            .visible_to(actor)
            .filter(
                pk__in=[item["food_item"].pk for item in item_inputs],
                current_version__isnull=False,
            )
            .values_list("pk", flat=True)
        )
    if any(
        item["food_item"].pk not in available_food_ids
        and (item["food_item"].pk, item.get("food_version")) not in existing_versions
        for item in item_inputs
    ):
        raise APIValidationError({"item_inputs": "This food is not available."})
    orders = [item["order"] for item in item_inputs]
    if len(orders) != len(set(orders)):
        raise APIValidationError(
            {"item_inputs": "Each meal item order must be unique."}
        )
    supplied_versions = [
        (item["food_item"].pk, item["food_version"])
        for item in item_inputs
        if "food_version" in item
    ]
    if instance is None and supplied_versions:
        raise APIValidationError(
            {"item_inputs": "New meals always use each food's current definition."}
        )
    if instance is not None:
        if any(pair not in existing_versions for pair in supplied_versions):
            raise APIValidationError(
                {
                    "item_inputs": "A saved food version must already belong to this meal."
                }
            )
    return attrs
