"""Explicit action metadata, writable-field discovery and mutation validation."""

from dataclasses import dataclass

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.estimates import services as proposal_services
from apps.estimates.models import MealProposal
from apps.estimates.serializers import (
    MapYourMealAdjustmentSerializer,
    MapYourMealDraftSerializer,
    MealProposalFollowUpSerializer,
    MealProposalSerializer,
)
from apps.foods import services as food_services
from apps.foods.models import FoodItem, FoodItemVersion
from apps.foods.serializers import FoodItemSerializer
from apps.meals import services as meal_services
from apps.meals.models import MealEntry
from apps.meals.serializers import MealEntrySerializer
from apps.notifications import services as notification_services
from apps.notifications.serializers import NotificationSerializer

from .permissions import principal
from .queries import serialize
from .results import json_value, paid_receipt, paid_result, result


class OperationError(ValidationError):
    """Only fixed, app-authored guidance may cross the sanitized tool boundary."""

    def __init__(self, guidance):
        self.guidance = guidance
        super().__init__(guidance)


@dataclass(frozen=True)
class Operation:
    kind: str
    method: str
    serializer: type
    detail: bool = True
    paid: bool = False
    empty: bool = False


OPERATIONS = {
    "food.create": Operation(
        "foods", "create", FoodItemSerializer, detail=False, paid=False, empty=False
    ),
    "food.update": Operation(
        "foods",
        "partial_update",
        FoodItemSerializer,
        detail=True,
        paid=False,
        empty=False,
    ),
    "food.archive": Operation(
        "foods", "destroy", FoodItemSerializer, detail=True, paid=False, empty=True
    ),
    "meal.create": Operation(
        "meals", "create", MealEntrySerializer, detail=False, paid=False, empty=False
    ),
    "meal.update": Operation(
        "meals",
        "partial_update",
        MealEntrySerializer,
        detail=True,
        paid=False,
        empty=False,
    ),
    "meal.delete": Operation(
        "meals", "destroy", MealEntrySerializer, detail=True, paid=False, empty=True
    ),
    "meal.draft_create": Operation(
        "meals",
        "create_draft",
        MapYourMealDraftSerializer,
        detail=False,
        paid=False,
        empty=False,
    ),
    "meal.draft_update": Operation(
        "meals",
        "update_draft",
        MapYourMealDraftSerializer,
        detail=True,
        paid=False,
        empty=False,
    ),
    "meal.adjustment": Operation(
        "meals",
        "adjustment",
        MapYourMealAdjustmentSerializer,
        detail=True,
        paid=True,
        empty=False,
    ),
    "proposal.estimate": Operation(
        "proposals",
        "create",
        MealProposalSerializer,
        detail=False,
        paid=True,
        empty=False,
    ),
    "proposal.update": Operation(
        "proposals",
        "partial_update",
        MealProposalSerializer,
        detail=True,
        paid=False,
        empty=False,
    ),
    "proposal.delete": Operation(
        "proposals",
        "destroy",
        MealProposalSerializer,
        detail=True,
        paid=False,
        empty=True,
    ),
    "proposal.accept": Operation(
        "proposals",
        "accept",
        MealProposalSerializer,
        detail=True,
        paid=False,
        empty=True,
    ),
    "proposal.follow_up": Operation(
        "proposals",
        "follow_up",
        MealProposalFollowUpSerializer,
        detail=True,
        paid=True,
        empty=False,
    ),
    "proposal.adjustment": Operation(
        "proposals",
        "create_adjustment",
        MapYourMealAdjustmentSerializer,
        detail=False,
        paid=True,
        empty=False,
    ),
    "notification.update": Operation(
        "notifications",
        "partial_update",
        NotificationSerializer,
        detail=True,
        paid=False,
        empty=False,
    ),
    "notification.delete": Operation(
        "notifications",
        "destroy",
        NotificationSerializer,
        detail=True,
        paid=False,
        empty=True,
    ),
    "notification.mark_all_read": Operation(
        "notifications",
        "mark_all_read",
        NotificationSerializer,
        detail=False,
        paid=False,
        empty=True,
    ),
    "notification.clear_all": Operation(
        "notifications",
        "clear_all",
        NotificationSerializer,
        detail=False,
        paid=False,
        empty=True,
    ),
}


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
                "evidence",
            }:
                raise ValidationError("Unknown source fields.")
            if "is_official" in source and type(source["is_official"]) is not bool:
                raise ValidationError("is_official must be boolean.")
        strict_proposal_items(item.get("components", []))


def validated(action, actor, target, payload):
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
    context = {"actor": actor}
    context.update(
        meal=target if isinstance(target, MealEntry) else None,
        proposal=target if isinstance(target, MealProposal) else None,
    )
    serializer = operation.serializer(
        target,
        data=payload,
        partial=operation.method == "partial_update",
        context=context,
    )
    strict_fields(serializer, payload)
    serializer.is_valid(raise_exception=True)
    return serializer


def validate_draft(action, serializer, owner, target):
    if action not in {"meal.draft_create", "meal.draft_update"}:
        return
    # The JSON field validates shape, not catalog authorization. After snapshot
    # bounds catalog expansion, run save_meal_draft's pure builder validation.
    # Never materialize foods or proposals before execution.

    try:
        builder_fields(serializer, owner, target)
    except DjangoValidationError:
        raise OperationError(
            "Draft items must reference visible catalog foods and matching components. "
            "For a manual food, execute food.create first, then use its "
            "food_item_id and food_version_id in a new meal draft operation. "
            "No meal was saved."
        ) from None


def builder_fields(serializer, owner, target):
    from apps.estimates.services import prepare_builder_proposal, saved_meal_version_ids

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


def operation_schema(raw, action):
    """Complete writable serializer metadata; never inspect a queryset or user data."""
    principal(raw)
    if action not in OPERATIONS:
        raise ValidationError("Unsupported action.")
    operation = OPERATIONS[action]
    serializer = operation.serializer()
    natural_servings_schema = {
        "type": "array",
        "max_length": 12,
        "items": {
            "key": "unique required string matching [a-z][a-z0-9_-]{0,30}",
            "label": "required nonblank string <=80; no markup, controls or URLs",
            "weight_grams": "positive finite decimal string <=100000",
        },
    }

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
        elif (
            isinstance(field, serializers.JSONField)
            and field.field_name == "natural_servings"
        ):
            schema.update(natural_servings_schema)
        elif field.__class__.__name__ in {
            "ProposalItemsField",
            "MapYourMealItemsField",
        }:
            from apps.estimates.serializers import ITEM_FIELDS, SOURCE_KINDS
            from apps.foods.nutrients import NUTRIENT_FIELDS

            strings = {
                "key",
                "name",
                "provider_name",
                "serving_label",
                "selected_portion_key",
                "market",
                "product_identifier",
                "identity_url",
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
                            if key
                            in {
                                "sources",
                                "components",
                                "portion_options",
                                "natural_servings",
                            }
                            else "object"
                        }
                        for key in sorted(ITEM_FIELDS)
                    },
                },
            )
            fields = schema["items"]["fields"]
            fields["natural_servings"] = natural_servings_schema
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
                "max_length": 20,
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
                "Catalog IDs must be paired and visible; edits retain existing provenance. "
                "Meal drafts require catalog-linked items, including components. "
                "For manual foods, separately execute food.create first, then use its catalog IDs. "
                "Choose selected_portion_key from portion_options. No unknown fields."
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
            "requires_confirmation": False,
            "request_id_required": True,
            "request_id_policy": "Generate a UUID automatically for each intended action; reuse the same UUID and exact arguments to recover its outcome. Never ask the user for an ID or an extra approval.",
            "paid": operation.paid,
            "scope": ["macromapper:read", "macromapper:write"]
            + (["macromapper:estimate"] if operation.paid else []),
            "input_budget": "32KiB, at most20 items; use only listed writable fields. A request UUID deduplicates the exact action for its account and OAuth client; retries never repeat paid work.",
        }
    )


def invoke(action, operation, actor, target, serializer, target_id, selected_ids):
    # Both transports call these actor-scoped operations with validated fields.
    data = serializer.validated_data if serializer is not None else {}
    try:
        if action == "food.create":
            output = serialize(
                "foods", actor, food_services.create_personal_food(actor, data)
            )
        elif action == "food.update":
            output = serialize(
                "foods", actor, food_services.update_personal_food(actor, target, data)
            )
        elif action == "food.archive":
            food_services.archive_personal_food(actor, target)
            output = None
        elif action == "meal.create":
            output = serialize("meals", actor, meal_services.create_meal(actor, data))
        elif action == "meal.update":
            output = serialize(
                "meals", actor, meal_services.update_meal(actor, target, data)
            )
        elif action == "meal.delete":
            meal_services.delete_meal(actor, target)
            output = None
        elif action in {"meal.draft_create", "meal.draft_update"}:
            output = serialize(
                "meals", actor, proposal_services.save_draft(actor, data, target)
            )
        elif action == "proposal.update":
            output = serialize(
                "proposals",
                actor,
                proposal_services.update_proposal(actor, target, data),
            )
        elif action == "proposal.delete":
            proposal_services.delete_proposal(actor, target)
            output = None
        elif action == "proposal.accept":
            output = serialize(
                "meals",
                actor,
                proposal_services.accept_reviewed_proposal(actor, target),
            )
        elif action == "notification.update":
            output = serialize(
                "notifications",
                actor,
                notification_services.update_notification(actor, target, data),
            )
        elif action == "notification.delete":
            notification_services.delete_notification(actor, target)
            output = None
        elif action == "notification.mark_all_read":
            output = {
                "updated": notification_services.mark_all_read(actor, selected_ids)
            }
        elif action == "notification.clear_all":
            output = {"deleted": notification_services.clear_all(actor, selected_ids)}
        else:
            raise ValidationError("Operation unavailable; no automatic retry.")
    except DjangoValidationError as error:
        if action in {"meal.draft_create", "meal.draft_update", "proposal.accept"}:
            raise ValidationError(error.messages) from error
        raise
    # Formatting failures after a successful mutation retain the bounded receipt.
    try:
        formatted = result(output)
        if not formatted["truncated"]:
            json_value(formatted, maximum=65536)
            return formatted
    except (ValidationError, ValueError, TypeError, OverflowError):
        # Only representation failed; the bounded receipt below reports success.
        pass
    kind = "meal" if action == "proposal.accept" else action.split(".")[0]
    record_id = output.get("id", target_id) if isinstance(output, dict) else target_id
    if type(record_id) is not int:
        record_id = target_id
    return {
        "data": {
            "id": record_id,
            "action": action,
            "target_id": target_id,
            "applied": True,
            "detail": f"Change applied once. Expanded output exceeded the MCP budget. Read the existing record with get_{kind} or review it in MacroMapper; do not repeat the mutation to recover detail.",
        },
        "truncated": True,
    }


def invoke_paid(
    action, token, target, serializer, target_id, prepared, guard, complete
):
    """Wait without a writer lock, then guard and persist business work + receipt."""
    from apps.estimates.provider import get_estimation_provider
    from apps.estimates.services import apply_proposal_follow_up

    if action == "proposal.estimate":

        def persist(proposal):
            output = MealProposalSerializer(
                proposal, context={"actor": token.user}
            ).data
            receipt = paid_receipt(action, proposal)
            return complete(paid_result(output, receipt), receipt)

        proposal_services.estimate_proposal(
            token.user,
            serializer.validated_data,
            before_apply=guard,
            after_apply=persist,
        )
    elif action == "proposal.follow_up":
        computed = get_estimation_provider().follow_up(
            original_description=target.description,
            meal_name=serializer.validated_data["name"],
            items=serializer.validated_data["items"],
            follow_up=serializer.validated_data["follow_up"],
        )
        with transaction.atomic():
            current, fresh_target, fresh_serializer = guard()
            outcome = proposal_services.apply_follow_up(
                current.user, fresh_target, fresh_serializer.validated_data, computed
            )
            output = {
                "applied": outcome["applied"],
                "message": outcome["message"],
                "proposal": MealProposalSerializer(
                    outcome["proposal"], context={"actor": current.user}
                ).data,
            }
            receipt = paid_receipt(
                action, outcome["proposal"], applied=outcome["applied"]
            )
            complete(paid_result(output, receipt), receipt)
    else:
        computed = get_estimation_provider().follow_up(
            original_description="",
            meal_name=prepared["name"],
            items=prepared["items"],
            follow_up=serializer.validated_data["adjustment"],
        )
        with transaction.atomic():
            current, fresh_target, fresh_serializer = guard()
            proposal = proposal_services.build_adjustment_proposal(
                current.user,
                fresh_serializer.validated_data,
                fresh_target if isinstance(fresh_target, MealEntry) else None,
            )
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
                    outcome["proposal"], context={"actor": current.user}
                ).data,
            }
            receipt = paid_receipt(
                action,
                outcome["proposal"],
                retained=action != "meal.adjustment",
                meal_id=target_id if action == "meal.adjustment" else None,
                applied=outcome["applied"],
            )
            if action == "meal.adjustment":
                proposal.delete()  # Match the existing transient adjustment endpoint.
            complete(paid_result(output, receipt), receipt)
