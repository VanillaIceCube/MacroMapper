from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class MealProposal(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACCEPTED = "accepted", "Accepted"

    class Generator(models.TextChoices):
        CATALOG = "catalog", "Catalog"
        OPENAI = "openai", "OpenAI"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="meal_proposals",
    )
    description = models.TextField(max_length=2000)
    entry_date = models.DateField(db_index=True)
    name = models.CharField(max_length=120)
    status = models.CharField(
        max_length=16,
        choices=Status,
        default=Status.DRAFT,
    )
    generator = models.CharField(max_length=16, choices=Generator)
    provider_name = models.CharField(max_length=80, blank=True)
    provider_model = models.CharField(max_length=120, blank=True)
    provider_response_id = models.CharField(max_length=160, blank=True)
    confidence_score = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    items = models.JSONField(default=list)
    accepted_meal = models.OneToOneField(
        "meals.MealEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_proposal",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["owner", "status", "created_at"])]

    def __str__(self):
        return f"{self.entry_date}: {self.name} ({self.get_status_display()})"
