from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("meals", "0004_rename_mealitemsnapshot_mealitem")]
    operations = [
        migrations.AddField(
            model_name="mealitem",
            name="selected_portion_key",
            field=models.CharField(default="base", max_length=80),
        ),
    ]
