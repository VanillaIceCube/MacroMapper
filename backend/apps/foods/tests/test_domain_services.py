"""Direct domain entrypoints enforce catalog privacy and shared immutability."""

from decimal import Decimal

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .. import services
from ..models import FoodItem
from .helpers import FoodApiFixtures, food_definition


class FoodDomainServiceTests(FoodApiFixtures, TestCase):
    def test_direct_mutations_recheck_owner_even_for_staff(self):
        self.owner.is_staff = True
        self.owner.save()
        for food in (self.shared_food, self.other_food):
            with self.assertRaises(PermissionDenied):
                services.update_personal_food(self.owner, food, {"name": "Changed"})
            with self.assertRaises(PermissionDenied):
                services.archive_personal_food(self.owner, food)
            food.refresh_from_db()
            self.assertIsNone(food.archived_at)
            self.assertNotEqual(food.name, "Changed")

    def test_direct_create_rejects_foreign_private_components_atomically(self):
        count = FoodItem.objects.count()
        with self.assertRaises(ValidationError):
            services.create_personal_food(
                self.owner,
                {
                    "name": "Private recipe",
                    "origin_type": "generic",
                    "provider_name": "",
                    "definition": food_definition(
                        components=[
                            {
                                "food_item": self.other_food,
                                "servings": Decimal("1"),
                                "order": 0,
                            }
                        ]
                    ),
                },
            )
        self.assertEqual(FoodItem.objects.count(), count)

    def test_query_and_mutation_recheck_archive_state(self):
        services.archive_personal_food(self.owner, self.personal_food)
        self.assertFalse(
            services.foods_for(self.owner).filter(pk=self.personal_food.pk).exists()
        )
        with self.assertRaises(PermissionDenied):
            services.update_personal_food(
                self.owner, self.personal_food, {"name": "Resurrected"}
            )
