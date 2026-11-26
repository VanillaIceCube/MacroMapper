"""Canonical product identity, portion fingerprints and private overrides."""

from copy import deepcopy
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.estimates.services import (
    _catalog_food,
    _materialize_item,
    resolve_catalog_matches,
)

from ..identity import canonical_food_identity
from ..models import (
    FoodItem,
)
from ..services import (
    create_food_item,
    create_food_version,
    publish_shared_food,
)
from .helpers import (
    CanonicalIdentityFixtures,
    definition,
    source,
)


class CanonicalIdentityTests(CanonicalIdentityFixtures, TestCase):
    def test_provider_punctuation_pluralization_and_classification_share_identity(self):
        food, original = self.publish()
        variant = {
            "name": "Hash Brown",
            "provider_name": "McDonalds",
            "origin_type": "branded",
        }
        second_food, alternative = self.publish(
            item=variant, calories="145", confidence="0.95"
        )
        self.assertEqual(food.pk, second_food.pk)
        self.assertNotEqual(original.pk, alternative.pk)
        original.refresh_from_db()
        self.assertEqual(original.calories, Decimal("140"))
        self.assertEqual(food.versions.count(), 2)
        food.refresh_from_db()
        self.assertEqual(food.current_version_id, alternative.pk)

    def test_market_product_identifiers_and_provider_urls_keep_distinct_products(self):
        base = canonical_food_identity(
            **self.item, market="US", product_identifier="101"
        )
        variants = [
            {"market": "UK", "product_identifier": "101"},
            {"market": "US", "product_identifier": "102"},
        ]
        for variant in variants:
            self.assertNotEqual(base, canonical_food_identity(**self.item, **variant))
        self.assertNotEqual(
            canonical_food_identity(**self.item, sources=[source()]),
            canonical_food_identity(
                **self.item,
                sources=[
                    source("https://www.mcdonalds.com/gb/en-gb/product/hash-brown.html")
                ],
            ),
        )

    def test_generic_sizes_share_identity_but_branded_size_variants_do_not(self):
        self.assertEqual(
            canonical_food_identity(name="Small red apples"),
            canonical_food_identity(name="Large red apple"),
        )
        self.assertNotEqual(
            canonical_food_identity(
                name="Small shake", provider_name="Brand", origin_type="branded"
            ),
            canonical_food_identity(
                name="Large shake", provider_name="Brand", origin_type="branded"
            ),
        )

    def test_serving_definition_changes_are_versions(self):
        food, original = self.publish()
        revised = definition()
        revised["serving_weight_grams"] = Decimal("60")
        changed = create_food_version(
            food_item=food, definition=revised, created_by=None
        )
        self.assertNotEqual(original.pk, changed.pk)
        self.assertEqual(food.versions.count(), 2)

    def test_recipe_versions_preserve_the_region_of_each_pinned_child(self):
        us_child, us_version = self.publish(sources=[source()])
        uk_source = source("https://www.mcdonalds.com/gb/en-gb/product/hash-brown.html")
        uk_child, uk_version = self.publish(sources=[uk_source])
        self.assertNotEqual(us_child.canonical_identity, uk_child.canonical_identity)
        self.assertEqual(us_version.content_fingerprint, uk_version.content_fingerprint)
        recipe_item = {
            "name": "Synthetic regional breakfast",
            "origin_type": "generic",
            "provider_name": "",
        }
        us_recipe_definition = {
            **definition(),
            "components": [
                {
                    "food_item": us_child,
                    "food_version": us_version,
                    "servings": Decimal("1"),
                    "order": 0,
                }
            ],
        }
        uk_recipe_definition = {
            **definition(),
            "components": [
                {
                    "food_item": uk_child,
                    "food_version": uk_version,
                    "servings": Decimal("1"),
                    "order": 0,
                }
            ],
        }

        recipe, us_recipe = publish_shared_food(
            item=recipe_item, definition=us_recipe_definition
        )
        same_recipe, uk_recipe = publish_shared_food(
            item=recipe_item, definition=uk_recipe_definition
        )
        repeated = create_food_version(
            food_item=recipe, definition=uk_recipe_definition, created_by=None
        )

        self.assertEqual(same_recipe.pk, recipe.pk)
        self.assertNotEqual(us_recipe.pk, uk_recipe.pk)
        self.assertEqual(repeated.pk, uk_recipe.pk)
        self.assertEqual(recipe.versions.count(), 2)
        self.assertEqual(us_recipe.components.get().child_version_id, us_version.pk)
        self.assertEqual(uk_recipe.components.get().child_version_id, uk_version.pk)

        # Legacy children have no registered identity and can have a newer source.
        us_child.canonical_identity = None
        us_child.save(update_fields=["canonical_identity"])
        create_food_version(
            food_item=us_child,
            definition=definition(sources=[uk_source]),
            created_by=None,
        )
        self.assertNotEqual(us_child.current_version_id, us_version.pk)
        us_version.refresh_from_db()
        pinned_recipe = create_food_version(
            food_item=recipe, definition=us_recipe_definition, created_by=None
        )
        self.assertEqual(pinned_recipe.pk, us_recipe.pk)

    def test_natural_servings_validate_and_participate_in_definition_fingerprint(self):
        food, original = self.publish()
        revised = definition()
        revised["natural_servings"] = [
            {"key": "small", "label": "Small", "weight_grams": "40"}
        ]
        changed = create_food_version(
            food_item=food, definition=revised, created_by=None
        )
        self.assertNotEqual(original.pk, changed.pk)
        revised["natural_servings"][0]["weight_grams"] = "NaN"
        with self.assertRaises(ValidationError):
            create_food_version(food_item=food, definition=revised, created_by=None)

    def test_no_op_materialization_retains_shared_but_material_override_stays_private(
        self,
    ):
        food, original = self.publish()
        item = _catalog_food(original, servings="4")
        saved_food, saved_version = _materialize_item(owner=self.user, item=item)
        self.assertEqual((saved_food.pk, saved_version.pk), (food.pk, original.pk))
        changed = deepcopy(item)
        changed["nutrients"]["calories"] = "155"
        personal, version = _materialize_item(owner=self.user, item=changed)
        self.assertEqual(personal.owner, self.user)
        self.assertEqual(personal.scope, "personal")
        self.assertEqual(version.derived_from_id, original.pk)
        self.assertEqual(FoodItem.objects.active().filter(scope="shared").count(), 1)

    def test_normalized_serving_definitions_reuse_the_same_shared_version(self):
        from ..serializers import FoodDefinitionInputSerializer

        original = definition()
        original["natural_servings"] = [
            {"key": "small", "label": "Small", "weight_grams": "40"}
        ]
        food, first = publish_shared_food(item=self.item, definition=original)
        incoming = deepcopy(original)
        incoming["natural_servings"] = [
            {"key": "small", "label": "  Small  ", "weight_grams": 40.0}
        ]
        # Exercise the API normalization boundary before the shared version service.
        serializer = FoodDefinitionInputSerializer(data=incoming)
        serializer.is_valid(raise_exception=True)

        repeated = create_food_version(
            food_item=food, definition=serializer.validated_data, created_by=None
        )

        self.assertEqual(repeated.pk, first.pk)
        self.assertEqual(repeated.natural_servings, original["natural_servings"])
        self.assertEqual(food.versions.count(), 1)

    def test_existing_no_op_personal_copy_does_not_shadow_shared_for_its_owner(self):
        shared, original = self.publish()
        personal = create_food_item(
            name=shared.name,
            scope="personal",
            origin_type=shared.origin_type,
            provider_name=shared.provider_name,
            owner=self.user,
            definition={**definition(), "derived_from": original},
            created_by=self.user,
        )
        for user in (
            self.user,
            get_user_model().objects.create_user(
                username="other-identity-owner", email="other-identity@example.com"
            ),
        ):
            resolution = resolve_catalog_matches(
                description="4 hash browns mcdonalds", user=user
            )
            self.assertEqual(resolution["matches"][0]["food"].pk, shared.pk)
            self.assertEqual(resolution["matches"][0]["servings"], Decimal("4"))
        create_food_version(
            food_item=personal,
            definition={**definition("200"), "derived_from": original},
            created_by=self.user,
        )
        resolution = resolve_catalog_matches(
            description="4 hash browns mcdonalds", user=self.user
        )
        self.assertEqual(resolution["matches"][0]["food"].pk, personal.pk)
