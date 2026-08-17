from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("meals", "0002_mealitemsnapshot_calories_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="mealentry",
            options={
                "ordering": ["entry_date", "created_at", "id"],
                "verbose_name_plural": "meal entries",
            },
        ),
        migrations.AlterModelOptions(
            name="mealitemsnapshot",
            options={
                "ordering": ["order", "id"],
                "verbose_name": "logged food",
                "verbose_name_plural": "logged foods",
            },
        ),
    ]
