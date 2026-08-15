from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from .models import (
    FoodComponent,
    FoodItem,
    FoodItemVersion,
    NutrientAmount,
    SourceReference,
)


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
):
    food_item = FoodItem(
        name=name,
        scope=scope,
        origin_type=origin_type,
        provider_name=provider_name,
        owner=owner,
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
    nutrients = definition.pop("nutrients", [])
    sources = definition.pop("sources", [])
    components = definition.pop("components", [])

    version = FoodItemVersion(
        food_item=locked_item,
        version_number=next_version,
        created_by=created_by,
        **definition,
    )
    version.full_clean()
    version.save()

    for nutrient_data in nutrients:
        amount = NutrientAmount(food_version=version, **nutrient_data)
        amount.full_clean()
        amount.save()

    for source_data in sources:
        source = SourceReference(food_version=version, **source_data)
        source.full_clean()
        source.save()

    for component_data in components:
        component_data = component_data.copy()
        child_food = component_data.pop("food_item")
        if child_food.pk == locked_item.pk:
            raise ValidationError(
                {"components": "A food cannot include itself as a component."}
            )
        child_version = child_food.current_version
        if child_version is None:
            raise ValidationError(
                {"components": f"{child_food.name} has no current definition."}
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
