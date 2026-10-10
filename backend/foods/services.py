from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from .models import (
    FoodComponent,
    FoodItem,
    FoodItemVersion,
    SourceReference,
)


def build_component_map(root_version_ids):
    component_map = defaultdict(list)
    pending_version_ids = {vid for vid in root_version_ids if vid}
    visited_version_ids = set()
    while pending_version_ids:
        pending_version_ids -= visited_version_ids
        if not pending_version_ids:
            break
        components = list(
            FoodComponent.objects.filter(parent_version_id__in=pending_version_ids)
            .select_related("child_version__food_item")
            .prefetch_related("child_version__sources")
        )
        visited_version_ids.update(pending_version_ids)
        pending_version_ids = set()
        for component in components:
            component_map[component.parent_version_id].append(component)
            if component.child_version_id not in visited_version_ids:
                pending_version_ids.add(component.child_version_id)
    return component_map


@transaction.atomic
def create_food_item(
    *,
    name,
    scope,
    origin_type,
    provider_name,
    owner,
    definition,
    created_by,
    shared_fingerprint=None,
):
    food_item = FoodItem(
        name=name,
        scope=scope,
        origin_type=origin_type,
        provider_name=provider_name,
        owner=owner,
        shared_fingerprint=shared_fingerprint,
    )
    food_item.full_clean()
    food_item.save()
    create_food_version(
        food_item=food_item,
        definition=definition,
        created_by=created_by,
    )
    return food_item


@transaction.atomic
def create_food_version(*, food_item, definition, created_by):
    locked_item = FoodItem.objects.select_for_update().get(pk=food_item.pk)
    next_version = (
        locked_item.versions.aggregate(highest=Max("version_number"))["highest"] or 0
    ) + 1

    definition = definition.copy()
    nutrients = definition.pop("nutrients", {})
    sources = definition.pop("sources", [])
    components = definition.pop("components", [])

    version = FoodItemVersion(
        food_item=locked_item,
        version_number=next_version,
        created_by=created_by,
        **nutrients,
        **definition,
    )
    version.full_clean()
    version.save()

    for source_data in sources:
        source = SourceReference(food_version=version, **source_data)
        source.full_clean()
        source.save()

    for component_data in components:
        component_data = component_data.copy()
        child_food = component_data.pop("food_item")
        pinned_child_version = component_data.pop("food_version", None)
        if child_food.pk == locked_item.pk:
            raise ValidationError(
                {"components": "A food cannot include itself as a component."}
            )
        child_version = pinned_child_version or child_food.current_version
        if child_version is None:
            raise ValidationError(
                {"components": f"{child_food.name} has no current definition."}
            )
        if child_version.food_item_id != child_food.pk:
            raise ValidationError(
                {"components": "A pinned component version must belong to its food."}
            )
        component = FoodComponent(
            parent_version=version,
            child_version=child_version,
            **component_data,
        )
        component.full_clean()
        component.save()

    locked_item.current_version = version
    locked_item.full_clean()
    locked_item.save(update_fields=["current_version", "updated_at"])
    food_item.current_version = version
    food_item.updated_at = locked_item.updated_at
    return version
