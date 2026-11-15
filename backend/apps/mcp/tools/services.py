"""Authenticated execution and automatic duplicate protection for MCP requests."""

import hashlib
import json
import logging
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from rest_framework.exceptions import ValidationError

from apps.estimates.serializers import MapYourMealAdjustmentSerializer
from apps.notifications import services as notification_services

from . import operations, queries
from .models import Execution
from .permissions import principal
from .results import json_value

logger = logging.getLogger(__name__)


def read(raw, operation, *arguments):
    """Only the registry can select one of these read-only query functions."""
    query = {
        "operation_schema": operations.operation_schema,
        "list_records": queries.list_records,
        "get_record": queries.get_record,
        "get_meal": queries.get_meal,
        "get_proposal": queries.get_proposal,
        "nutrition_totals": queries.nutrition_totals,
    }[operation]
    return query(raw, *arguments)


def _request_id(value):
    try:
        if not isinstance(value, str):
            raise ValueError
        return UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise operations.OperationError(
            "Supply a generated request UUID; keep it unchanged when recovering the same operation."
        ) from None


def _pending(record, *, replayed):
    return {
        "request_id": str(record.pk),
        "action": record.action,
        "status": record.state,
        "applied": None,
        "replayed": replayed,
        "result": {
            "data": {
                "detail": "This request is running or its outcome is uncertain. It will not be executed again. Inspect current records; reuse this same request ID to recover its outcome, and never retry paid work under a new ID automatically."
            },
            "truncated": False,
        },
    }


def _complete(record, output, receipt=None):
    outcome = {
        "request_id": str(record.pk),
        "action": record.action,
        "status": Execution.State.COMPLETED,
        "applied": receipt.get("applied", True) if receipt else True,
        "replayed": False,
        "result": output,
    }
    try:
        outcome = json_value(outcome, maximum=65536)
    except (ValidationError, ValueError, TypeError, OverflowError):
        data = output.get("data")
        record_id = data.get("id") if isinstance(data, dict) else record.target_id
        outcome["result"] = {
            "data": receipt
            or {
                "id": record_id,
                "action": record.action,
                "applied": True,
                "detail": "Change completed. Inspect the existing record in MacroMapper for full details; do not repeat the mutation.",
            },
            "truncated": True,
        }
        outcome = json_value(outcome, maximum=65536)
    record.state, record.outcome = Execution.State.COMPLETED, outcome
    record.save(update_fields=["state", "outcome", "updated_at"])
    return outcome


def execute_change(raw, request_id, action, target_id, payload, authorized_paid=False):
    """Execute once without an approval round-trip; recover duplicate outcomes."""
    request_id = _request_id(request_id)
    operation = operations.OPERATIONS.get(action)
    if operation is None:
        raise ValidationError("Unsupported operation.")
    if type(authorized_paid) is not bool or operation.paid != authorized_paid:
        raise ValidationError("Use the matching paid or nonpaid execution tool.")
    if (operation.detail and (type(target_id) is not int or target_id <= 0)) or (
        not operation.detail and target_id is not None
    ):
        raise ValidationError("Supply the action's exact target identifier.")
    outer_transaction = connection.in_atomic_block
    payload = json_value(payload)
    digest = hashlib.sha256(
        json.dumps(
            {"action": action, "target_id": target_id, "payload": payload},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    with transaction.atomic():
        token = principal(raw, write=True, paid=operation.paid, lock=True)
        if operation.paid and outer_transaction:
            raise ValidationError("Paid operations require an autocommit caller.")
        record = Execution.objects.select_for_update().filter(pk=request_id).first()
        if record is not None:
            if (
                record.owner_id != token.user_id
                or record.client_id != token.application.client_id
            ):
                raise PermissionDenied("Execution unavailable for this connection.")
            if record.request_digest != digest:
                raise operations.OperationError(
                    "This request ID belongs to different arguments. Keep the original ID and arguments when recovering an outcome."
                )
            # A completed delete has no surviving target. Receipt ownership and
            # current OAuth identity/scopes authorize replay, not target existence.
            if record.state == Execution.State.COMPLETED:
                return dict(record.outcome, replayed=True)
            return _pending(record, replayed=True)
        target = queries.target_for(operation, token.user, target_id)
        serializer = operations.validated(action, token.user, target, payload)
        prepared = (
            operations.builder_fields(serializer, token.user, target)
            if operation.serializer is MapYourMealAdjustmentSerializer
            else None
        )
        selected_ids = []
        if action in {"notification.mark_all_read", "notification.clear_all"}:
            selected_ids = list(
                notification_services.notifications_for(token.user)
                .order_by("pk")
                .values_list("pk", flat=True)[:201]
            )
            if len(selected_ids) > 200:
                raise ValidationError(
                    "Use individual notification operations for more than 200 entries."
                )
        fingerprint = queries.snapshot(
            action, target, token.user, payload, selected_ids
        )
        operations.validate_draft(action, serializer, token.user, target)
        record = Execution.objects.create(
            id=request_id,
            owner=token.user,
            client_id=token.application.client_id,
            action=action,
            target_id=target_id,
            request_digest=digest,
        )
        if not operation.paid:
            output = operations.invoke(
                action,
                operation,
                token.user,
                target,
                serializer,
                target_id,
                selected_ids,
            )
            return _complete(record, output)

    # Reservation is durable before the provider wait. A retry or crashed worker
    # cannot invoke the provider again for this UUID. No writer lock spans I/O.
    def guard():
        current = principal(raw, write=True, paid=True, lock=True)
        if (
            current.user_id != record.owner_id
            or current.application.client_id != record.client_id
            or current.token_checksum != token.token_checksum
        ):
            raise PermissionDenied("Execution identity changed.")
        fresh = queries.target_for(operation, current.user, target_id)
        if queries.snapshot(action, fresh, current.user, payload, []) != fingerprint:
            raise operations.OperationError(
                "Target or catalog changed during estimation; no paid result was applied. Inspect current records before requesting another operation."
            )
        return (
            current,
            fresh,
            operations.validated(action, current.user, fresh, payload),
        )

    try:
        operations.invoke_paid(
            action,
            token,
            target,
            serializer,
            target_id,
            prepared,
            guard,
            lambda output, receipt: _complete(record, output, receipt),
        )
    except Exception as error:
        # Domain write transactions roll back with receipt persistence. Keep the
        # consumed reservation even for ambiguous provider/connection failures.
        Execution.objects.filter(
            pk=record.pk, state=Execution.State.IN_PROGRESS
        ).update(state=Execution.State.UNCERTAIN)
        logger.warning("MCP paid execution stopped category=%s", type(error).__name__)
        raise
    return record.outcome
