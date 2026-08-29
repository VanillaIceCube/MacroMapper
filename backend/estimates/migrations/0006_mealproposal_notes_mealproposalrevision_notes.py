from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("estimates", "0005_mealproposalrevision_follow_up"),
    ]

    operations = [
        migrations.AddField(
            model_name="mealproposal",
            name="notes",
            field=models.TextField(blank=True, max_length=2000),
        ),
        migrations.AddField(
            model_name="mealproposalrevision",
            name="notes",
            field=models.TextField(blank=True, max_length=2000),
        ),
    ]
