"""Bounded app operations. Confirmation never invokes meal estimation/name generation."""

import hashlib
import json
from datetime import timedelta
from types import SimpleNamespace

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from foods.models import FoodComponent, FoodItem, FoodItemVersion, SourceReference
from foods.nutrients import NUTRIENT_FIELDS
from meals.models import MealEntry
from meals.serializers import MealEntrySerializer
from meals.services import _effective_nutrients, daily_totals

from .auth import CLIENTS, ISSUER, READ, RESOURCE, WRITE, linked_user
from .models import IdentityLink, MealConfirmation


def principal(token, *, write=False):
    if (
        token is None
        or token.claims.get("iss") != ISSUER
        or token.resource != RESOURCE
        or token.client_id not in CLIENTS
        or not token.expires_at
        or token.expires_at <= timezone.now().timestamp()
        or READ not in token.scopes
        or (write and WRITE not in token.scopes)
    ):
        raise PermissionDenied("MCP permission denied.")
    link = linked_user(token.subject)
    if link is None:
        raise PermissionDenied("MCP permission denied.")
    return link


def nutrients(item):
    return {
        key: str(value) if (value := getattr(item, key)) is not None else None
        for key in NUTRIENT_FIELDS
    }


def meal_summary(meal):
    items = list(meal.items.order_by("order", "id")[:21])
    return {
        "id": meal.pk,
        "date": meal.entry_date.isoformat(),
        "name": meal.name,
        "notes": meal.notes[:2000],
        "notes_truncated": len(meal.notes) > 2000,
        "updated_at": meal.updated_at.isoformat(),
        "items": [
            {
                "food_item_id": item.food_version.food_item_id,
                "food_version_id": item.food_version_id,
                "name": item.food_name,
                "servings": str(item.servings),
                "nutrients": nutrients(item),
            }
            for item in items[:20]
        ],
        "items_truncated": len(items) > 20,
    }


def search_foods(token, query, limit, offset):
    user = principal(token).user
    foods = list(
        FoodItem.objects.active()
        .visible_to(user)
        .filter(
            Q(name__icontains=query) | Q(provider_name__icontains=query),
            current_version__isnull=False,
        )
        .select_related("current_version")
        .order_by("name", "id")[offset : offset + limit + 1]
    )
    return {
        "foods": [
            {
                "id": food.pk,
                "name": food.name,
                "provider": food.provider_name,
                "scope": food.scope,
                "version_id": food.current_version_id,
                "serving_quantity": str(food.current_version.serving_quantity),
                "serving_unit": food.current_version.serving_unit,
                "serving_label": food.current_version.serving_label,
                "provenance": food.current_version.provenance,
            }
            for food in foods[:limit]
        ],
        "has_more": len(foods) > limit,
        "next_offset": offset + limit
        if len(foods) > limit and offset + limit <= 1000
        else None,
    }


def read_diary(token, day, limit, offset):
    user = principal(token).user
    meals = list(
        MealEntry.objects.filter(owner=user, entry_date=day).order_by("id")[
            offset : offset + limit + 1
        ]
    )
    return {
        "meals": [meal_summary(meal) for meal in meals[:limit]],
        "has_more": len(meals) > limit,
        "next_offset": offset + limit
        if len(meals) > limit and offset + limit <= 1000
        else None,
    }


def nutrition_totals(token, start, end):
    user = principal(token).user
    if end < start or (end - start).days > 30:
        raise ValidationError("Choose an ordered range of at most 31 days.")
    meals = list(
        MealEntry.objects.filter(owner=user, entry_date__range=(start, end)).order_by(
            "id"
        )[:501]
    )
    if len(meals) > 500 or sum(meal.items.count() for meal in meals) > 2000:
        raise ValidationError("Too many records; request a shorter date range.")
    totals = daily_totals(meals)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "meal_count": len(meals),
        "nutrients": [
            {
                **total,
                "amount": str(total["amount"]) if total["amount"] is not None else None,
            }
            for total in totals
        ],
        "note": "Known nutrient values only; missing values are not zero. No medical advice.",
    }


def fingerprint(meal, foods, owner_id):
    # Versions are immutable in ordinary app use; include every reachable component
    # version plus each current definition to detect a catalog update before commit.
    pending = {food.current_version_id for food in foods}
    visited = set()
    for _ in range(9):
        if not pending:
            break
        visited |= pending
        if len(visited) > 100:
            raise ValidationError("Meal definition is too complex.")
        children = list(
            FoodComponent.objects.filter(parent_version_id__in=pending).select_related(
                "child_version__food_item"
            )[:101]
        )
        if len(children) > 100 or any(
            child.child_version.food_item.archived_at
            or (
                child.child_version.food_item.scope == "personal"
                and child.child_version.food_item.owner_id != owner_id
            )
            for child in children
        ):
            raise ValidationError("A component is unavailable.")
        pending = {child.child_version_id for child in children} - visited
    if pending:
        raise ValidationError("Meal definition is too complex.")
    edges = list(
        FoodComponent.objects.filter(parent_version_id__in=visited)
        .order_by("pk")
        .values()[:101]
    )
    sources = list(
        SourceReference.objects.filter(food_version_id__in=visited)
        .order_by("pk")
        .values()[:101]
    )
    if len(edges) > 100 or len(sources) > 100:
        raise ValidationError("Meal definition is too complex.")
    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge["parent_version_id"], []).append(
            edge["child_version_id"]
        )
    expanded = 0

    def visit(version_id, path):
        nonlocal expanded
        expanded += 1
        if expanded > 200 or len(path) > 8 or version_id in path:
            raise ValidationError("Meal definition is too complex.")
        for child in adjacency.get(version_id, []):
            visit(child, path | {version_id})

    for food in foods:
        visit(food.current_version_id, set())
    if meal is not None and meal.items.count() > 20:
        raise ValidationError("This meal has too many items for MCP editing.")
    versions = list(
        FoodItemVersion.objects.select_for_update()
        .filter(pk__in=visited)
        .order_by("pk")
        .values()
    )
    component_foods = list(
        FoodItem.objects.select_for_update()
        .filter(pk__in={version["food_item_id"] for version in versions})
        .order_by("pk")
        .values()
    )
    if any(
        food["archived_at"]
        or (food["scope"] == "personal" and food["owner_id"] != owner_id)
        for food in component_foods
    ):
        raise ValidationError("A component is unavailable.")
    state = {
        "meal": meal_summary(meal) if meal else None,
        "foods": [
            (food.pk, food.current_version_id, food.updated_at.isoformat())
            for food in foods
        ],
        "versions": versions,
        "component_foods": component_foods,
        "components": edges,
        "sources": sources,
    }
    return hashlib.sha256(
        json.dumps(state, sort_keys=True, default=str).encode()
    ).hexdigest()


def validated_meal(link, payload):
    meal_id = payload.get("meal_id")
    meal = None
    if meal_id is not None:
        meal = (
            MealEntry.objects.select_for_update()
            .filter(pk=meal_id, owner=link.user)
            .first()
        )
        if meal is None:
            raise ValidationError("Meal unavailable.")
    foods = list(
        FoodItem.objects.select_for_update()
        .active()
        .visible_to(link.user)
        .filter(
            pk__in=[item["food_item"] for item in payload["item_inputs"]],
            current_version__isnull=False,
        )
        .order_by("id")
    )
    if len(foods) != len({item["food_item"] for item in payload["item_inputs"]}):
        raise ValidationError("Food unavailable.")
    serializer = MealEntrySerializer(
        meal,
        data={key: value for key, value in payload.items() if key != "meal_id"},
        context={"request": SimpleNamespace(user=link.user)},
    )
    serializer.is_valid(raise_exception=True)
    digest = fingerprint(meal, foods, link.user_id)
    for item in serializer.validated_data["items"]:
        for value in _effective_nutrients(item["food_item"].current_version).values():
            if value is not None and (
                not value.is_finite() or value < 0 or value * item["servings"] >= 10**10
            ):
                raise ValidationError("Nutrient amount is outside the supported range.")
    return serializer, digest


@transaction.atomic
def preview_meal(token, payload):
    link = principal(token, write=True)
    # Lock the link to serialize confirmation preparation/consumption per identity.
    link = lock_link(link)
    MealConfirmation.objects.filter(link=link, expires_at__lte=timezone.now()).delete()
    if MealConfirmation.objects.filter(link=link).count() >= 10:
        raise ValidationError("Too many pending confirmations; wait five minutes.")
    serializer, digest = validated_meal(link, payload)
    preview = MealConfirmation.objects.create(
        link=link,
        client_id=token.client_id,
        payload=payload,
        fingerprint=digest,
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    selected = []
    for item in serializer.validated_data["items"]:
        food = item["food_item"]
        version = food.current_version
        selected.append(
            {
                "food_id": food.pk,
                "version_id": version.pk,
                "name": food.name,
                "provider": food.provider_name,
                "servings": str(item["servings"]),
                "serving_quantity": str(version.serving_quantity),
                "serving_unit": version.serving_unit,
                "serving_label": version.serving_label,
                "nutrients": {
                    key: str(value * item["servings"]) if value is not None else None
                    for key, value in _effective_nutrients(version).items()
                },
            }
        )
    return {
        "confirmation_id": str(preview.pk),
        "expires_at": preview.expires_at.isoformat(),
        "action": "replace meal" if serializer.instance else "create meal",
        "meal": payload,
        "selected_foods": selected,
        "replaces": meal_summary(serializer.instance) if serializer.instance else None,
        "instruction": "Show the exact meal, food IDs, quantities and replacement action to the user. Call confirm_meal only after explicit user approval.",
    }


@transaction.atomic
def confirm_meal(token, confirmation_id, confirmed):
    link = principal(token, write=True)
    link = lock_link(link)
    if confirmed is not True:
        raise ValidationError("Explicit user confirmation is required.")
    preview = MealConfirmation.objects.filter(
        pk=confirmation_id,
        link=link,
        client_id=token.client_id,
        expires_at__gt=timezone.now(),
    ).first()
    if preview is None:
        raise ValidationError("Confirmation unavailable or expired; preview again.")
    serializer, digest = validated_meal(link, preview.payload)
    if digest != preview.fingerprint:
        raise ValidationError("Meal or food changed; preview again.")
    # The conditional delete and meal write share one transaction. Replays cannot
    # produce a second write, including competing requests in separate workers.
    if MealConfirmation.objects.filter(pk=preview.pk).delete()[0] != 1:
        raise ValidationError("Confirmation unavailable; preview again.")
    meal = serializer.save()
    return {"saved": True, "meal": meal_summary(meal)}


def lock_link(link):
    # SQLite ignores SELECT FOR UPDATE. Acquire its database writer lock before
    # reading meal/catalog state. A concurrent commit after principal()'s read
    # makes this snapshot upgrade fail closed, rather than overwriting that edit.
    # On row-locking databases this serializes the identity; the meal, selected
    # foods and immutable versions are then locked through fingerprint/save.
    if (
        IdentityLink.objects.filter(pk=link.pk, active=True).update(active=F("active"))
        != 1
    ):
        raise PermissionDenied("MCP permission denied.")
    current = (
        IdentityLink.objects.select_for_update()
        .select_related("user")
        .filter(
            pk=link.pk,
            active=True,
            user__is_active=True,
        )
        .first()
    )
    if current is None:
        raise PermissionDenied("MCP permission denied.")
    return current
