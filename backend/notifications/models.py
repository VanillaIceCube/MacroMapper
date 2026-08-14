from django.conf import settings
from django.db import models


class Notification(models.Model):
    EVENT_GENERAL = "general"
    EVENT_SYSTEM = "system"
    EVENT_CHOICES = [
        (EVENT_GENERAL, "General"),
        (EVENT_SYSTEM, "System"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_notifications",
    )
    event_type = models.CharField(
        max_length=40,
        choices=EVENT_CHOICES,
        default=EVENT_GENERAL,
    )
    title = models.CharField(max_length=160)
    message = models.TextField()
    target_path = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
        ]
