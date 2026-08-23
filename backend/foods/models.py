from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q


class FoodItemQuerySet(models.QuerySet):
    def active(self):
        return self.filter(archived_at__isnull=True)

    def visible_to(self, user):
        if not user or not user.is_authenticated:
            return self.none()
        return self.filter(Q(scope=FoodItem.Scope.SHARED) | Q(owner=user))


class FoodItem(models.Model):
    class Scope(models.TextChoices):
        SHARED = "shared", "Shared"
        PERSONAL = "personal", "Personal"

    class OriginType(models.TextChoices):
        GENERIC = "generic", "Generic"
        BRANDED = "branded", "Branded"
        RESTAURANT = "restaurant", "Restaurant"

    name = models.CharField(max_length=200)
    scope = models.CharField(max_length=16, choices=Scope, default=Scope.PERSONAL)
    origin_type = models.CharField(
        max_length=16,
        choices=OriginType,
        default=OriginType.GENERIC,
    )
    provider_name = models.CharField(max_length=160, blank=True)
    shared_fingerprint = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="food_items",
    )
    current_version = models.OneToOneField(
        "FoodItemVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_for_food_item",
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = FoodItemQuerySet.as_manager()

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(scope="shared", owner__isnull=True)
                    | Q(scope="personal", owner__isnull=False)
                ),
                name="food_scope_matches_owner",
            ),
            models.CheckConstraint(
                condition=(Q(shared_fingerprint__isnull=True) | Q(scope="shared")),
                name="food_shared_fingerprint_scope",
            ),
        ]
        indexes = [
            models.Index(fields=["scope", "name"]),
            models.Index(fields=["owner", "name"]),
        ]

    def clean(self):
        super().clean()
        if self.scope == self.Scope.SHARED and self.owner_id is not None:
            raise ValidationError({"owner": "Shared foods cannot have an owner."})
        if self.scope == self.Scope.PERSONAL and self.owner_id is None:
            raise ValidationError({"owner": "Personal foods require an owner."})
        if self.scope == self.Scope.PERSONAL and self.shared_fingerprint is not None:
            raise ValidationError(
                {
                    "shared_fingerprint": "Personal foods cannot have a shared fingerprint."
                }
            )
        if (
            self.origin_type in {self.OriginType.BRANDED, self.OriginType.RESTAURANT}
            and not self.provider_name.strip()
        ):
            raise ValidationError(
                {"provider_name": "Branded and restaurant foods require a provider."}
            )
        if (
            self.current_version_id
            and self.pk
            and self.current_version.food_item_id != self.pk
        ):
            raise ValidationError(
                {"current_version": "The current version must belong to this food."}
            )

    def __str__(self):
        if self.provider_name:
            return f"{self.provider_name} — {self.name}"
        return self.name


class FoodItemVersion(models.Model):
    class ServingUnit(models.TextChoices):
        GRAM = "g", "Gram"
        MILLILITER = "ml", "Milliliter"
        OUNCE = "oz", "Ounce"
        FLUID_OUNCE = "fl_oz", "Fluid ounce"
        CUP = "cup", "Cup"
        TABLESPOON = "tbsp", "Tablespoon"
        TEASPOON = "tsp", "Teaspoon"
        ITEM = "item", "Item"
        SERVING = "serving", "Serving"

    class Provenance(models.TextChoices):
        OFFICIAL = "official", "Official"
        COMMUNITY_ESTIMATE = "community_estimate", "Community estimate"
        AI_ESTIMATE = "ai_estimate", "AI estimate"
        USER_MODIFIED_ESTIMATE = (
            "user_modified_estimate",
            "User-modified estimate",
        )
        USER_ENTERED = "user_entered", "User entered"

    food_item = models.ForeignKey(
        FoodItem,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField()
    serving_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    serving_unit = models.CharField(max_length=16, choices=ServingUnit)
    serving_label = models.CharField(max_length=120, blank=True)
    serving_weight_grams = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    serving_volume_ml = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    provenance = models.CharField(max_length=24, choices=Provenance)
    confidence_score = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0")),
            MaxValueValidator(Decimal("1")),
        ],
    )
    calories = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    protein = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    carbohydrates = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    fat = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    fiber = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    sugar = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    sodium = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    cholesterol = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_food_versions",
    )
    derived_from = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="derived_versions",
    )
    estimation_provider = models.CharField(max_length=80, blank=True)
    estimation_model = models.CharField(max_length=120, blank=True)
    estimation_response_id = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["food_item", "version_number"],
                name="unique_food_version_number",
            ),
            models.CheckConstraint(
                condition=Q(serving_quantity__gt=0),
                name="food_version_serving_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(confidence_score__isnull=True)
                    | Q(confidence_score__gte=0, confidence_score__lte=1)
                ),
                name="food_version_confidence_range",
            ),
        ]

    def clean(self):
        super().clean()
        if self.derived_from_id and self.pk and self.derived_from_id == self.pk:
            raise ValidationError(
                {"derived_from": "A food version cannot be derived from itself."}
            )
        if (
            self.food_item_id
            and self.food_item.scope == FoodItem.Scope.SHARED
            and self.confidence_score is None
        ):
            raise ValidationError(
                {"confidence_score": "Shared food versions require confidence."}
            )

    def __str__(self):
        return f"{self.food_item} v{self.version_number}"


class SourceReference(models.Model):
    food_version = models.ForeignKey(
        FoodItemVersion,
        on_delete=models.CASCADE,
        related_name="sources",
    )
    title = models.CharField(max_length=200)
    provider = models.CharField(max_length=160, blank=True)
    url = models.URLField(max_length=500)
    accessed_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["food_version", "url"],
                name="unique_source_url_per_food_version",
            ),
        ]

    def __str__(self):
        return self.title


class FoodComponent(models.Model):
    parent_version = models.ForeignKey(
        FoodItemVersion,
        on_delete=models.CASCADE,
        related_name="components",
    )
    child_version = models.ForeignKey(
        FoodItemVersion,
        on_delete=models.PROTECT,
        related_name="used_by_components",
    )
    servings = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["parent_version", "child_version"],
                name="unique_component_per_parent_version",
            ),
            models.UniqueConstraint(
                fields=["parent_version", "order"],
                name="unique_component_order_per_parent",
            ),
            models.CheckConstraint(
                condition=Q(servings__gt=0),
                name="food_component_servings_positive",
            ),
            models.CheckConstraint(
                condition=~Q(parent_version=F("child_version")),
                name="food_component_not_self",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.parent_version_id or not self.child_version_id:
            return
        if self.parent_version_id == self.child_version_id:
            raise ValidationError(
                {"child_version": "A food version cannot contain itself."}
            )

        parent_food = self.parent_version.food_item
        child_food = self.child_version.food_item
        if (
            parent_food.scope == FoodItem.Scope.SHARED
            and child_food.scope != FoodItem.Scope.SHARED
        ):
            raise ValidationError(
                {"child_version": "Shared foods can contain only shared foods."}
            )
        if (
            parent_food.scope == FoodItem.Scope.PERSONAL
            and child_food.scope == FoodItem.Scope.PERSONAL
            and parent_food.owner_id != child_food.owner_id
        ):
            raise ValidationError(
                {"child_version": "Personal foods cannot use another user's food."}
            )

        pending = [self.child_version_id]
        visited = set()
        while pending:
            version_id = pending.pop()
            if version_id == self.parent_version_id:
                raise ValidationError(
                    {"child_version": "Food components cannot form a cycle."}
                )
            if version_id in visited:
                continue
            visited.add(version_id)
            pending.extend(
                FoodComponent.objects.filter(parent_version_id=version_id).values_list(
                    "child_version_id", flat=True
                )
            )

    def __str__(self):
        return f"{self.servings} × {self.child_version}"
