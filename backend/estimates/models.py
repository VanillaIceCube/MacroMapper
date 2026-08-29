from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
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


class MealProposalRevision(models.Model):
    class Kind(models.TextChoices):
        GENERATED = "generated", "Generated"
        USER_REVIEWED = "user_reviewed", "User reviewed"
        AI_FOLLOW_UP = "ai_follow_up", "AI follow-up"
        ACCEPTED = "accepted", "Accepted"

    proposal = models.ForeignKey(
        MealProposal,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    revision_number = models.PositiveIntegerField()
    kind = models.CharField(max_length=24, choices=Kind)
    name = models.CharField(max_length=120)
    items = models.JSONField(default=list)
    follow_up = models.CharField(max_length=500, blank=True)
    message = models.CharField(max_length=300, blank=True)
    parent_revision = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="child_revisions",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meal_proposal_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["revision_number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "revision_number"],
                name="unique_meal_proposal_revision_number",
            )
        ]

    def clean(self):
        super().clean()
        if (
            self.parent_revision_id
            and self.parent_revision.proposal_id != self.proposal_id
        ):
            raise ValidationError(
                {"parent_revision": "The parent must belong to the same proposal."}
            )

    def __str__(self):
        return f"{self.proposal} revision {self.revision_number}"
