"""App-owned identity links and short-lived, one-use meal confirmations."""

import uuid

from django.conf import settings
from django.db import models


class IdentityLink(models.Model):
    issuer = models.URLField(default="https://auth.judeandrewalaba.com", editable=False)
    subject = models.UUIDField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["issuer", "subject"], name="mcp_subject_link"
            ),
            models.UniqueConstraint(fields=["issuer", "user"], name="mcp_user_link"),
        ]


class MealConfirmation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    link = models.ForeignKey(IdentityLink, on_delete=models.CASCADE)
    client_id = models.CharField(max_length=80)
    payload = models.JSONField()
    fingerprint = models.CharField(max_length=64)
    expires_at = models.DateTimeField(db_index=True)
