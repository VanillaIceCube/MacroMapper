"""Recipient-scoped notification operations shared by REST and MCP."""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .models import Notification


def notifications_for(actor, selected_ids=None):
    rows = (
        Notification.objects.filter(recipient=actor)
        .select_related("actor")
        .order_by("-created_at", "-id")
    )
    return rows if selected_ids is None else rows.filter(pk__in=selected_ids)


def require_recipient(actor, notification):
    if not notifications_for(actor).filter(pk=notification.pk).exists():
        raise PermissionDenied("Notification unavailable.")


@transaction.atomic
def update_notification(actor, notification, data):
    notification = Notification.objects.select_for_update().get(pk=notification.pk)
    require_recipient(actor, notification)
    if "is_read" in data:
        notification.is_read = data["is_read"]
        if notification.is_read and not notification.read_at:
            notification.read_at = timezone.now()
        elif not notification.is_read:
            notification.read_at = None
    notification.save()
    return notification


@transaction.atomic
def delete_notification(actor, notification):
    notification = Notification.objects.select_for_update().get(pk=notification.pk)
    require_recipient(actor, notification)
    notification.delete()


@transaction.atomic
def mark_all_read(actor, selected_ids=None):
    return (
        notifications_for(actor, selected_ids)
        .filter(is_read=False)
        .update(is_read=True, read_at=timezone.now())
    )


@transaction.atomic
def clear_all(actor, selected_ids=None):
    count, _ = notifications_for(actor, selected_ids).delete()
    return count
