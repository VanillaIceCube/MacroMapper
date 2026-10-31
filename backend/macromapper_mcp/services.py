"""Closed business operations using the website's serializers/permissions/services.

No caller controls a view, path, model, owner, OAuth identity or provider. Paid
operations consume their approval before waiting on the existing bounded provider.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from types import SimpleNamespace

from django.core.exceptions import PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.db.models import Prefetch
from django.http import QueryDict
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from estimates.models import MealProposal
from estimates.serializers import (
    MapYourMealAdjustmentSerializer,
    MapYourMealDraftSerializer,
    MealProposalFollowUpSerializer,
)
from estimates.views import MealProposalViewSet
from foods.models import FoodComponent, FoodItem, FoodItemVersion, SourceReference
from foods.views import FoodItemViewSet
from meals.models import MealEntry, MealItem
from meals.services import daily_totals
from meals.views import MealEntryViewSet
from notifications.models import Notification
from notifications.views import NotificationViewSet

from .auth import principal
from .models import Confirmation


@dataclass(frozen=True)
class Operation:
    view: type
    method: str
    verb: str
    detail: bool = True
    serializer: type | None = None
    paid: bool = False
    empty: bool = False


OPERATIONS = {
    "food.create": Operation(FoodItemViewSet, "create", "POST", False),
    "food.update": Operation(FoodItemViewSet, "partial_update", "PATCH"),
    "food.archive": Operation(FoodItemViewSet, "destroy", "DELETE", empty=True),
    "meal.create": Operation(MealEntryViewSet, "create", "POST", False),
    "meal.update": Operation(MealEntryViewSet, "partial_update", "PATCH"),
    "meal.delete": Operation(MealEntryViewSet, "destroy", "DELETE", empty=True),
    "meal.draft_create": Operation(
        MealEntryViewSet, "create_draft", "POST", False, MapYourMealDraftSerializer
    ),
    "meal.draft_update": Operation(
        MealEntryViewSet, "update_draft", "PATCH", serializer=MapYourMealDraftSerializer
    ),
    "meal.adjustment": Operation(
        MealEntryViewSet,
        "adjustment",
        "POST",
        serializer=MapYourMealAdjustmentSerializer,
        paid=True,
    ),
    "proposal.estimate": Operation(
        MealProposalViewSet, "create", "POST", False, paid=True
    ),
    "proposal.update": Operation(MealProposalViewSet, "partial_update", "PATCH"),
    "proposal.delete": Operation(MealProposalViewSet, "destroy", "DELETE", empty=True),
    "proposal.accept": Operation(MealProposalViewSet, "accept", "POST", empty=True),
    "proposal.follow_up": Operation(
        MealProposalViewSet,
        "follow_up",
        "POST",
        serializer=MealProposalFollowUpSerializer,
        paid=True,
    ),
    "proposal.adjustment": Operation(
        MealProposalViewSet,
        "create_adjustment",
        "POST",
        False,
        MapYourMealAdjustmentSerializer,
        True,
    ),
    "notification.update": Operation(NotificationViewSet, "partial_update", "PATCH"),
    "notification.delete": Operation(
        NotificationViewSet, "destroy", "DELETE", empty=True
    ),
    "notification.mark_all_read": Operation(
        NotificationViewSet, "mark_all_read", "PATCH", False, empty=True
    ),
    "notification.clear_all": Operation(
        NotificationViewSet, "clear_all", "DELETE", False, empty=True
    ),
}


def json_value(value, *, maximum=32768, max_nodes=2000, max_collection=100):
    """Reject nonfinite/unbounded nested input before serializer or provider work."""
    nodes = 0

    def walk(item, depth=0):
        nonlocal nodes
        nodes += 1
        if (
            nodes > max_nodes
            or depth > 12
            or (isinstance(item, (list, dict)) and len(item) > max_collection)
        ):
            raise ValidationError("Request is too complex; use smaller operations.")
        if isinstance(item, dict):
            for child in item.values():
                walk(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                walk(child, depth + 1)

    walk(value)
    encoded = json.dumps(value, cls=DjangoJSONEncoder, allow_nan=False)
    if len(encoded.encode()) > maximum:
        raise ValidationError("Request is too large; use a narrower result.")
    return json.loads(encoded)


def result(value, **extra):
    truncated = False

    def trim(item, depth=0):
        nonlocal truncated
        if depth > 10:
            truncated = True
            return None
        if isinstance(item, str) and len(item) > 2000:
            truncated = True
            return item[:2000]
        if isinstance(item, (list, tuple)):
            truncated |= len(item) > 20
            return [trim(child, depth + 1) for child in item[:20]]
        if isinstance(item, dict):
            return {key: trim(child, depth + 1) for key, child in item.items()}
        return item

    return {
        "data": json_value(trim(value), maximum=65536),
        "truncated": truncated,
        **extra,
    }


def paid_receipt(action, proposal, *, retained=True, meal_id=None, applied=True):
    """Fixed-size receipt survives an oversized paid result, including temporary builders."""
    return {
        "action": action,
        "proposal_id": proposal.pk if retained else None,
        "temporary_proposal_id": None if retained else proposal.pk,
        "proposal_retained": retained,
        "source_meal_id": meal_id,
        "effect": "proposal_review" if retained else "temporary_adjustment_only",
        "diary_mutated": False,
        "applied": applied,
        "name": proposal.name[:120],
        "entry_date": proposal.entry_date.isoformat(),
        "item_count": len(proposal.items),
        "items": [
            {
                "key": str(item.get("key", ""))[:160],
                "name": str(item.get("name", ""))[:200],
                "servings": str(item.get("servings", ""))[:64],
            }
            for item in proposal.items[:20]
        ],
        "detail": "Result truncated. Retained proposals can be inspected in MacroMapper; temporary adjustments have only this bounded summary. Do not repeat a paid call automatically.",
    }


def paid_result(output, receipt):
    try:
        return result(output)
    except (ValidationError, ValueError, TypeError, OverflowError):
        # All fields in the receipt are fixed, bounded primitives. Never turn a
        # committed paid change into an error merely because its output is large.
        return {"data": receipt, "truncated": True}


def view_for(
    operation, user, payload=None, target_id=None, query=None, selected_ids=None
):
    view = operation.view()
    params = QueryDict(mutable=True)
    params.update(query or {})
    view.request = SimpleNamespace(
        user=user,
        data=payload or {},
        query_params=params,
        method=operation.verb,
        authenticators=(),
        successful_authenticator=None,
    )
    view.kwargs = {"pk": target_id} if operation.detail else {}
    view.args, view.format_kwarg, view.action = (), None, operation.method
    if selected_ids is not None:
        original = view.get_queryset
        view.get_queryset = lambda: original().filter(pk__in=selected_ids)
    view.check_permissions(view.request)
    return view


def target_for(view, operation):
    if not operation.detail:
        return None
    obj = view.get_object()  # Exactly the existing REST ownership/object policy.
    obj = type(obj).objects.select_for_update().get(pk=obj.pk)
    view.check_object_permissions(view.request, obj)
    return obj


def strict_fields(serializer, data):
    if not isinstance(data, dict):
        raise ValidationError("Supply an object.")
    writable = {key for key, field in serializer.fields.items() if not field.read_only}
    if set(data) - writable:
        raise ValidationError("Unknown or read-only fields are not accepted.")
    for key, value in data.items():
        field = serializer.fields[key]
        if isinstance(field, serializers.PrimaryKeyRelatedField) and (
            type(value) is not int or value <= 0
        ):
            raise ValidationError("Identifiers must be positive integers.")
        if isinstance(
            field,
            (
                serializers.IntegerField,
                serializers.DecimalField,
                serializers.FloatField,
            ),
        ) and isinstance(value, bool):
            raise ValidationError("Numbers must not be booleans.")
        if isinstance(field, serializers.ListSerializer):
            if not isinstance(value, list) or len(value) > 20:
                raise ValidationError("Use at most twenty nested items.")
            for item in value:
                strict_fields(field.child, item)
        elif isinstance(field, serializers.Serializer):
            strict_fields(field, value)
        elif field.__class__.__name__ in {
            "ProposalItemsField",
            "MapYourMealItemsField",
        }:
            strict_proposal_items(value)


def strict_proposal_items(items):
    if not isinstance(items, list) or len(items) > 20:
        raise ValidationError("Supply at most twenty proposal items.")
    for item in items:
        if not isinstance(item, dict):
            raise ValidationError("Supply item objects.")
        for key in ("food_item_id", "food_version_id"):
            if item.get(key) is not None and (
                type(item[key]) is not int or item[key] <= 0
            ):
                raise ValidationError("Identifiers must be positive integers.")
        if "is_user_modified" in item and type(item["is_user_modified"]) is not bool:
            raise ValidationError("is_user_modified must be boolean.")
        for source in item.get("sources", []):
            if not isinstance(source, dict) or set(source) - {
                "title",
                "provider",
                "url",
                "accessed_on",
                "is_official",
            }:
                raise ValidationError("Unknown source fields.")
            if "is_official" in source and type(source["is_official"]) is not bool:
                raise ValidationError("is_official must be boolean.")
        strict_proposal_items(item.get("components", []))


def validated(action, view, target, payload):
    operation = OPERATIONS[action]
    if operation.empty:
        if payload:
            raise ValidationError("This action accepts no fields.")
        return None
    if action == "proposal.estimate" and set(payload) - {"description", "entry_date"}:
        raise ValidationError("Estimates accept description and entry_date only.")
    if action == "proposal.update" and "description" in payload:
        raise ValidationError("The original proposal description cannot be edited.")
    if action == "notification.update" and (
        set(payload) != {"is_read"} or type(payload["is_read"]) is not bool
    ):
        raise ValidationError("Supply only a boolean is_read.")
    if action in {"meal.draft_create", "meal.draft_update"} and "notes" not in payload:
        raise ValidationError("Supply notes explicitly; an empty string is allowed.")
    if (
        action in {"meal.draft_create", "meal.draft_update"}
        and not str(payload.get("name", "")).strip()
    ):
        raise ValidationError("Supply the draft meal name explicitly.")
    if action in {
        "meal.create",
        "meal.update",
        "meal.draft_create",
        "meal.draft_update",
    }:
        if not str(payload.get("name", getattr(target, "name", ""))).strip():
            raise ValidationError(
                "Supply a meal name; manual operations never call AI."
            )
    context = view.get_serializer_context()
    context.update(
        meal=target if isinstance(target, MealEntry) else None,
        proposal=target if isinstance(target, MealProposal) else None,
    )
    serializer = (operation.serializer or view.serializer_class)(
        target,
        data=payload,
        partial=operation.method == "partial_update",
        context=context,
    )
    strict_fields(serializer, payload)
    serializer.is_valid(raise_exception=True)
    return serializer


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


@transaction.atomic
def preview_change(raw, action, target_id, payload, authorized_paid=False):
    if action not in OPERATIONS:
        raise ValidationError("Unsupported operation.")
    operation = OPERATIONS[action]
    if type(authorized_paid) is not bool or operation.paid != authorized_paid:
        raise ValidationError("Use the matching paid or nonpaid preview tool.")
    if (operation.detail and (type(target_id) is not int or target_id <= 0)) or (
        not operation.detail and target_id is not None
    ):
        raise ValidationError("Supply the action's exact target identifier.")
    payload = json_value(payload)
    token = principal(raw, write=True, paid=operation.paid, lock=True)
    view = view_for(operation, token.user, payload, target_id)
    target = target_for(view, operation)
    serializer = validated(action, view, target, payload)
    if operation.serializer is MapYourMealAdjustmentSerializer:
        builder_fields(serializer, token.user, target)
    ids = []
    if action in {"notification.mark_all_read", "notification.clear_all"}:
        ids = list(
            Notification.objects.filter(recipient=token.user)
            .order_by("pk")
            .values_list("pk", flat=True)[:201]
        )
        if len(ids) > 200:
            raise ValidationError(
                "Use individual notification operations for more than 200 entries."
            )
    digest = snapshot(action, target, token.user, payload, ids)
    Confirmation.objects.filter(
        owner=token.user, expires_at__lte=timezone.now()
    ).delete()
    if Confirmation.objects.filter(owner=token.user).count() >= 10:
        raise ValidationError("Ten pending confirmations; wait five minutes.")
    pending = Confirmation.objects.create(
        owner=token.user,
        client_id=token.application.client_id,
        token_checksum=token.token_checksum,
        action=action,
        target_id=target_id,
        payload=payload,
        fingerprint=digest,
        selected_ids=ids,
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    current = None
    if action in {"notification.mark_all_read", "notification.clear_all"}:
        current = {"notification_ids": ids, "count": len(ids)}
    if target is not None:
        current = {
            "id": target.pk,
            "name": getattr(target, "name", getattr(target, "title", "")),
            "updated_at": str(getattr(target, "updated_at", "")),
        }
    return {
        "confirmation_id": str(pending.pk),
        "expires_at": pending.expires_at.isoformat(),
        "action": action,
        "target_id": target_id,
        "changes": payload,
        "current": current,
        "paid": operation.paid,
        "instruction": "Show this exact action/target/fields to the user and obtain explicit approval before "
        + ("confirm_paid_change" if operation.paid else "confirm_change")
        + ". Paid actions may call the existing AI provider and create shared catalog/proposal records; they never directly accept a meal. No automatic retry.",
    }


def invoke(operation, view, target_id):
    response = getattr(view, operation.method)(
        view.request, **({"pk": target_id} if operation.detail else {})
    )
    if not 200 <= response.status_code < 300:
        raise ValidationError("Operation unavailable; no automatic retry.")
    return result(response.data)


def builder_fields(serializer, owner, target):
    from estimates.services import prepare_builder_proposal, saved_meal_version_ids

    data = serializer.validated_data
    return prepare_builder_proposal(
        owner=owner,
        entry_date=data["entry_date"],
        name=data.get("name", ""),
        notes=data.get("notes", ""),
        items=data["items"],
        allowed_version_ids=saved_meal_version_ids(target)
        if isinstance(target, MealEntry)
        else (),
    )


def confirm_change(raw, confirmation_id, confirmed, authorized_paid):
    if confirmed is not True:
        raise ValidationError("Explicit user approval is required.")
    with transaction.atomic():
        token = principal(raw, write=True, lock=True)
        pending = (
            Confirmation.objects.select_for_update()
            .filter(
                pk=confirmation_id,
                owner=token.user,
                client_id=token.application.client_id,
                token_checksum=token.token_checksum,
                expires_at__gt=timezone.now(),
            )
            .first()
        )
        if pending is None:
            raise ValidationError("Confirmation unavailable; preview again.")
        operation = OPERATIONS[pending.action]
        if type(authorized_paid) is not bool or operation.paid != authorized_paid:
            raise ValidationError(
                "Use the confirmation tool matching the preview kind."
            )
        token = principal(raw, write=True, paid=operation.paid, lock=True)
        view = view_for(
            operation,
            token.user,
            pending.payload,
            pending.target_id,
            selected_ids=pending.selected_ids
            if pending.action
            in {"notification.mark_all_read", "notification.clear_all"}
            else None,
        )
        target = target_for(view, operation)
        serializer = validated(pending.action, view, target, pending.payload)
        if (
            snapshot(
                pending.action,
                target,
                token.user,
                pending.payload,
                pending.selected_ids,
            )
            != pending.fingerprint
        ):
            raise ValidationError("Target or catalog changed; preview again.")
        prepared = (
            builder_fields(serializer, token.user, target)
            if operation.serializer is MapYourMealAdjustmentSerializer
            else None
        )
        pending.delete()  # Consume once; nonpaid mutation shares this transaction.
        if not operation.paid:
            return {
                "applied": True,
                "action": pending.action,
                "result": invoke(operation, view, pending.target_id),
            }
    # No SQLite writer lock over the provider wait. The approval stays consumed
    # even if a paid call fails or has an ambiguous outcome; never retry it here.
    if connection.in_atomic_block:
        raise ValidationError("Paid operations require an autocommit caller.")
    from estimates.provider import get_estimation_provider
    from estimates.serializers import MealProposalSerializer
    from estimates.services import apply_proposal_follow_up, create_proposal

    def guard():
        current = principal(raw, write=True, paid=True, lock=True)
        if (
            current.user_id != pending.owner_id
            or current.application.client_id != pending.client_id
            or current.token_checksum != pending.token_checksum
        ):
            raise PermissionDenied("MCP confirmation identity changed.")
        fresh_view = view_for(
            operation, current.user, pending.payload, pending.target_id
        )
        fresh_target = target_for(fresh_view, operation)
        if (
            snapshot(pending.action, fresh_target, current.user, pending.payload, [])
            != pending.fingerprint
        ):
            raise ValidationError(
                "State changed during estimation; paid result was not applied. Preview again."
            )
        fresh_serializer = validated(
            pending.action, fresh_view, fresh_target, pending.payload
        )
        return current, fresh_view, fresh_target, fresh_serializer

    if pending.action == "proposal.estimate":
        proposal = create_proposal(
            owner=token.user,
            description=serializer.validated_data["description"],
            entry_date=serializer.validated_data["entry_date"],
            before_apply=guard,
        )
        output = MealProposalSerializer(
            proposal, context={"request": view.request}
        ).data
        receipt = paid_receipt(pending.action, proposal)
    elif pending.action == "proposal.follow_up":
        computed = get_estimation_provider().follow_up(
            original_description=target.description,
            meal_name=serializer.validated_data["name"],
            items=serializer.validated_data["items"],
            follow_up=serializer.validated_data["follow_up"],
        )
        with transaction.atomic():
            current, fresh_view, fresh_target, fresh_serializer = guard()
            outcome = fresh_serializer.apply(computed)
            output = {
                "applied": outcome["applied"],
                "message": outcome["message"],
                "proposal": MealProposalSerializer(
                    outcome["proposal"], context={"request": fresh_view.request}
                ).data,
            }
            receipt = paid_receipt(
                pending.action, outcome["proposal"], applied=outcome["applied"]
            )
    else:
        computed = get_estimation_provider().follow_up(
            original_description="",
            meal_name=prepared["name"],
            items=prepared["items"],
            follow_up=serializer.validated_data["adjustment"],
        )
        with transaction.atomic():
            current, fresh_view, fresh_target, fresh_serializer = guard()
            proposal = fresh_serializer.create_proposal()
            outcome = apply_proposal_follow_up(
                proposal=proposal,
                owner=current.user,
                follow_up=fresh_serializer.validated_data["adjustment"],
                items=proposal.items,
                result=computed,
            )
            output = {
                "applied": outcome["applied"],
                "message": outcome["message"],
                "proposal": MealProposalSerializer(
                    outcome["proposal"], context={"request": fresh_view.request}
                ).data,
            }
            receipt = paid_receipt(
                pending.action,
                outcome["proposal"],
                retained=pending.action != "meal.adjustment",
                meal_id=pending.target_id
                if pending.action == "meal.adjustment"
                else None,
                applied=outcome["applied"],
            )
            if pending.action == "meal.adjustment":
                proposal.delete()  # Match the existing transient adjustment endpoint.
    return {
        "applied": True,
        "action": pending.action,
        "result": paid_result(output, receipt),
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
    classes = {
        "foods": FoodItemViewSet,
        "meals": MealEntryViewSet,
        "proposals": MealProposalViewSet,
        "notifications": NotificationViewSet,
    }
    view = view_for(
        Operation(classes[kind], "list", "GET", False), token.user, query=query
    )
    queryset = view.filter_queryset(view.get_queryset())
    if kind == "notifications" and "is_read" in query:
        queryset = queryset.filter(is_read=query["is_read"] == "true")
    if kind == "proposals" and query.get("status"):
        queryset = queryset.filter(status=query["status"])
    if kind == "proposals":
        # Listing must remain usable after a successful oversized paid result.
        # Do not serialize repeated item snapshots merely to discover its ID.
        queryset = queryset.prefetch_related(None)
    if kind == "meals":
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
    bound_related_cache(records, kind)
    # Guard recursive catalog serialization, including historical meal versions.
    food_ids = [obj.pk for obj in records[:limit]] if kind == "foods" else []
    version_ids = (
        {item.food_version_id for obj in records[:limit] for item in obj.items.all()}
        if kind == "meals"
        else set()
    )
    catalog_state(food_ids, version_ids, token.user)
    return result(
        [proposal_summary(record) for record in records[:limit]]
        if kind == "proposals"
        else view.get_serializer(records[:limit], many=True).data,
        has_more=len(records) > limit,
        next_offset=offset + limit
        if len(records) > limit and offset + limit <= 1000
        else None,
    )


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
    token = principal(raw)
    classes = {
        "foods": FoodItemViewSet,
        "meals": MealEntryViewSet,
        "proposals": MealProposalViewSet,
        "notifications": NotificationViewSet,
    }
    operation = Operation(classes[kind], "retrieve", "GET")
    view = view_for(operation, token.user, target_id=target_id)
    original = view.get_queryset
    if kind == "meals":
        view.get_queryset = lambda: (
            original()
            .prefetch_related(None)
            .prefetch_related(
                Prefetch(
                    "items",
                    queryset=MealItem.objects.select_related(
                        "food_version", "food_version__food_item"
                    ).order_by("order", "id")[:21],
                    to_attr="_mcp_items",
                )
            )
        )
    target = view.get_object()
    bound_related_cache([target], kind)
    catalog_state(
        [target.pk] if kind == "foods" else [],
        {item.food_version_id for item in target.items.all()}
        if kind == "meals"
        else set(),
        token.user,
    )
    return result(view.get_serializer(target).data)


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


def get_proposal(raw, target_id, item_limit=5, item_offset=0):
    if (
        type(item_limit) is not int
        or not 1 <= item_limit <= 20
        or type(item_offset) is not int
        or not 0 <= item_offset <= 1000
    ):
        raise ValidationError("Use a valid proposal item page.")
    token = principal(raw)
    view = view_for(
        Operation(MealProposalViewSet, "retrieve", "GET"),
        token.user,
        target_id=target_id,
    )
    # Only current review items belong in this result. Historical snapshots can
    # multiply an otherwise ordinary mixed meal past the output budget.
    original = view.get_queryset
    view.get_queryset = lambda: original().prefetch_related(None)
    proposal = view.get_object()
    serializer = view.get_serializer(proposal)
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
            return result(
                output,
                has_more=has_more,
                next_offset=next_offset if has_more else None,
            )
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


def operation_schema(raw, action):
    """Complete writable serializer metadata; never inspect a queryset or user data."""
    principal(raw)
    if action not in OPERATIONS:
        raise ValidationError("Unsupported action.")
    operation = OPERATIONS[action]
    serializer = (operation.serializer or operation.view.serializer_class)()

    def describe(field):
        schema = {
            "type": field.__class__.__name__,
            "required": field.required,
            "allow_null": field.allow_null,
        }
        for name in (
            "allow_blank",
            "min_value",
            "max_value",
            "min_length",
            "max_length",
            "max_digits",
            "decimal_places",
        ):
            value = getattr(field, name, None)
            if value is not None:
                schema[name] = str(value) if name.endswith("value") else value
        if getattr(field, "choices", None):
            schema["choices"] = list(field.choices)
        if isinstance(field, serializers.ListSerializer):
            schema.update(max_length=20, items=describe(field.child))
        elif isinstance(field, serializers.Serializer):
            schema["fields"] = {
                key: describe(child)
                for key, child in field.fields.items()
                if not child.read_only
            }
        elif field.__class__.__name__ in {
            "ProposalItemsField",
            "MapYourMealItemsField",
        }:
            from estimates.serializers import ITEM_FIELDS, SOURCE_KINDS
            from foods.nutrients import NUTRIENT_FIELDS

            strings = {
                "key",
                "name",
                "provider_name",
                "serving_label",
                "selected_portion_key",
            }
            decimals = {
                "servings",
                "serving_quantity",
                "serving_weight_grams",
                "serving_volume_ml",
                "confidence_score",
            }
            schema.update(
                max_length=20,
                items={
                    "type": "object",
                    "required": ["key", "name"],
                    "additional_properties": False,
                    "fields": {
                        key: {
                            "type": "string"
                            if key in strings
                            else "finite decimal string"
                            if key in decimals
                            else "positive integer or null"
                            if key.endswith("_id")
                            else "boolean"
                            if key == "is_user_modified"
                            else "array"
                            if key in {"sources", "components", "portion_options"}
                            else "object"
                        }
                        for key in sorted(ITEM_FIELDS)
                    },
                },
            )
            fields = schema["items"]["fields"]
            fields["origin_type"] = {
                "type": "string",
                "choices": list(FoodItem.OriginType.values),
            }
            fields["serving_unit"] = {
                "type": "string",
                "choices": list(FoodItemVersion.ServingUnit.values),
            }
            fields["provenance"] = {
                "type": "string",
                "choices": list(FoodItemVersion.Provenance.values),
            }
            fields["source_kind"] = {"type": "string", "choices": sorted(SOURCE_KINDS)}
            fields["nutrients"] = {
                "type": "object",
                "fields": {
                    key: "nonnegative finite decimal string or null"
                    for key in NUTRIENT_FIELDS
                },
            }
            fields["sources"] = {
                "type": "array",
                "max_length": 20,
                "items": {
                    "title": "required string <=200",
                    "provider": "string <=160",
                    "url": "required HTTP(S) URL",
                    "accessed_on": "ISO date or null",
                    "is_official": "boolean",
                },
            }
            fields["portion_options"] = {
                "type": "array",
                "max_length": 12,
                "items": {
                    "key": "unique required string",
                    "label": "required string",
                    "unit_label": "required string",
                    "serving_multiplier": "positive finite decimal string",
                },
            }
            fields["components"] = {
                "type": "array",
                "max_length": 20,
                "items": "same item schema recursively; at most five levels",
            }
            schema["constraints"] = (
                "Catalog IDs must be paired and visible; edits retain existing provenance. Choose selected_portion_key from portion_options. No unknown fields."
            )
        return schema

    fields = (
        {}
        if operation.empty
        else {
            key: describe(field)
            for key, field in serializer.fields.items()
            if not field.read_only
        }
    )
    if action == "proposal.estimate":
        fields = {
            key: value
            for key, value in fields.items()
            if key in {"description", "entry_date"}
        }
    if action == "proposal.update":
        fields.pop("description", None)
    if operation.method == "partial_update":
        for field in fields.values():
            field["required"] = False
    if action == "notification.update":
        fields["is_read"]["required"] = True
    if action in {"meal.create", "meal.draft_create", "meal.draft_update"}:
        fields["name"].update(required=True, allow_blank=False)
    if action == "food.create":
        fields["definition"]["required"] = True
    if action in {"meal.draft_create", "meal.draft_update"}:
        fields["notes"]["required"] = True
    return result(
        {
            "action": action,
            "target_id_required": operation.detail,
            "fields": fields,
            "requires_confirmation": True,
            "paid": operation.paid,
            "scope": ["macromapper:read", "macromapper:write"]
            + (["macromapper:estimate"] if operation.paid else []),
            "input_budget": "32KiB, at most20 items; use only listed writable fields. Confirmation expires5min and is one-use for the same OAuth token/client/user.",
        }
    )
