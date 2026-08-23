from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from foods.models import FoodItem, FoodItemVersion
from foods.nutrients import NUTRIENT_FIELDS
from foods.portions import portion_options_for_serving
from foods.services import create_food_item
from meals.models import MealEntry
from meals.services import _effective_nutrients, replace_meal_items

from .models import MealProposal
from .provider import get_estimation_provider

STOP_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "for",
    "from",
    "in",
    "of",
    "the",
    "to",
    "with",
}


def _terms(value):
    return {
        term
        for term in re.findall(r"[a-z0-9]+", value.lower())
        if len(term) > 1 and term not in STOP_WORDS
    }


def _decimal(value, *, default="0"):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _storage_decimal(value, *, decimal_places, default="0"):
    quantum = Decimal("1").scaleb(-decimal_places)
    return _decimal(value, default=default).quantize(quantum, rounding=ROUND_HALF_UP)


def _source_kind(provenance):
    if provenance == FoodItemVersion.Provenance.OFFICIAL:
        return "official_verified"
    if provenance == FoodItemVersion.Provenance.AI_ESTIMATE:
        return "ai_estimate"
    return "catalog_estimate"


def _sources(version):
    return [
        {
            "title": source.title,
            "provider": source.provider,
            "url": source.url,
            "accessed_on": (
                source.accessed_on.isoformat() if source.accessed_on else None
            ),
            "is_official": version.provenance == FoodItemVersion.Provenance.OFFICIAL,
        }
        for source in version.sources.all()
    ]


def _portion_options(item):
    return item.get("portion_options") or portion_options_for_serving(
        quantity=item.get("serving_quantity", "1"),
        unit=item.get("serving_unit", FoodItemVersion.ServingUnit.SERVING),
        label=item.get("serving_label", ""),
    )


def _catalog_food(version, *, servings="1", key=None):
    food = version.food_item
    item_key = key or f"catalog-{food.pk}"
    nutrients = _effective_nutrients(version)
    portion_options = portion_options_for_serving(
        quantity=version.serving_quantity,
        unit=version.serving_unit,
        label=version.serving_label,
    )
    option_keys = {option["key"] for option in portion_options}
    return {
        "key": item_key,
        "food_item_id": food.pk,
        "food_version_id": version.pk,
        "name": food.name,
        "provider_name": food.provider_name,
        "origin_type": food.origin_type,
        "servings": str(servings),
        "serving_quantity": str(version.serving_quantity),
        "serving_unit": version.serving_unit,
        "serving_label": version.serving_label,
        "portion_options": portion_options,
        "selected_portion_key": (
            version.serving_unit if version.serving_unit in option_keys else "base"
        ),
        "provenance": version.provenance,
        "source_kind": _source_kind(version.provenance),
        "confidence_score": (
            str(version.confidence_score)
            if version.confidence_score is not None
            else None
        ),
        "nutrients": {
            field: str(amount) if amount is not None else None
            for field, amount in nutrients.items()
        },
        "sources": _sources(version),
        "components": [
            _catalog_food(
                component.child_version,
                servings=component.servings,
                key=f"{item_key}.{index}",
            )
            for index, component in enumerate(version.components.all())
        ],
    }


def find_catalog_matches(*, description, user):
    query_terms = _terms(description)
    if not query_terms:
        return []
    foods = list(
        FoodItem.objects.active()
        .visible_to(user)
        .filter(current_version__isnull=False)
        .select_related("current_version")
        .prefetch_related(
            "current_version__sources",
            "current_version__components__child_version__food_item",
            "current_version__components__child_version__sources",
            "current_version__components__child_version__components",
        )
    )
    candidates = []
    normalized_description = " ".join(sorted(query_terms))
    for food in foods:
        identity_terms = _terms(f"{food.provider_name} {food.name}")
        overlap = len(query_terms & identity_terms)
        if not overlap:
            continue
        coverage = overlap / max(len(identity_terms), 1)
        phrase = " ".join(sorted(identity_terms))
        exactish = phrase == normalized_description or identity_terms <= query_terms
        if exactish or coverage >= 0.6 or overlap >= 2:
            candidates.append((exactish, overlap, coverage, food))
    candidates.sort(
        key=lambda value: (value[0], value[1], value[2], -value[3].pk),
        reverse=True,
    )
    return [candidate[3] for candidate in candidates[:5]]


def _recalculate_item(item):
    item = dict(item)
    item["servings"] = str(_decimal(item.get("servings"), default="1"))
    item["portion_options"] = _portion_options(item)
    option_keys = {option["key"] for option in item["portion_options"]}
    if item.get("selected_portion_key") not in option_keys:
        item["selected_portion_key"] = item["portion_options"][0]["key"]
    components = [
        _recalculate_item(component) for component in item.get("components", [])
    ]
    item["components"] = components
    if components:
        nutrients = {}
        for field in NUTRIENT_FIELDS:
            known_components = [
                component
                for component in components
                if component.get("nutrients", {}).get(field) is not None
            ]
            if not known_components:
                nutrients[field] = None
            else:
                nutrients[field] = str(
                    sum(
                        (
                            _decimal(component["nutrients"][field])
                            * _decimal(component["servings"], default="1")
                            for component in known_components
                        ),
                        Decimal("0"),
                    )
                )
        item["nutrients"] = nutrients
    return item


def normalize_items(items):
    return [_recalculate_item(item) for item in items]


def _items_by_key(items):
    indexed = {}
    for item in items:
        indexed[item["key"]] = item
        indexed.update(_items_by_key(item.get("components", [])))
    return indexed


@transaction.atomic
def create_proposal(*, owner, description, entry_date):
    description = description.strip()
    matches = find_catalog_matches(description=description, user=owner)
    if matches:
        items = [_catalog_food(food.current_version) for food in matches]
        confidence_values = [
            food.current_version.confidence_score
            for food in matches
            if food.current_version.confidence_score is not None
        ]
        return MealProposal.objects.create(
            owner=owner,
            description=description,
            entry_date=entry_date,
            name=matches[0].name if len(matches) == 1 else description[:120],
            generator=MealProposal.Generator.CATALOG,
            provider_name="MacroMapper catalog",
            confidence_score=(min(confidence_values) if confidence_values else None),
            items=items,
        )

    estimate = get_estimation_provider().estimate(description)
    return MealProposal.objects.create(
        owner=owner,
        description=description,
        entry_date=entry_date,
        name=estimate["name"],
        generator=MealProposal.Generator.OPENAI,
        provider_name=estimate["provider_name"],
        provider_model=estimate["provider_model"],
        provider_response_id=estimate["provider_response_id"],
        confidence_score=estimate["confidence_score"],
        items=normalize_items(estimate["items"]),
    )


def _visible_catalog_version(*, owner, item):
    food_item_id = item.get("food_item_id")
    version_id = item.get("food_version_id")
    if not food_item_id or not version_id:
        return None
    return (
        FoodItemVersion.objects.filter(
            pk=version_id,
            food_item_id=food_item_id,
            food_item__archived_at__isnull=True,
        )
        .filter(Q(food_item__scope=FoodItem.Scope.SHARED) | Q(food_item__owner=owner))
        .select_related("food_item")
        .first()
    )


def secure_review_items(*, proposal, owner, items):
    """Keep provenance immutable while accepting quantity and nutrient edits."""

    existing = _items_by_key(proposal.items)

    def secure(item, *, depth=0):
        original = existing.get(item["key"])
        if original is None:
            if depth:
                raise ValidationError(
                    "New ingredients must be added as top-level catalog foods."
                )
            version = _visible_catalog_version(owner=owner, item=item)
            if version is None:
                raise ValidationError(
                    "New proposal foods must come from your visible catalog."
                )
            result = _catalog_food(
                version,
                servings=item["servings"],
                key=item["key"],
            ) | {"components": []}
            selected_portion_key = item["selected_portion_key"]
            if selected_portion_key not in {
                option["key"] for option in result["portion_options"]
            }:
                raise ValidationError("Choose an available portion option.")
            result["selected_portion_key"] = selected_portion_key
            result["nutrients"] = item["nutrients"]
            return result

        result = dict(original)
        result["portion_options"] = _portion_options(original)
        selected_portion_key = item["selected_portion_key"]
        if selected_portion_key not in {
            option["key"] for option in result["portion_options"]
        }:
            raise ValidationError("Choose an available portion option.")
        result["selected_portion_key"] = selected_portion_key
        result["servings"] = item["servings"]
        result["nutrients"] = item["nutrients"]
        requested_components = item.get("components", [])
        original_component_keys = {
            component["key"] for component in original.get("components", [])
        }
        if any(
            component["key"] not in original_component_keys
            for component in requested_components
        ):
            raise ValidationError(
                "New ingredients must be added from the catalog, not inserted into a component tree."
            )
        result["components"] = [
            secure(component, depth=depth + 1) for component in requested_components
        ]
        if original.get("components") and not result["components"]:
            result["nutrients"] = {field: None for field in NUTRIENT_FIELDS}
        return result

    return normalize_items([secure(item) for item in items])


def _definition(item, components):
    nutrients = {
        field: _storage_decimal(value, decimal_places=4)
        for field in NUTRIENT_FIELDS
        if (value := item.get("nutrients", {}).get(field)) is not None
    }
    confidence = item.get("confidence_score")
    return {
        "serving_quantity": _storage_decimal(
            item.get("serving_quantity"), decimal_places=3, default="1"
        ),
        "serving_unit": item.get("serving_unit") or "serving",
        "serving_label": item.get("serving_label") or "one serving",
        "provenance": item.get("provenance") or FoodItemVersion.Provenance.AI_ESTIMATE,
        "confidence_score": (
            _storage_decimal(confidence, decimal_places=3)
            if confidence is not None
            else None
        ),
        "nutrients": nutrients,
        "sources": [
            {
                "title": source["title"],
                "provider": source.get("provider", ""),
                "url": source["url"],
                "accessed_on": source.get("accessed_on"),
            }
            for source in item.get("sources", [])
        ],
        "components": components,
    }


def _matches_catalog_nutrients(item, version):
    catalog_nutrients = _effective_nutrients(version)
    requested_nutrients = item.get("nutrients", {})
    for field in NUTRIENT_FIELDS:
        catalog_value = catalog_nutrients.get(field)
        requested_value = requested_nutrients.get(field)
        if catalog_value is None or requested_value is None:
            if catalog_value is not None or requested_value is not None:
                return False
            continue
        if _storage_decimal(catalog_value, decimal_places=4) != _storage_decimal(
            requested_value, decimal_places=4
        ):
            return False
    return True


def _materialize_item(*, owner, item):
    components = []
    for order, component_item in enumerate(item.get("components", [])):
        child_food, child_version = _materialize_item(owner=owner, item=component_item)
        components.append(
            {
                "food_item": child_food,
                "food_version": child_version,
                "servings": _storage_decimal(
                    component_item.get("servings"),
                    decimal_places=4,
                    default="1",
                ),
                "order": order,
            }
        )

    catalog_version = _visible_catalog_version(owner=owner, item=item)
    if (
        catalog_version is not None
        and not components
        and _matches_catalog_nutrients(item, catalog_version)
    ):
        return catalog_version.food_item, catalog_version

    origin_type = item.get("origin_type") or FoodItem.OriginType.GENERIC
    provider_name = item.get("provider_name", "")
    if (
        origin_type
        in {
            FoodItem.OriginType.BRANDED,
            FoodItem.OriginType.RESTAURANT,
        }
        and not provider_name.strip()
    ):
        origin_type = FoodItem.OriginType.GENERIC
    definition = _definition(item, components)
    if catalog_version is not None:
        definition["provenance"] = FoodItemVersion.Provenance.USER_ENTERED
        definition["confidence_score"] = None
    food = create_food_item(
        name=item["name"],
        scope=FoodItem.Scope.PERSONAL,
        origin_type=origin_type,
        provider_name=provider_name,
        owner=owner,
        definition=definition,
        created_by=owner,
    )
    return food, food.current_version


@transaction.atomic
def accept_proposal(*, proposal):
    proposal = MealProposal.objects.select_for_update().get(pk=proposal.pk)
    if proposal.status != MealProposal.Status.DRAFT:
        raise ValidationError("This proposal has already been accepted.")
    items = normalize_items(proposal.items)
    if not items:
        raise ValidationError("Add at least one food before saving this meal.")

    meal = MealEntry.objects.create(
        owner=proposal.owner,
        entry_date=proposal.entry_date,
        name=proposal.name,
        notes=f"Estimated from: {proposal.description}",
    )
    item_inputs = []
    for order, item in enumerate(items):
        food, version = _materialize_item(owner=proposal.owner, item=item)
        item_inputs.append(
            {
                "food_item": food,
                "food_version": version.pk,
                "servings": _storage_decimal(
                    item.get("servings"), decimal_places=4, default="1"
                ),
                "order": order,
            }
        )
    replace_meal_items(meal_entry=meal, item_inputs=item_inputs)
    proposal.items = items
    proposal.status = MealProposal.Status.ACCEPTED
    proposal.accepted_meal = meal
    proposal.accepted_at = timezone.now()
    proposal.save(
        update_fields=["items", "status", "accepted_meal", "accepted_at", "updated_at"]
    )
    return meal
