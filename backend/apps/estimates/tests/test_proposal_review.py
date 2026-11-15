"""Owner-scoped proposal review, acceptance, revisions and immutable snapshots."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase

from apps.foods.models import FoodItem, FoodItemVersion
from apps.meals.models import MealEntry

from ..models import MealProposal, MealProposalRevision
from ..provider import EstimationProviderError
from .helpers import ProposalFixtures, ai_estimate, shared_food, simple_ai_estimate


class ProposalReviewTests(ProposalFixtures, TestCase):
    def test_catalog_proposal_keys_include_the_full_component_path(self):
        leaf = shared_food(name="Shared garnish")
        reused = shared_food(
            name="Reused filling",
            components=[{"food_item": leaf, "servings": Decimal("1"), "order": 0}],
        )
        left = shared_food(
            name="Left layer",
            components=[{"food_item": reused, "servings": Decimal("1"), "order": 0}],
        )
        right = shared_food(
            name="Right layer",
            components=[{"food_item": reused, "servings": Decimal("1"), "order": 0}],
        )
        shared_food(
            name="Layered plate",
            components=[
                {"food_item": left, "servings": Decimal("1"), "order": 0},
                {"food_item": right, "servings": Decimal("1"), "order": 1},
            ],
        )

        created = self.client.post(
            "/api/meal-proposals/",
            {"description": "Layered plate", "entry_date": "2026-08-16"},
            format="json",
        )

        self.assertEqual(created.status_code, 201)

        def collect_keys(items):
            return [
                key
                for item in items
                for key in [item["key"], *collect_keys(item.get("components", []))]
            ]

        keys = collect_keys(created.data["items"])
        self.assertEqual(len(keys), len(set(keys)))
        updated = self.client.patch(
            f"/api/meal-proposals/{created.data['id']}/",
            {"items": created.data["items"]},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)

    def test_ai_proposal_can_be_edited_and_accepted_as_private_snapshot(self):
        provider = Mock()
        provider.estimate.return_value = ai_estimate()
        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            created = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "A restaurant burger without cheese",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(created.status_code, 201)
        proposal_id = created.data["id"]
        item = created.data["items"][0]
        shared_parent = FoodItem.objects.get(pk=item["food_item_id"])
        shared_child = FoodItem.objects.get(pk=item["components"][0]["food_item_id"])
        self.assertEqual(shared_parent.scope, FoodItem.Scope.SHARED)
        self.assertEqual(shared_child.scope, FoodItem.Scope.SHARED)
        self.assertEqual(
            shared_parent.current_version.components.get().child_version_id,
            shared_child.current_version_id,
        )
        self.assertEqual(created.data["items"][0]["nutrients"]["calories"], "400")
        item["components"][0]["servings"] = "1"
        item["source_kind"] = "official_verified"
        item["provenance"] = "official"
        item["nutrients"]["calories"] = "1"
        updated = self.client.patch(
            f"/api/meal-proposals/{proposal_id}/",
            {
                "name": "Cheese-free burger",
                "notes": "Extra crispy, please.",
                "entry_date": "2026-08-17",
                "items": [item],
            },
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(str(updated.data["entry_date"]), "2026-08-17")
        self.assertEqual(updated.data["notes"], "Extra crispy, please.")
        self.assertEqual(updated.data["items"][0]["nutrients"]["calories"], "200")
        self.assertEqual(
            updated.data["items"][0]["source_kind"], "user_modified_estimate"
        )
        self.assertEqual(
            updated.data["items"][0]["provenance"], "user_modified_estimate"
        )

        accepted = self.client.post(f"/api/meal-proposals/{proposal_id}/accept/")

        self.assertEqual(accepted.status_code, 201)
        proposal = MealProposal.objects.get(pk=proposal_id)
        self.assertEqual(accepted.data["confidence_score"], "0.800")
        self.assertEqual(proposal.provider_name, "OpenAI")
        self.assertEqual(proposal.provider_model, "gpt-test")
        self.assertEqual(proposal.provider_response_id, "resp_test")
        self.assertEqual(proposal.status, MealProposal.Status.ACCEPTED)
        meal = MealEntry.objects.get(pk=accepted.data["id"])
        self.assertEqual(meal.owner, self.user)
        self.assertEqual(str(meal.entry_date), "2026-08-17")
        self.assertEqual(meal.name, "Cheese-free burger")
        self.assertEqual(
            meal.notes,
            "Extra crispy, please.\n\n"
            "Estimated from: A restaurant burger without cheese",
        )
        saved_item = meal.items.get()
        self.assertEqual(saved_item.calories, Decimal("200"))
        self.assertEqual(saved_item.component_snapshot[0]["food_name"], "Burger patty")
        self.assertEqual(saved_item.component_snapshot[0]["servings"], "1.0000")
        self.assertEqual(
            saved_item.food_version.food_item.scope, FoodItem.Scope.PERSONAL
        )
        self.assertEqual(
            saved_item.food_version.provenance,
            FoodItemVersion.Provenance.USER_MODIFIED_ESTIMATE,
        )
        self.assertEqual(saved_item.food_version.derived_from.food_item.scope, "shared")
        self.assertEqual(
            saved_item.food_version.sources.get().url,
            "https://example.com/nutrition",
        )

        second_accept = self.client.post(f"/api/meal-proposals/{proposal_id}/accept/")
        self.assertEqual(second_accept.status_code, 400)
        edit_after_accept = self.client.patch(
            f"/api/meal-proposals/{proposal_id}/",
            {"name": "Changed"},
            format="json",
        )
        self.assertEqual(edit_after_accept.status_code, 400)

    def test_ai_proposal_rounds_provider_values_to_storage_precision(self):
        estimate = ai_estimate()
        item = estimate["items"][0]
        component = item["components"][0]
        item["servings"] = "1.23456"
        item["serving_quantity"] = "1.23456"
        item["confidence_score"] = "0.87654"
        component["servings"] = "1.23456"
        component["serving_quantity"] = "0.33333"
        component["confidence_score"] = "0.65432"
        component["nutrients"]["calories"] = "200.123456"
        provider = Mock()
        provider.estimate.return_value = estimate

        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            created = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "A precisely estimated restaurant burger",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(created.status_code, 201)
        accepted = self.client.post(f"/api/meal-proposals/{created.data['id']}/accept/")

        self.assertEqual(accepted.status_code, 201)
        saved_item = MealEntry.objects.get(pk=accepted.data["id"]).items.get()
        self.assertEqual(saved_item.servings, Decimal("1.2346"))
        self.assertEqual(saved_item.food_version.serving_quantity, Decimal("1.235"))
        self.assertEqual(saved_item.food_version.confidence_score, Decimal("0.877"))
        saved_component = saved_item.food_version.components.get()
        self.assertEqual(saved_component.servings, Decimal("1.2346"))
        self.assertEqual(
            saved_component.child_version.serving_quantity, Decimal("0.333")
        )
        self.assertEqual(
            saved_component.child_version.confidence_score, Decimal("0.654")
        )
        self.assertEqual(saved_component.child_version.calories, Decimal("200.1235"))

    def test_ai_proposal_accepts_reviewed_component_nutrients(self):
        provider = Mock()
        provider.estimate.return_value = ai_estimate()
        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            created = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "A restaurant burger with adjusted nutrition",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        item = created.data["items"][0]
        item["components"][0]["nutrients"]["calories"] = "175"
        item["components"][0]["nutrients"]["protein"] = "10"
        updated = self.client.patch(
            f"/api/meal-proposals/{created.data['id']}/",
            {"items": [item]},
            format="json",
        )

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["items"][0]["nutrients"]["calories"], "350")
        self.assertEqual(updated.data["items"][0]["nutrients"]["protein"], "20")
        accepted = self.client.post(f"/api/meal-proposals/{created.data['id']}/accept/")
        self.assertEqual(accepted.status_code, 201)
        saved_item = MealEntry.objects.get(pk=accepted.data["id"]).items.get()
        self.assertEqual(saved_item.calories, Decimal("350"))
        saved_component = saved_item.food_version.components.get()
        self.assertEqual(saved_component.child_version.calories, Decimal("175"))
        self.assertEqual(saved_component.child_version.protein, Decimal("10"))

    def test_ai_proposal_rolls_up_known_nutrients_when_a_component_is_unknown(self):
        estimate = ai_estimate()
        first_component = estimate["items"][0]["components"][0]
        first_component["nutrients"]["carbohydrates"] = None
        second_component = deepcopy(first_component)
        second_component["key"] = "ai-0.1"
        second_component["name"] = "Burger bun"
        second_component["servings"] = "1"
        second_component["nutrients"]["protein"] = None
        second_component["nutrients"]["carbohydrates"] = "30"
        estimate["items"][0]["components"].append(second_component)
        provider = Mock()
        provider.estimate.return_value = estimate

        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            created = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "A burger with a bun",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        self.assertEqual(created.status_code, 201)
        nutrients = created.data["items"][0]["nutrients"]
        self.assertEqual(nutrients["protein"], "24")
        self.assertEqual(nutrients["carbohydrates"], "30")

    def test_catalog_nutrient_adjustment_creates_a_personal_copy(self):
        catalog_food = shared_food(name="Protein bar")
        created = self.client.post(
            "/api/meal-proposals/",
            {"description": "Protein bar", "entry_date": "2026-08-16"},
            format="json",
        )
        item = created.data["items"][0]
        item["nutrients"]["calories"] = "125"

        updated = self.client.patch(
            f"/api/meal-proposals/{created.data['id']}/",
            {"items": [item]},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        accepted = self.client.post(f"/api/meal-proposals/{created.data['id']}/accept/")

        self.assertEqual(accepted.status_code, 201)
        saved_version = (
            MealEntry.objects.get(pk=accepted.data["id"]).items.get().food_version
        )
        self.assertNotEqual(saved_version.food_item_id, catalog_food.pk)
        self.assertEqual(saved_version.food_item.scope, FoodItem.Scope.PERSONAL)
        self.assertEqual(
            saved_version.provenance,
            FoodItemVersion.Provenance.USER_MODIFIED_ESTIMATE,
        )
        self.assertEqual(saved_version.calories, Decimal("125"))
        catalog_food.refresh_from_db()
        self.assertEqual(catalog_food.current_version.calories, Decimal("100"))

    def test_multiple_servings_are_multiplied_exactly_once_when_accepted(self):
        estimate = simple_ai_estimate(name="Hash Browns", calories="140")
        item = estimate["items"][0]
        item.update(
            {
                "servings": "5.5",
                "serving_label": "1 hash brown",
                "serving_weight_grams": "53",
                "nutrients": {
                    "calories": "140",
                    "protein": "1",
                    "carbohydrates": "18",
                    "fat": "8",
                    "fiber": "2",
                    "sugar": "0",
                    "sodium": "310",
                    "cholesterol": "0",
                },
            }
        )
        provider = Mock()
        provider.estimate.return_value = estimate
        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            created = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "5.5 McDonald's hash browns",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        accepted = self.client.post(f"/api/meal-proposals/{created.data['id']}/accept/")

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["items"][0]["nutrients"]["calories"], "140")
        self.assertEqual(accepted.status_code, 201)
        saved_item = MealEntry.objects.get(pk=accepted.data["id"]).items.get()
        self.assertEqual(saved_item.servings, Decimal("5.5"))
        self.assertEqual(saved_item.calories, Decimal("770"))
        self.assertEqual(saved_item.carbohydrates, Decimal("99"))
        self.assertEqual(saved_item.fat, Decimal("44"))

    def test_proposal_revisions_preserve_generated_reviewed_and_accepted_values(self):
        provider = Mock()
        provider.estimate.return_value = simple_ai_estimate()
        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            created = self.client.post(
                "/api/meal-proposals/",
                {"description": "A single apple", "entry_date": "2026-08-16"},
                format="json",
            )

        item = created.data["items"][0]
        item["nutrients"]["calories"] = "250"
        reviewed = self.client.patch(
            f"/api/meal-proposals/{created.data['id']}/",
            {"items": [item]},
            format="json",
        )
        accepted = self.client.post(f"/api/meal-proposals/{created.data['id']}/accept/")

        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(accepted.status_code, 201)
        revisions = list(
            MealProposalRevision.objects.filter(proposal_id=created.data["id"])
        )
        self.assertEqual(
            [revision.kind for revision in revisions],
            [
                MealProposalRevision.Kind.GENERATED,
                MealProposalRevision.Kind.USER_REVIEWED,
                MealProposalRevision.Kind.ACCEPTED,
            ],
        )
        self.assertEqual(revisions[0].items[0]["nutrients"]["calories"], "95")
        self.assertEqual(revisions[1].items[0]["nutrients"]["calories"], "250")
        self.assertEqual(revisions[1].parent_revision, revisions[0])
        self.assertEqual(revisions[2].parent_revision, revisions[1])
        saved_version = (
            MealEntry.objects.get(pk=accepted.data["id"]).items.get().food_version
        )
        self.assertEqual(
            saved_version.provenance,
            FoodItemVersion.Provenance.USER_MODIFIED_ESTIMATE,
        )
        self.assertEqual(
            saved_version.derived_from_id, revisions[0].items[0]["food_version_id"]
        )

    def test_edited_draft_can_be_deleted_without_removing_shared_base(self):
        provider = Mock()
        provider.estimate.return_value = simple_ai_estimate()
        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            created = self.client.post(
                "/api/meal-proposals/",
                {"description": "A single apple", "entry_date": "2026-08-16"},
                format="json",
            )

        item = created.data["items"][0]
        item["nutrients"]["calories"] = "100"
        reviewed = self.client.patch(
            f"/api/meal-proposals/{created.data['id']}/",
            {"items": [item]},
            format="json",
        )
        deleted = self.client.delete(f"/api/meal-proposals/{created.data['id']}/")

        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(MealProposal.objects.filter(pk=created.data["id"]).exists())
        self.assertFalse(
            MealProposalRevision.objects.filter(proposal_id=created.data["id"]).exists()
        )
        self.assertTrue(
            FoodItem.objects.filter(name="Apple", scope=FoodItem.Scope.SHARED).exists()
        )

    def test_proposals_are_owner_scoped(self):
        MealProposal.objects.create(
            owner=self.other_user,
            description="Private meal",
            entry_date=date(2026, 8, 16),
            name="Private meal",
            generator=MealProposal.Generator.CATALOG,
            items=[],
        )
        response = self.client.get("/api/meal-proposals/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_proposal_edits_reject_non_finite_numbers(self):
        provider = Mock()
        provider.estimate.return_value = ai_estimate()
        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            created = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "A burger with invalid numeric edits",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        invalid_edits = (
            ("servings", "NaN"),
            ("nutrient", "Infinity"),
            ("confidence", "-Infinity"),
        )
        for field, value in invalid_edits:
            with self.subTest(field=field, value=value):
                item = deepcopy(created.data["items"][0])
                if field == "servings":
                    item["servings"] = value
                elif field == "nutrient":
                    item["nutrients"]["calories"] = value
                else:
                    item["confidence_score"] = value

                response = self.client.patch(
                    f"/api/meal-proposals/{created.data['id']}/",
                    {"items": [item]},
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("finite number", str(response.data))

        proposal = MealProposal.objects.get(pk=created.data["id"])
        self.assertEqual(proposal.status, MealProposal.Status.DRAFT)
        self.assertFalse(MealEntry.objects.exists())

    def test_proposal_edits_cannot_inject_untrusted_portion_options(self):
        provider = Mock()
        provider.estimate.return_value = ai_estimate()
        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            created = self.client.post(
                "/api/meal-proposals/",
                {
                    "description": "A burger with portion choices",
                    "entry_date": "2026-08-16",
                },
                format="json",
            )

        item = deepcopy(created.data["items"][0])
        item["portion_options"].append(
            {
                "key": "triple",
                "label": "Untrusted triple portion",
                "unit_label": "triple",
                "serving_multiplier": "3",
            }
        )
        item["selected_portion_key"] = "triple"

        response = self.client.patch(
            f"/api/meal-proposals/{created.data['id']}/",
            {"items": [item]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("could not be validated", str(response.data))

    def test_provider_failure_returns_safe_service_unavailable(self):
        provider = Mock()
        provider.estimate.side_effect = EstimationProviderError("Provider unavailable.")
        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            response = self.client.post(
                "/api/meal-proposals/",
                {"description": "Unknown meal", "entry_date": "2026-08-16"},
                format="json",
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.data["detail"],
            "The meal estimation service is temporarily unavailable. "
            "Try again or log the meal manually.",
        )
        self.assertFalse(MealProposal.objects.exists())
