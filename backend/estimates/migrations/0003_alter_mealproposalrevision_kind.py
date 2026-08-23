from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("estimates", "0002_mealproposalrevision"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mealproposalrevision",
            name="kind",
            field=models.CharField(
                choices=[
                    ("generated", "Generated"),
                    ("user_reviewed", "User reviewed"),
                    ("ai_follow_up", "AI follow-up"),
                    ("accepted", "Accepted"),
                ],
                max_length=24,
            ),
        ),
    ]
