from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from .admin import (
    FoodComponentAdmin,
    FoodComponentInline,
    FoodItemAdmin,
    FoodItemVersionAdmin,
    SourceReferenceAdmin,
    SourceReferenceInline,
)
from .models import (
    FoodComponent,
    FoodItem,
    FoodItemVersion,
    SourceReference,
)
from .nutrients import NUTRIENT_METADATA
from .services import create_food_item, create_food_version

User = get_user_model()


def food_definition(*, calories="100", confidence="0.900", components=None):
    return {
        "serving_quantity": Decimal("1"),
        "serving_unit": FoodItemVersion.ServingUnit.ITEM,
        "serving_label": "one item",
        "provenance": FoodItemVersion.Provenance.USER_ENTERED,
        "confidence_score": (Decimal(confidence) if confidence is not None else None),
        "nutrients": {"calories": Decimal(calories)},
        "sources": [],
        "components": components or [],
    }


class FoodModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="owner-password",
        )

    def test_core_nutrient_metadata_has_canonical_units(self):
        expected = {
            "calories": "kcal",
            "protein": "g",
            "carbohydrates": "g",
            "fat": "g",
            "fiber": "g",
            "sugar": "g",
            "sodium": "mg",
            "cholesterol": "mg",
        }

        actual = {key: metadata["unit"] for key, metadata in NUTRIENT_METADATA.items()}

        self.assertEqual(actual, expected)

    def test_personal_food_requires_an_owner_at_database_level(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            FoodItem.objects.create(
                name="Ownerless food",
                scope=FoodItem.Scope.PERSONAL,
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


class FoodAdminTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.request = RequestFactory().get("/admin/")

    def test_food_privacy_fields_cannot_change_after_creation_in_admin(self):
        food_admin = FoodItemAdmin(FoodItem, self.site)
        existing_food = FoodItem(
            name="Private food",
            scope=FoodItem.Scope.PERSONAL,
            owner_id=1,
        )

        add_readonly_fields = food_admin.get_readonly_fields(self.request)
        change_readonly_fields = food_admin.get_readonly_fields(
            self.request,
            existing_food,
        )

        self.assertIn("current_version", add_readonly_fields)
        self.assertNotIn("scope", add_readonly_fields)
        self.assertNotIn("owner", add_readonly_fields)
        self.assertIn("current_version", change_readonly_fields)
        self.assertIn("scope", change_readonly_fields)
        self.assertIn("owner", change_readonly_fields)
        self.assertNotIn(
            "current_version", food_admin.get_autocomplete_fields(self.request)
        )

    def test_version_and_related_records_are_immutable_in_admin(self):
        admin_classes = (
            (FoodItemVersionAdmin, FoodItemVersion),
            (FoodComponentAdmin, FoodComponent),
            (SourceReferenceAdmin, SourceReference),
        )

        for admin_class, model in admin_classes:
            with self.subTest(model=model.__name__):
                model_admin = admin_class(model, self.site)
                self.assertFalse(model_admin.has_add_permission(self.request))
                self.assertFalse(model_admin.has_change_permission(self.request))
                self.assertFalse(model_admin.has_delete_permission(self.request))

    def test_version_related_inlines_are_immutable_in_admin(self):
        inline_classes = (
            SourceReferenceInline,
            FoodComponentInline,
        )

        for inline_class in inline_classes:
            with self.subTest(inline=inline_class.__name__):
                inline = inline_class(FoodItemVersion, self.site)
                self.assertFalse(inline.has_add_permission(self.request))
                self.assertFalse(inline.has_change_permission(self.request))
                self.assertFalse(inline.has_delete_permission(self.request))


class FoodApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="owner-password",
        )
        self.other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="other-password",
        )
        self.shared_food = create_food_item(
            name="Shared apple",
            scope=FoodItem.Scope.SHARED,
            origin_type=FoodItem.OriginType.BRANDED,
            provider_name="Example Orchard",
            owner=None,
            definition={
                **food_definition(calories="95", confidence="0.990"),
                "provenance": FoodItemVersion.Provenance.OFFICIAL,
                "sources": [
                    {
                        "title": "Official apple data",
                        "provider": "Example source",
                        "url": "https://example.com/apple",
                    }
                ],
            },
            created_by=self.owner,
        )
        self.personal_food = create_food_item(
            name="Owner smoothie",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.owner,
            definition=food_definition(calories="210", confidence=None),
            created_by=self.owner,
        )
        self.other_food = create_food_item(
            name="Other private food",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=self.other_user,
            definition=food_definition(calories="300", confidence=None),
            created_by=self.other_user,
        )

    def personal_food_payload(self, **overrides):
        payload = {
            "name": "Personal toast",
            "origin_type": FoodItem.OriginType.BRANDED,
            "provider_name": "Example Bakery",
            "definition": {
                "serving_quantity": "1",
                "serving_unit": FoodItemVersion.ServingUnit.ITEM,
                "serving_label": "one slice",
                "provenance": FoodItemVersion.Provenance.USER_ENTERED,
                "confidence_score": None,
                "nutrients": {"calories": "80", "fiber": "0"},
                "sources": [],
                "components": [],
            },
        }
        payload.update(overrides)
        return payload

    def test_food_endpoint_requires_authentication(self):
        food_response = self.client.get("/api/foods/")

        self.assertEqual(food_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_catalog_lists_shared_and_owned_foods_only(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get("/api/foods/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            {item["id"] for item in response.data},
            {self.shared_food.id, self.personal_food.id},
        )

    def test_catalog_search_matches_name_and_provider(self):
        self.client.force_authenticate(user=self.owner)

        name_response = self.client.get("/api/foods/?search=apple")
        provider_response = self.client.get("/api/foods/?search=Orchard")

        self.assertEqual(
            [item["id"] for item in name_response.data],
            [self.shared_food.id],
        )
        self.assertEqual(
            [item["id"] for item in provider_response.data],
            [self.shared_food.id],
        )

    def test_shared_detail_retains_provenance_confidence_and_sources(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(f"/api/foods/{self.shared_food.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        definition = response.data["current_version"]
        self.assertEqual(definition["provenance"], FoodItemVersion.Provenance.OFFICIAL)
        self.assertEqual(definition["confidence_score"], "0.990")
        self.assertEqual(
            definition["sources"][0]["url"],
            "https://example.com/apple",
        )

    def test_user_can_create_a_personal_food_with_unknown_and_zero_nutrients(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            "/api/foods/",
            self.personal_food_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        created = FoodItem.objects.get(pk=response.data["id"])
        self.assertEqual(created.owner, self.owner)
        self.assertEqual(created.scope, FoodItem.Scope.PERSONAL)
        nutrient_values = {
            item["key"]: item["amount"]
            for item in response.data["current_version"]["nutrients"]
        }
        self.assertEqual(nutrient_values["fiber"], "0.0000")
        self.assertNotIn("sugar", nutrient_values)

    def test_personal_food_rejects_an_unsupported_nutrient(self):
        payload = self.personal_food_payload()
        payload["definition"]["nutrients"]["potassium"] = "120"
        self.client.force_authenticate(user=self.owner)

        response = self.client.post("/api/foods/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nutrients", response.data["definition"])

    def test_personal_foods_are_private_for_retrieve_update_and_delete(self):
        self.client.force_authenticate(user=self.owner)
        url = f"/api/foods/{self.other_food.id}/"

        retrieve_response = self.client.get(url)
        update_response = self.client.patch(url, {"name": "Changed"}, format="json")
        delete_response = self.client.delete(url)

        self.assertEqual(retrieve_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_composite_cannot_reference_another_users_personal_food(self):
        payload = self.personal_food_payload()
        payload["definition"]["components"] = [
            {"food_item": self.other_food.id, "servings": "1", "order": 0}
        ]
        self.client.force_authenticate(user=self.owner)

        response = self.client.post("/api/foods/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("components", response.data["definition"])

    def test_shared_foods_are_read_only_for_normal_users(self):
        self.client.force_authenticate(user=self.owner)
        url = f"/api/foods/{self.shared_food.id}/"

        update_response = self.client.patch(url, {"name": "Changed"}, format="json")
        delete_response = self.client.delete(url)

        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_updating_a_definition_creates_a_new_version(self):
        self.client.force_authenticate(user=self.owner)
        old_version = self.personal_food.current_version
        payload = self.personal_food_payload()["definition"]
        payload["nutrients"] = {"calories": "225"}

        response = self.client.patch(
            f"/api/foods/{self.personal_food.id}/",
            {"definition": payload},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.personal_food.refresh_from_db()
        self.assertEqual(self.personal_food.current_version.version_number, 2)
        self.assertNotEqual(self.personal_food.current_version_id, old_version.id)
        self.assertEqual(
            old_version.calories,
            Decimal("210"),
        )

    def test_composite_food_keeps_the_exact_child_version(self):
        self.client.force_authenticate(user=self.owner)
        old_child_version = self.personal_food.current_version
        definition = self.personal_food_payload()["definition"]
        definition["components"] = [
            {
                "food_item": self.personal_food.id,
                "servings": "0.5",
                "order": 0,
            }
        ]
        parent_response = self.client.post(
            "/api/foods/",
            self.personal_food_payload(name="Composite snack", definition=definition),
            format="json",
        )
        self.assertEqual(
            parent_response.status_code,
            status.HTTP_201_CREATED,
            parent_response.data,
        )

        updated_definition = self.personal_food_payload()["definition"]
        updated_definition["nutrients"] = {"calories": "250"}
        update_response = self.client.patch(
            f"/api/foods/{self.personal_food.id}/",
            {"definition": updated_definition},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)

        parent_detail = self.client.get(f"/api/foods/{parent_response.data['id']}/")
        component = parent_detail.data["current_version"]["components"][0]
        self.assertEqual(component["food_version_id"], old_child_version.id)

    def test_delete_archives_an_owned_personal_food(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.delete(f"/api/foods/{self.personal_food.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.personal_food.refresh_from_db()
        self.assertIsNotNone(self.personal_food.archived_at)
        list_response = self.client.get("/api/foods/")
        self.assertNotIn(
            self.personal_food.id,
            [item["id"] for item in list_response.data],
        )
