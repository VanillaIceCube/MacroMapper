from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("meals", "0004_rename_mealitemsnapshot_mealitem"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MealProposal",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("description", models.TextField(max_length=2000)),
                ("entry_date", models.DateField(db_index=True)),
                ("name", models.CharField(max_length=120)),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Draft"), ("accepted", "Accepted")],
                        default="draft",
                        max_length=16,
                    ),
                ),
                (
                    "generator",
                    models.CharField(
                        choices=[("catalog", "Catalog"), ("openai", "OpenAI")],
                        max_length=16,
                    ),
                ),
                ("provider_name", models.CharField(blank=True, max_length=80)),
                ("provider_model", models.CharField(blank=True, max_length=120)),
                ("provider_response_id", models.CharField(blank=True, max_length=160)),
                (
                    "confidence_score",
                    models.DecimalField(
                        blank=True,
                        decimal_places=3,
                        max_digits=4,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0")),
                            django.core.validators.MaxValueValidator(Decimal("1")),
                        ],
                    ),
                ),
                ("items", models.JSONField(default=list)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "accepted_meal",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="accepted_proposal",
                        to="meals.mealentry",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="meal_proposals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["owner", "status", "created_at"],
                        name="estimates_m_owner_i_c852eb_idx",
                    )
                ],
            },
        ),
    ]
