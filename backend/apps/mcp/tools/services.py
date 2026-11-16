"""Trusted app approval and durable, scope-bound MCP execution."""

import hashlib
import json
import logging
from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.estimates.serializers import MapYourMealAdjustmentSerializer
from apps.notifications import services as notification_services

from . import operations, queries
from .models import Confirmation, Execution
from .permissions import ESTIMATE, READ, WRITE, lock_actor, principal
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


def _digest(action, target_id, payload):
    return hashlib.sha256(
        json.dumps(
            {"action": action, "target_id": target_id, "payload": payload},
            sort_keys=True,
        ).encode()
    ).hexdigest()


def _outcome(record, *, replayed):
    if record.state == Execution.State.COMPLETED:
        return dict(record.outcome, replayed=replayed)
    if record.state in {Execution.State.CANCELLED, Execution.State.EXPIRED}:
        return {
            "request_id": str(record.pk),
            "action": record.action,
            "status": record.state,
            "applied": False,
            "replayed": replayed,
            "result": {
                "data": {
                    "detail": "This action was cancelled, changed or expired. It cannot execute. Prepare a new action and review it in MacroMapper if still wanted."
                },
                "truncated": False,
            },
        }
    return _pending(record, replayed=replayed)


def _close(record, state):
    record.state = state
    record.save(update_fields=["state", "updated_at"])
    Confirmation.objects.filter(pk=record.confirmation_id).delete()
    return _outcome(record, replayed=False)


def _preparation(record):
    pending = (
        Confirmation.objects.select_for_update()
        .filter(pk=record.confirmation_id)
        .first()
    )
    if pending is None or pending.expires_at <= timezone.now():
        _close(record, Execution.State.EXPIRED)
        return None
    if (
        pending.owner_id != record.owner_id
        or pending.client_id != record.client_id
        or pending.action != record.action
        or pending.target_id != record.target_id
        or _digest(pending.action, pending.target_id, pending.payload)
        != record.request_digest
    ):
        _close(record, Execution.State.CANCELLED)
        return None
    return pending


def _fresh(record, pending, user):
    operation = operations.OPERATIONS[record.action]
    target = queries.target_for(operation, user, record.target_id)
    if (
        queries.snapshot(
            record.action, target, user, pending.payload, pending.selected_ids
        )
        != pending.fingerprint
    ):
        _close(record, Execution.State.CANCELLED)
        return None
    serializer = operations.validated(record.action, user, target, pending.payload)
    operations.validate_draft(record.action, serializer, user, target)
    return target, serializer


def _prepared(record, pending, *, replayed):
    return json_value(
        {
            "request_id": str(record.pk),
            "action": record.action,
            "status": record.state,
            "applied": False,
            "replayed": replayed,
            "result": {
                "data": {
                    "confirmation_id": str(pending.pk),
                    "approval_url": settings.FRONTEND_BASE_URL.rstrip("/")
                    + "/connections/authorize?approval_id="
                    + str(pending.pk),
                    "expires_at": pending.expires_at.isoformat(),
                    "target_id": pending.target_id,
                    "changes": pending.payload,
                    "paid": operations.OPERATIONS[pending.action].paid,
                    "detail": "Open the approval URL and explicitly approve this exact action while signed in to MacroMapper. MCP bearer tokens cannot approve it. Then call the matching confirm tool with the same request and confirmation IDs; never automatically resubmit paid work under a new request ID.",
                },
                "truncated": False,
            },
        },
        maximum=65536,
    )


def _owned(record, token):
    if (
        record.owner_id != token.user_id
        or record.client_id != token.application.client_id
    ):
        raise PermissionDenied("Execution unavailable for this connection.")


def execute_change(raw, request_id, action, target_id, payload, authorized_paid=False):
    """Execute a non-removal; paid work reserves before its provider wait."""
    request_id = _request_id(request_id)
    operation = operations.OPERATIONS.get(action)
    payload = json_value(payload)
    if not isinstance(payload, dict) or operations.requires_approval(action, payload):
        raise operations.OperationError(
            "This action requires preparation and signed-in app approval."
        )
    if (
        operation is None
        or type(authorized_paid) is not bool
        or operation.paid != authorized_paid
    ):
        raise ValidationError("Use the matching paid or nonpaid execution tool.")
    if (operation.detail and (type(target_id) is not int or target_id <= 0)) or (
        not operation.detail and target_id is not None
    ):
        raise ValidationError("Supply the action's exact target identifier.")
    digest = _digest(action, target_id, payload)
    outer_transaction = connection.in_atomic_block
    with transaction.atomic():
        token = principal(raw, write=True, paid=operation.paid, lock=True)
        record = Execution.objects.select_for_update().filter(pk=request_id).first()
        if record is not None:
            _owned(record, token)
            if record.request_digest != digest:
                raise operations.OperationError(
                    "This request ID belongs to different arguments."
                )
            if record.state not in {Execution.State.PREPARED, Execution.State.APPROVED}:
                return _outcome(record, replayed=True)
            # A client may opt into stronger approval, but cannot then bypass it.
            pending = _preparation(record)
            if pending is None:
                return _outcome(record, replayed=True)
            if pending.token_checksum != token.token_checksum:
                raise PermissionDenied("Preparation belongs to a different token.")
            if _fresh(record, pending, token.user) is None:
                return _outcome(record, replayed=True)
            return _prepared(record, pending, replayed=True)
        target = queries.target_for(operation, token.user, target_id)
        serializer = operations.validated(action, token.user, target, payload)
        operations.validate_draft(action, serializer, token.user, target)
        selected_ids = []
        if action == "notification.mark_all_read":
            selected_ids = list(
                notification_services.notifications_for(token.user)
                .order_by("pk")
                .values_list("pk", flat=True)[:201]
            )
            if len(selected_ids) > 200:
                raise ValidationError(
                    "Use individual notification operations for more than 200 entries."
                )
        # Retain the same live catalog validation and guarded paid publication.
        fingerprint = queries.snapshot(
            action, target, token.user, payload, selected_ids
        )
        prepared = (
            operations.builder_fields(serializer, token.user, target)
            if operation.serializer is MapYourMealAdjustmentSerializer
            else None
        )
        if operation.paid and outer_transaction:
            raise ValidationError("Paid operations require an autocommit caller.")
        record = Execution.objects.create(
            id=request_id,
            owner=token.user,
            client_id=token.application.client_id,
            action=action,
            target_id=target_id,
            request_digest=digest,
            state=Execution.State.IN_PROGRESS,
        )
        if not operation.paid:
            return _complete(
                record,
                operations.invoke(
                    action,
                    operation,
                    token.user,
                    target,
                    serializer,
                    target_id,
                    selected_ids,
                ),
            )
    return _execute_paid(
        raw, record, token, target, serializer, payload, fingerprint, prepared
    )


def prepare_change(raw, request_id, action, target_id, payload, authorized_paid=False):
    """Prepare exactly one action; no business mutation or provider call occurs."""
    request_id = _request_id(request_id)
    operation = operations.OPERATIONS.get(action)
    if operation is None:
        raise ValidationError("Unsupported operation.")
    if type(authorized_paid) is not bool or operation.paid != authorized_paid:
        raise ValidationError("Use the matching paid or nonpaid preparation tool.")
    if (operation.detail and (type(target_id) is not int or target_id <= 0)) or (
        not operation.detail and target_id is not None
    ):
        raise ValidationError("Supply the action's exact target identifier.")
    payload = json_value(payload)
    digest = _digest(action, target_id, payload)
    with transaction.atomic():
        token = principal(raw, write=True, paid=operation.paid, lock=True)
        record = Execution.objects.select_for_update().filter(pk=request_id).first()
        if record is not None:
            _owned(record, token)
            if record.request_digest != digest:
                raise operations.OperationError(
                    "This request ID belongs to different arguments. Keep the original ID and arguments when recovering an outcome."
                )
            if record.state not in {Execution.State.PREPARED, Execution.State.APPROVED}:
                return _outcome(record, replayed=True)
            pending = _preparation(record)
            if pending is None:
                return _outcome(record, replayed=True)
            if pending.token_checksum != token.token_checksum:
                raise PermissionDenied("Preparation belongs to a different token.")
            if _fresh(record, pending, token.user) is None:
                return _outcome(record, replayed=True)
            return _prepared(record, pending, replayed=True)
        target = queries.target_for(operation, token.user, target_id)
        serializer = operations.validated(action, token.user, target, payload)
        if operation.serializer is MapYourMealAdjustmentSerializer:
            operations.builder_fields(serializer, token.user, target)
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
        expired = Confirmation.objects.filter(
            owner=token.user, expires_at__lte=timezone.now()
        )
        Execution.objects.filter(
            confirmation_id__in=expired.values("pk"),
            state__in=[Execution.State.PREPARED, Execution.State.APPROVED],
        ).update(state=Execution.State.EXPIRED)
        expired.delete()
        if Confirmation.objects.filter(owner=token.user).count() >= 10:
            raise operations.OperationError(
                "Ten pending actions; cancel one in MacroMapper or wait five minutes."
            )
        record = Execution.objects.create(
            id=request_id,
            owner=token.user,
            client_id=token.application.client_id,
            action=action,
            target_id=target_id,
            request_digest=digest,
        )
        pending = Confirmation.objects.create(
            id=record.confirmation_id,
            owner=token.user,
            client_id=record.client_id,
            token_checksum=token.token_checksum,
            action=action,
            target_id=target_id,
            payload=payload,
            fingerprint=fingerprint,
            selected_ids=selected_ids,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        return _prepared(record, pending, replayed=False)


def action_approval(user, reference, decision=None):
    """Called only by the framework's JWT-authenticated, ticket-bound app view."""
    from django.http import Http404
    from oauth2_provider.models import AccessToken

    with transaction.atomic():
        lock_actor(user)
        record = (
            Execution.objects.select_for_update()
            .filter(owner=user, confirmation_id=reference)
            .first()
        )
        if record is None:
            raise Http404
        operation = operations.OPERATIONS[record.action]
        base = {
            "status": record.state,
            "action": record.action,
            "target_id": record.target_id,
            "paid": operation.paid,
        }
        if record.state not in {Execution.State.PREPARED, Execution.State.APPROVED}:
            return base
        pending = _preparation(record)
        if pending is None:
            return dict(base, status=record.state)
        token = (
            AccessToken.objects.select_related("user", "application")
            .select_for_update()
            .filter(token_checksum=pending.token_checksum, user=user)
            .first()
        )
        required = {READ, WRITE} | ({ESTIMATE} if operation.paid else set())
        if (
            token is None
            or not token.is_valid()
            or not token.user.is_active
            or token.resource != [settings.MCP_RESOURCE_URL]
            or token.application is None
            or token.application.client_id != record.client_id
            or token.application.authorization_grant_type != "authorization-code"
            or not required <= set(token.scope.split())
        ):
            raise PermissionDenied("This action's connection is no longer authorized.")
        fresh = _fresh(record, pending, user)
        if fresh is None:
            return dict(base, status=record.state)
        target, _ = fresh
        if decision == "cancel":
            _close(record, Execution.State.CANCELLED)
            return dict(base, status=record.state)
        if decision == "allow":
            record.state = Execution.State.APPROVED
            record.save(update_fields=["state", "updated_at"])
        elif decision is not None:
            raise ValidationError("Invalid approval decision.")
        # Display the full bound state, including selected notifications and catalog
        # definitions. Never authorize against a truncated read-tool summary.
        current = queries.snapshot(
            record.action,
            target,
            user,
            pending.payload,
            pending.selected_ids,
            details=True,
        )
        return json_value(
            dict(
                base,
                status=record.state,
                application={
                    "name": token.application.name,
                    "client_id": record.client_id,
                },
                user={"username": user.get_username()},
                changes=pending.payload,
                current=current,
                expires_at=pending.expires_at.isoformat(),
                destructive=(
                    operations.requires_approval(record.action, pending.payload)
                    and not operation.paid
                ),
            ),
            maximum=327680,
            max_nodes=13000,
            max_collection=200,
        )


def confirm_change(raw, request_id, confirmation_id, authorized_paid=False):
    """Consume a live app-approved action once; a bearer cannot approve it."""
    request_id, confirmation_id = _request_id(request_id), _request_id(confirmation_id)
    if type(authorized_paid) is not bool:
        raise ValidationError("Use the matching confirmation tool.")
    outer_transaction = connection.in_atomic_block
    with transaction.atomic():
        token = principal(raw, write=True, paid=authorized_paid, lock=True)
        record = Execution.objects.select_for_update().filter(pk=request_id).first()
        if record is None:
            raise operations.OperationError(
                "Prepare and approve this action in MacroMapper first."
            )
        _owned(record, token)
        operation = operations.OPERATIONS[record.action]
        if (
            operation.paid != authorized_paid
            or record.confirmation_id != confirmation_id
        ):
            raise operations.OperationError(
                "Use the matching confirmation tool and original identifiers."
            )
        if record.state not in {Execution.State.PREPARED, Execution.State.APPROVED}:
            return _outcome(record, replayed=True)
        pending = _preparation(record)
        if pending is None:
            return _outcome(record, replayed=False)
        if pending.token_checksum != token.token_checksum:
            raise PermissionDenied("Preparation belongs to a different token.")
        fresh = _fresh(record, pending, token.user)
        if fresh is None:
            return _outcome(record, replayed=False)
        if record.state != Execution.State.APPROVED:
            return _prepared(record, pending, replayed=True)
        if operation.paid and outer_transaction:
            raise ValidationError("Paid operations require an autocommit caller.")
        target, serializer = fresh
        action, target_id, payload = record.action, record.target_id, pending.payload
        fingerprint = pending.fingerprint
        prepared = (
            operations.builder_fields(serializer, token.user, target)
            if operation.serializer is MapYourMealAdjustmentSerializer
            else None
        )
        record.state = Execution.State.IN_PROGRESS
        record.save(update_fields=["state", "updated_at"])
        pending.delete()
        if not operation.paid:
            return _complete(
                record,
                operations.invoke(
                    action,
                    operation,
                    token.user,
                    target,
                    serializer,
                    target_id,
                    pending.selected_ids,
                ),
            )

    return _execute_paid(
        raw, record, token, target, serializer, payload, fingerprint, prepared
    )


def _execute_paid(
    raw, record, token, target, serializer, payload, fingerprint, prepared
):
    """Shared one-use paid execution after either direct reservation or approval."""
    action, target_id = record.action, record.target_id
    operation = operations.OPERATIONS[action]

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
