"""Direct diary services preserve ownership and catalog authorization."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, TransactionTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .. import services
from ..models import MealEntry
from .helpers import MealEntryFixtures


class MealDomainServiceTests(MealEntryFixtures, TestCase):
    def inputs(self, food):
        return {
            "entry_date": date(2026, 11, 15),
            "name": "Lunch",
            "items": [{"food_item": food, "servings": Decimal("1"), "order": 0}],
        }

    def test_direct_create_rejects_foreign_private_food_without_writes(self):
        with self.assertRaises(ValidationError):
            services.create_meal(self.owner, self.inputs(self.other_food))
        self.assertFalse(MealEntry.objects.exists())

    def test_direct_update_and_delete_require_current_owner(self):
        meal = services.create_meal(self.owner, self.inputs(self.apple))
        self.assertEqual(meal.items.get().food_name, "Apple")
        for operation, args in (
            (services.update_meal, ({"name": "Foreign"},)),
            (services.delete_meal, ()),
        ):
            with self.assertRaises(PermissionDenied):
                operation(self.other_user, meal, *args)
        meal.refresh_from_db()
        self.assertEqual(meal.name, "Lunch")
        self.assertEqual(meal.items.count(), 1)


class MealNamingTransactionTests(MealEntryFixtures, TransactionTestCase):
    def test_naming_provider_runs_before_write_transaction(self):
        def name(**kwargs):
            self.assertFalse(connection.in_atomic_block)
            self.assertFalse(MealEntry.objects.exists())
            return "Provider name"

        with patch("apps.meals.services.generate_meal_name", side_effect=name):
            meal = services.create_meal(
                self.owner,
                {
                    "entry_date": date(2026, 11, 15),
                    "name": "",
                    "items": [
                        {"food_item": self.apple, "servings": Decimal("1"), "order": 0}
                    ],
                },
            )
        self.assertEqual(meal.name, "Provider name")
        self.assertEqual(meal.items.count(), 1)
