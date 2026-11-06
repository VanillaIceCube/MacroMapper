import uuid

from django.conf import settings
from django.db import models


class ActorLock(models.Model):
    """Serializes confirmed operations, including SQLite's early writer barrier."""

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, primary_key=True, on_delete=models.CASCADE
    )
    revision = models.PositiveBigIntegerField(default=0)


class Confirmation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    client_id = models.CharField(max_length=255)
    token_checksum = models.CharField(max_length=64)
    action = models.CharField(max_length=48)
    target_id = models.PositiveBigIntegerField(null=True)
    payload = models.JSONField(default=dict)
    fingerprint = models.CharField(max_length=64)
    selected_ids = models.JSONField(default=list)
    expires_at = models.DateTimeField(db_index=True)
