from django.db import migrations

CORE_NUTRIENTS = (
    ("calories", "Calories", "kcal", 10),
    ("protein", "Protein", "g", 20),
    ("carbohydrates", "Carbohydrates", "g", 30),
    ("fat", "Fat", "g", 40),
    ("fiber", "Fiber", "g", 50),
    ("sugar", "Sugar", "g", 60),
    ("sodium", "Sodium", "mg", 70),
    ("cholesterol", "Cholesterol", "mg", 80),
)


def seed_core_nutrients(apps, schema_editor):
    NutrientDefinition = apps.get_model("foods", "NutrientDefinition")
    NutrientDefinition.objects.bulk_create(
        [
            NutrientDefinition(
                key=key,
                name=name,
                unit=unit,
                is_core=True,
                display_order=display_order,
            )
            for key, name, unit, display_order in CORE_NUTRIENTS
        ]
    )


def remove_core_nutrients(apps, schema_editor):
    NutrientDefinition = apps.get_model("foods", "NutrientDefinition")
    NutrientDefinition.objects.filter(
        key__in=[key for key, *_ in CORE_NUTRIENTS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("foods", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_core_nutrients, remove_core_nutrients),
    ]
