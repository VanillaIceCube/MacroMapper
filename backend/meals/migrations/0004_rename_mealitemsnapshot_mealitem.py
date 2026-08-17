import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("foods", "0003_fooditemversion_calories_and_more"),
        ("meals", "0003_update_admin_model_names"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="MealItemSnapshot",
            new_name="MealItem",
        ),
        migrations.AlterModelOptions(
            name="mealitem",
            options={
                "ordering": ["order", "id"],
                "verbose_name": "meal item",
                "verbose_name_plural": "meal items",
            },
        ),
        migrations.AlterField(
            model_name="mealitem",
            name="food_version",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="meal_items",
                to="foods.fooditemversion",
            ),
        ),
    ]
