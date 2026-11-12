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


class CanonicalIdentitySchemaMigrationTests(TransactionTestCase):
    migrate_from = [
        ("foods", "0004_fooditem_shared_fingerprint_and_more"),
        ("meals", "0004_rename_mealitemsnapshot_mealitem"),
    ]
    migrate_to = [
        ("foods", "0005_canonical_food_identity"),
        ("meals", "0004_rename_mealitemsnapshot_mealitem"),
    ]

    def test_schema_addition_preserves_legacy_duplicate_versions_and_sources(self):
        executor = MigrationExecutor(connection)
        try:
            executor.migrate(self.migrate_from)
            old_apps = executor.loader.project_state(self.migrate_from).apps
            Food = old_apps.get_model("foods", "FoodItem")
            Version = old_apps.get_model("foods", "FoodItemVersion")
            Source = old_apps.get_model("foods", "SourceReference")
            food_ids = []
            version_ids = []
            for calories in ("140", "145"):
                food = Food.objects.create(
                    name="Hash Browns",
                    scope="shared",
                    provider_name="McDonald's",
                    origin_type="restaurant",
                )
                version = Version.objects.create(
                    food_item=food,
                    version_number=1,
                    serving_quantity="1",
                    serving_unit="item",
                    serving_label="1 hash brown",
                    provenance="ai_estimate",
                    confidence_score="0.9",
                    calories=calories,
                )
                food.current_version_id = version.pk
                food.save(update_fields=["current_version"])
                Source.objects.create(
                    food_version=version,
                    title="Product information",
                    provider="McDonald's",
                    url="https://www.mcdonalds.com/us/en-us/product/hash-browns.html",
                )
                food_ids.append(food.pk)
                version_ids.append(version.pk)
            User = old_apps.get_model("authentication", "User")
            owner = User.objects.create(
                username="migration-history-owner",
                email="migration-history@example.com",
                password="not-a-real-password",
            )
            Meal = old_apps.get_model("meals", "MealEntry")
            meal = Meal.objects.create(
                owner=owner, name="Historical breakfast", entry_date="2026-11-11"
            )
            snapshot = old_apps.get_model("meals", "MealItem").objects.create(
                meal_entry=meal,
                food_version_id=version_ids[1],
                servings="2",
                order=0,
                food_name="Hash Browns",
                serving_quantity="1",
                serving_unit="item",
                serving_label="1 hash brown",
                calories="290",
                component_snapshot=[
                    {
                        "food_version_id": version_ids[0],
                        "nutrients": {"calories": "140"},
                    }
                ],
            )
            component = old_apps.get_model("foods", "FoodComponent").objects.create(
                parent_version_id=version_ids[0],
                child_version_id=version_ids[1],
                servings="1",
                order=0,
            )
            forward = MigrationExecutor(connection)
            forward.migrate(self.migrate_to)
            new_apps = forward.loader.project_state(self.migrate_to).apps
            NewFood = new_apps.get_model("foods", "FoodItem")
            NewVersion = new_apps.get_model("foods", "FoodItemVersion")
            self.assertEqual(
                list(
                    NewVersion.objects.filter(pk__in=version_ids)
                    .order_by("pk")
                    .values_list("calories", flat=True)
                ),
                [Decimal("140"), Decimal("145")],
            )
            self.assertEqual(
                NewFood.objects.filter(
                    pk__in=food_ids,
                    archived_at=None,
                    canonical_identity=None,
                    merged_into=None,
                ).count(),
                2,
            )
            self.assertEqual(
                new_apps.get_model("foods", "SourceReference")
                .objects.filter(food_version_id__in=version_ids)
                .count(),
                2,
            )
            self.assertTrue(
                all(
                    not version.natural_servings and not version.content_fingerprint
                    for version in NewVersion.objects.filter(pk__in=version_ids)
                )
            )
            preserved_snapshot = new_apps.get_model("meals", "MealItem").objects.get(
                pk=snapshot.pk
            )
            self.assertEqual(preserved_snapshot.food_version_id, version_ids[1])
            self.assertEqual(preserved_snapshot.calories, Decimal("290"))
            self.assertEqual(
                preserved_snapshot.component_snapshot, snapshot.component_snapshot
            )
            self.assertEqual(
                new_apps.get_model("foods", "FoodComponent")
                .objects.get(pk=component.pk)
                .child_version_id,
                version_ids[1],
            )
            reverse = MigrationExecutor(connection)
            reverse.migrate(self.migrate_from)
            reversed_apps = reverse.loader.project_state(self.migrate_from).apps
            self.assertEqual(
                reversed_apps.get_model("foods", "FoodItemVersion")
                .objects.filter(pk__in=version_ids)
                .count(),
                2,
            )
        finally:
            latest = MigrationExecutor(connection)
            latest.migrate(latest.loader.graph.leaf_nodes())
