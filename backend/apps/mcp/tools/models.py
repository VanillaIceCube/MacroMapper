"""Per-account concurrency and automatic execution receipts."""

from django.conf import settings
from django.db import models


class ActorLock(models.Model):
    """Serializes mutations, including SQLite's early writer barrier."""

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, primary_key=True, on_delete=models.CASCADE
    )
    revision = models.PositiveBigIntegerField(default=0)


class Execution(models.Model):
    """A client-generated request UUID is never silently executed a second time."""

    class State(models.TextChoices):
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        UNCERTAIN = "uncertain"

    id = models.UUIDField(primary_key=True, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    client_id = models.CharField(max_length=255)
    action = models.CharField(max_length=48)
    target_id = models.PositiveBigIntegerField(null=True)
    request_digest = models.CharField(max_length=64)
    state = models.CharField(
        max_length=16, choices=State.choices, default=State.IN_PROGRESS
    )
    outcome = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
