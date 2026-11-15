"""Actor-scoped reads, catalog snapshots and bounded result pagination."""

import hashlib
import json

from django.db import connection
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from apps.estimates import services as proposal_services
from apps.estimates.models import MealProposal
from apps.estimates.serializers import (
    MealProposalSerializer,
)
from apps.foods import services as food_services
from apps.foods.models import FoodComponent, FoodItem, FoodItemVersion, SourceReference
from apps.foods.serializers import FoodItemSerializer
from apps.meals import services as meal_services
from apps.meals.models import MealEntry, MealItem
from apps.meals.serializers import MealEntrySerializer, MealItemSerializer
from apps.meals.services import daily_totals
from apps.notifications import services as notification_services
from apps.notifications.models import Notification
from apps.notifications.serializers import NotificationSerializer

from .permissions import principal
from .results import json_value, result

SERIALIZERS = {
    "foods": FoodItemSerializer,
    "meals": MealEntrySerializer,
    "proposals": MealProposalSerializer,
    "notifications": NotificationSerializer,
}


def records_for(kind, actor, query=None, *, retrieve=False):
    query = query or {}
    if kind == "foods":
        return food_services.foods_for(actor, query, retrieve=retrieve)
    if kind == "meals":
        return meal_services.meals_for(actor, query)
    if kind == "proposals":
        return proposal_services.proposals_for(actor)
    return notification_services.notifications_for(actor)


def target_for(operation, actor, target_id):
    if not operation.detail:
        return None
    obj = get_object_or_404(records_for(operation.kind, actor), pk=target_id)
    obj = type(obj).objects.select_for_update().get(pk=obj.pk)
    if operation.kind == "foods":
        food_services.require_personal_owner(actor, obj)
    return obj


def serialize(kind, actor, value, *, many=False):
    return SERIALIZERS[kind](value, many=many, context={"actor": actor}).data


def catalog_state(food_ids, version_ids, owner):
    """Bound and lock reachable catalog definitions before recursive serializers."""
    food_ids, pending, visited, edges = set(food_ids), set(version_ids), set(), []

    def rows(model):
        return (
            model.objects.select_for_update()
            if connection.in_atomic_block
            else model.objects.all()
        )

    foods = list(rows(FoodItem).filter(pk__in=food_ids).order_by("pk"))
    if len(foods) != len(food_ids) or any(
        food.scope == "personal" and food.owner_id != owner.pk for food in foods
    ):
        raise ValidationError("Food unavailable.")
    pending |= {food.current_version_id for food in foods if food.current_version_id}
    for _ in range(9):
        if not pending:
            break
        visited |= pending
        if len(visited) > 100:
            raise ValidationError("Food definition too complex.")
        children = list(
            rows(FoodComponent).filter(parent_version_id__in=pending).values()[:101]
        )
        edges += children
        if len(edges) > 100:
            raise ValidationError("Food definition too complex.")
        pending = {edge["child_version_id"] for edge in children} - visited
    if pending:
        raise ValidationError("Food definition too deep.")
    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge["parent_version_id"], []).append(
            edge["child_version_id"]
        )

    expanded = 0

    def cycle(node, path):
        nonlocal expanded
        expanded += 1
        if node in path or len(path) > 8 or expanded > 1000:
            raise ValidationError("Cyclic food definition.")
        for child in adjacency.get(node, []):
            cycle(child, path | {node})

    for node in visited:
        cycle(node, set())
    versions = list(
        rows(FoodItemVersion).filter(pk__in=visited).order_by("pk").values()
    )
    related = list(
        rows(FoodItem)
        .filter(pk__in={v["food_item_id"] for v in versions})
        .order_by("pk")
        .values()
    )
    if any(
        food["scope"] == "personal" and food["owner_id"] != owner.pk for food in related
    ):
        raise ValidationError("Food unavailable.")
    sources = list(
        SourceReference.objects.filter(food_version_id__in=visited)
        .order_by("pk")
        .values()[:101]
    )
    if len(sources) > 100:
        raise ValidationError("Food definition too complex.")
    return {
        "foods": list(FoodItem.objects.filter(pk__in=food_ids).order_by("pk").values()),
        "related": related,
        "versions": versions,
        "edges": sorted(edges, key=lambda edge: edge["id"]),
        "sources": sources,
    }


def list_records(raw, kind, query, limit, offset):
    if (
        type(limit) is not int
        or not 1 <= limit <= 20
        or type(offset) is not int
        or not 0 <= offset <= 1000
    ):
        raise ValidationError("Invalid bounded page.")
    token = principal(raw)
    queryset = records_for(kind, token.user, query)
    if kind == "notifications" and "is_read" in query:
        queryset = queryset.filter(is_read=query["is_read"] == "true")
    if kind == "proposals" and query.get("status"):
        queryset = queryset.filter(status=query["status"])
    if kind == "proposals":
        # Listing must remain usable after a successful oversized paid result.
        # Do not serialize repeated item snapshots merely to discover its ID.
        queryset = queryset.prefetch_related(None)
    if kind == "meals":
        return list_meals(queryset, token.user, limit, offset)
    records = list(queryset[offset : offset + limit + 1])
    catalog_state(
        [obj.pk for obj in records[:limit]] if kind == "foods" else [],
        [],
        token.user,
    )
    return result(
        [proposal_summary(record) for record in records[:limit]]
        if kind == "proposals"
        else serialize(kind, token.user, records[:limit], many=True),
        has_more=len(records) > limit,
        next_offset=offset + limit
        if len(records) > limit and offset + limit <= 1000
        else None,
    )


def meal_summary(meal):
    return {
        "id": meal.pk,
        "name": meal.name[:120],
        "entry_date": meal.entry_date,
        "updated_at": meal.updated_at,
        "item_count": MealItem.objects.filter(meal_entry=meal).count(),
        "truncated": True,
        "detail": "Summary only. Use get_meal with item_limit/item_offset for complete item pages. If a single item exceeds the budget, review full details in MacroMapper before editing.",
    }


def list_meals(queryset, owner, limit, offset):
    queryset = queryset.prefetch_related(None).prefetch_related(
        Prefetch(
            "items",
            queryset=MealItem.objects.select_related(
                "food_version", "food_version__food_item"
            ).order_by("order", "id")[:21],
            to_attr="_mcp_items",
        )
    )
    records = list(queryset[offset : offset + limit + 1])
    bound_related_cache(records, "meals")
    output = []
    for meal in records[:limit]:
        try:
            catalog_state(
                [], {item.food_version_id for item in meal.items.all()}, owner
            )
            page = result(serialize("meals", owner, meal))
            if page["truncated"]:
                raise ValidationError("Incomplete meal.")
            output.append(page["data"])
        except ValidationError:
            output.append(meal_summary(meal))
    while True:
        count = len(output)
        has_more = len(records) > count
        try:
            at_offset_limit = has_more and offset + count > 1000
            if at_offset_limit:
                output[-1] = meal_summary(records[count - 1]) | {
                    "detail": "More diary records exist beyond the MCP offset limit. Review the full day in MacroMapper; this page is not the complete diary.",
                    "pagination_limit_reached": True,
                }
            page = result(
                output,
                has_more=has_more and not at_offset_limit,
                next_offset=offset + count
                if has_more and offset + count <= 1000
                else None,
            )
            page["truncated"] |= any(
                record.get("truncated", False) for record in output
            )
            json_value(page, maximum=65536)
            return page
        except ValidationError:
            if count > 1:
                output = output[: max(1, count // 2)]
                continue
            # Include envelope overhead when a single full meal barely fits.
            output = [meal_summary(records[0])]


def bound_related_cache(records, kind):
    # Sliced prefetch uses to_attr: Django must not subsequently try to filter
    # the already sliced queryset. Existing serializers still read the relation.
    relation = {"meals": "items"}.get(kind)
    if relation:
        for record in records:
            record._prefetched_objects_cache[relation] = getattr(
                record, f"_mcp_{relation}"
            )


def get_record(raw, kind, target_id):
    if kind == "proposals":
        return get_proposal(raw, target_id)
    if kind == "meals":
        return get_meal(raw, target_id)
    token = principal(raw)
    target = get_object_or_404(
        records_for(kind, token.user, retrieve=True), pk=target_id
    )
    catalog_state(
        [target.pk] if kind == "foods" else [],
        [],
        token.user,
    )
    return result(serialize(kind, token.user, target))


def get_meal(raw, target_id, item_limit=20, item_offset=0):
    if (
        type(item_limit) is not int
        or not 1 <= item_limit <= 20
        or type(item_offset) is not int
        or not 0 <= item_offset <= 1000
    ):
        raise ValidationError("Use a valid meal item page.")
    token = principal(raw)
    meal = get_object_or_404(
        meal_services.meals_for(token.user).prefetch_related(None), pk=target_id
    )
    serializer = MealEntrySerializer(meal, context={"actor": token.user})
    serializer.fields.pop("items")
    output = dict(serializer.data)
    items_query = (
        MealItem.objects.filter(meal_entry=meal)
        .select_related("food_version", "food_version__food_item")
        .order_by("order", "id")
    )
    total = items_query.count()
    items = list(items_query[item_offset : item_offset + item_limit])
    output.update(item_count=total, item_offset=item_offset)
    while True:
        next_offset = item_offset + len(items)
        has_more = next_offset < total
        if has_more and next_offset > 1000:
            return result(
                meal_summary(meal)
                | {
                    "item_offset": item_offset,
                    "pagination_limit_reached": True,
                    "detail": "More items exist beyond the MCP offset limit. Review the complete saved meal in MacroMapper; this summary is not complete editable data.",
                },
                has_more=False,
                next_offset=None,
            ) | {"truncated": True}
        try:
            catalog_state([], {item.food_version_id for item in items}, token.user)
            output["items"] = MealItemSerializer(
                items, many=True, context={"actor": token.user}
            ).data
            page = result(
                output,
                has_more=has_more,
                next_offset=next_offset if has_more and next_offset <= 1000 else None,
            )
            if page["truncated"]:
                raise ValidationError("Incomplete meal item.")
            json_value(page, maximum=65536)
            return page
        except ValidationError:
            if len(items) > 1:
                items = items[: max(1, len(items) // 2)]
                continue
            return result(
                meal_summary(meal)
                | {
                    "item_offset": item_offset,
                    "item_id": items[0].pk if items else None,
                    "detail": "This meal item or metadata exceeds the MCP detail budget. Review the complete saved meal in MacroMapper. Follow next_offset for later items, but this summary is not complete editable data.",
                },
            ) | {
                "truncated": True,
                "has_more": has_more,
                "next_offset": next_offset if has_more else None,
            }


def proposal_summary(proposal):
    return {
        "id": proposal.pk,
        "name": proposal.name,
        "entry_date": proposal.entry_date,
        "status": proposal.status,
        "generator": proposal.generator,
        "item_count": len(proposal.items),
        "accepted_meal_id": proposal.accepted_meal_id,
        "updated_at": proposal.updated_at,
        "detail": "Read current review items with get_proposal; an estimate is not a diary meal.",
    }


def get_proposal(raw, target_id, item_limit=20, item_offset=0):
    if (
        type(item_limit) is not int
        or not 1 <= item_limit <= 20
        or type(item_offset) is not int
        or not 0 <= item_offset <= 1000
    ):
        raise ValidationError("Use a valid proposal item page.")
    token = principal(raw)
    # Current review items exclude repeated historical snapshots.
    proposal = get_object_or_404(
        proposal_services.proposals_for(token.user).prefetch_related(None), pk=target_id
    )
    serializer = MealProposalSerializer(proposal, context={"actor": token.user})
    serializer.fields.pop("revisions")
    output = dict(serializer.data)
    output.update(
        item_count=len(proposal.items),
        item_offset=item_offset,
        revision_count=proposal.revisions.count(),
        detail="Current review items only. Follow next_offset for the remaining items before editing or accepting. Historical revision snapshots remain available in MacroMapper. Never repeat a paid call to recover detail.",
    )
    items = proposal.items[item_offset : item_offset + item_limit]
    while True:
        output["items"] = items
        next_offset = item_offset + len(items)
        has_more = next_offset < len(proposal.items)
        try:
            page = result(
                output,
                has_more=has_more,
                next_offset=next_offset if has_more else None,
            )
            if page["truncated"]:
                # result() also trims deep trees, long strings and collections.
                # Never expose those partial items as editable review data.
                raise ValidationError("Current review item was truncated.")
            return page
        except ValidationError:
            if len(items) > 1:
                items = items[: max(1, len(items) // 2)]
                continue
            # A single complex item cannot be safely split into editable pieces.
            # Preserve identity and explicitly require full review in the app.
            return {
                "data": json_value(
                    proposal_summary(proposal)
                    | {
                        "item_offset": item_offset,
                        "detail": "This item exceeds the MCP review budget. Open the existing proposal in MacroMapper to review/edit/accept it; do not repeat the paid estimate or treat this summary as complete review data.",
                    }
                ),
                "truncated": True,
                "has_more": has_more,
                "next_offset": None,
            }


def nutrition_totals(raw, start, end):
    token = principal(raw)
    if end < start or (end - start).days > 30:
        raise ValidationError("Choose at most 31 ordered days.")
    meals = list(
        MealEntry.objects.filter(
            owner=token.user, entry_date__range=(start, end)
        ).order_by("pk")[:501]
    )
    if len(meals) > 500 or MealItem.objects.filter(meal_entry__in=meals).count() > 2000:
        raise ValidationError("Too many records; shorten the date range.")
    return result(
        {
            "start": start,
            "end": end,
            "meal_count": len(meals),
            "nutrients": daily_totals(meals),
            "note": "Known nutrient values only; missing values are not zero. No medical advice.",
        }
    )


def snapshot(action, target, user, payload, selected_ids):
    state, food_ids, versions = {}, set(), set()
    if target is not None:
        state["target"] = type(target).objects.filter(pk=target.pk).values().get()
        if isinstance(target, FoodItem):
            food_ids.add(target.pk)
        if isinstance(target, MealEntry):
            items = list(target.items.select_for_update().order_by("pk").values()[:21])
            if len(items) > 20:
                raise ValidationError(
                    "Use the website for meals with more than twenty items."
                )
            state["items"] = items
            versions |= {item["food_version_id"] for item in items}
        if isinstance(target, MealProposal):
            state["revisions"] = list(target.revisions.order_by("pk").values()[:101])
            if len(state["revisions"]) > 100:
                raise ValidationError("Too many proposal revisions for MCP editing.")
    if selected_ids:
        state["notifications"] = list(
            Notification.objects.select_for_update()
            .filter(recipient=user, pk__in=selected_ids)
            .order_by("pk")
            .values()
        )

    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"food_item", "food_item_id"} and type(item) is int:
                    food_ids.add(item)
                elif key in {"food_version", "food_version_id"} and type(item) is int:
                    versions.add(item)
                else:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(payload)
    if isinstance(target, MealProposal):
        collect(target.items)
    state["catalog"] = catalog_state(food_ids, versions, user)
    return hashlib.sha256(
        json.dumps(
            json_value(state, maximum=262144, max_nodes=10000, max_collection=200),
            sort_keys=True,
        ).encode()
    ).hexdigest()
