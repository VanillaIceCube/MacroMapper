"""Food ownership constraints, component boundaries and immutable versions."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from ..models import (
    FoodComponent,
    FoodItem,
    FoodItemVersion,
)
from ..services import (
    create_food_item,
    create_food_version,
)
from .helpers import FoodModelFixtures, food_definition


class FoodModelIntegrityTests(FoodModelFixtures, TestCase):
    def test_personal_food_requires_an_owner_at_database_level(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            FoodItem.objects.create(
                name="Ownerless food",
                scope=FoodItem.Scope.PERSONAL,
            )

    def test_personal_food_cannot_use_a_shared_fingerprint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            FoodItem.objects.create(
                name="Personal fingerprint",
                scope=FoodItem.Scope.PERSONAL,
                owner=self.user,
                shared_fingerprint="a" * 64,
            )

    def test_shared_version_requires_confidence(self):
        shared_food = FoodItem.objects.create(
            name="Shared food",
            scope=FoodItem.Scope.SHARED,
        )
        version = FoodItemVersion(
            food_item=shared_food,
            version_number=1,
            serving_quantity=Decimal("1"),
            serving_unit=FoodItemVersion.ServingUnit.ITEM,
            provenance=FoodItemVersion.Provenance.COMMUNITY_ESTIMATE,
            confidence_score=None,
        )

        with self.assertRaises(ValidationError):
            version.full_clean()

    def test_component_validation_rejects_cycles(self):
        first = create_food_item(
            name="First food",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.user,
            definition=food_definition(),
            created_by=self.user,
        )
        second = create_food_item(
            name="Second food",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.user,
            definition=food_definition(),
            created_by=self.user,
        )
        FoodComponent.objects.create(
            parent_version=first.current_version,
            child_version=second.current_version,
            servings=Decimal("1"),
        )
        reverse_component = FoodComponent(
            parent_version=second.current_version,
            child_version=first.current_version,
            servings=Decimal("1"),
        )

        with self.assertRaises(ValidationError):
            reverse_component.full_clean()

    def test_shared_composite_cannot_expose_a_personal_component(self):
        personal_food = create_food_item(
            name="Private component",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.user,
            definition=food_definition(confidence=None),
            created_by=self.user,
        )
        shared_food = create_food_item(
            name="Shared composite",
            scope=FoodItem.Scope.SHARED,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=None,
            definition=food_definition(),
            created_by=self.user,
        )
        component = FoodComponent(
            parent_version=shared_food.current_version,
            child_version=personal_food.current_version,
            servings=Decimal("1"),
        )

        with self.assertRaises(ValidationError):
            component.full_clean()

    def test_new_version_preserves_the_old_nutrient_values(self):
        food = create_food_item(
            name="Versioned food",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.user,
            definition=food_definition(calories="100"),
            created_by=self.user,
        )
        old_version = food.current_version

        new_version = create_food_version(
            food_item=food,
            definition=food_definition(calories="125"),
            created_by=self.user,
        )

        self.assertEqual(new_version.version_number, 2)
        self.assertEqual(food.current_version_id, new_version.id)
        self.assertEqual(
            old_version.calories,
            Decimal("100"),
        )
