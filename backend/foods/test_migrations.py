from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class NutrientColumnMigrationTests(TransactionTestCase):
    migrate_from = [("foods", "0002_seed_core_nutrients")]
    migrate_to = [("foods", "0003_fooditemversion_calories_and_more")]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        FoodItem = old_apps.get_model("foods", "FoodItem")
        FoodItemVersion = old_apps.get_model("foods", "FoodItemVersion")
        NutrientAmount = old_apps.get_model("foods", "NutrientAmount")
        NutrientDefinition = old_apps.get_model("foods", "NutrientDefinition")

        food = FoodItem.objects.create(
            name="Migration apple",
            scope="shared",
            origin_type="generic",
            provider_name="",
        )
        version = FoodItemVersion.objects.create(
            food_item=food,
            version_number=1,
            serving_quantity=Decimal("1"),
            serving_unit="item",
            serving_label="one item",
            provenance="official",
            confidence_score=Decimal("1"),
        )
        food.current_version = version
        food.save(update_fields=["current_version"])
        NutrientAmount.objects.create(
            food_version=version,
            nutrient=NutrientDefinition.objects.get(key="calories"),
            amount=Decimal("95"),
        )
        self.version_id = version.pk

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_nutrient_data_survives_forward_and_reverse_migration(self):
        forward_executor = MigrationExecutor(connection)
        forward_executor.migrate(self.migrate_to)
        migrated_apps = forward_executor.loader.project_state(self.migrate_to).apps
        migrated_version = migrated_apps.get_model(
            "foods", "FoodItemVersion"
        ).objects.get(pk=self.version_id)
        self.assertEqual(migrated_version.calories, Decimal("95"))

        reverse_executor = MigrationExecutor(connection)
        reverse_executor.migrate(self.migrate_from)
        reversed_apps = reverse_executor.loader.project_state(self.migrate_from).apps
        NutrientDefinition = reversed_apps.get_model("foods", "NutrientDefinition")
        NutrientAmount = reversed_apps.get_model("foods", "NutrientAmount")

        self.assertEqual(NutrientDefinition.objects.count(), 8)
        calorie_definition = NutrientDefinition.objects.get(key="calories")
        self.assertEqual(calorie_definition.name, "Calories")
        self.assertEqual(calorie_definition.unit, "kcal")
        self.assertEqual(calorie_definition.display_order, 10)
        restored = NutrientAmount.objects.get(
            food_version_id=self.version_id,
            nutrient=calorie_definition,
        )
        self.assertEqual(restored.amount, Decimal("95"))
