from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class MealEntry(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="meal_entries",
    )
    entry_date = models.DateField(db_index=True)
    name = models.CharField(max_length=120)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["entry_date", "created_at", "id"]
        indexes = [models.Index(fields=["owner", "entry_date"])]
        verbose_name_plural = "meal entries"

    def __str__(self):
        return f"{self.entry_date}: {self.name}"


class MealItem(models.Model):
    meal_entry = models.ForeignKey(
        MealEntry,
        on_delete=models.CASCADE,
        related_name="items",
    )
    food_version = models.ForeignKey(
        "foods.FoodItemVersion",
        on_delete=models.PROTECT,
        related_name="meal_items",
    )
    servings = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    order = models.PositiveSmallIntegerField(default=0)
    food_name = models.CharField(max_length=200)
    provider_name = models.CharField(max_length=160, blank=True)
    serving_quantity = models.DecimalField(max_digits=10, decimal_places=3)
    serving_unit = models.CharField(max_length=16)
    serving_label = models.CharField(max_length=120, blank=True)
    component_snapshot = models.JSONField(default=list, blank=True)
    calories = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    protein = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    carbohydrates = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    fat = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    fiber = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    sugar = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    sodium = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    cholesterol = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "meal item"
        verbose_name_plural = "meal items"
        constraints = [
            models.UniqueConstraint(
                fields=["meal_entry", "order"],
                name="unique_meal_item_order",
            ),
            models.CheckConstraint(
                condition=Q(servings__gt=0),
                name="meal_item_servings_positive",
            ),
        ]

    def __str__(self):
        return f"{self.servings} × {self.food_name}"
