"""Proposal follow-up fields, catalog additions and reviewed metadata."""

from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase

from apps.foods.models import FoodItem

from ..models import MealProposal
from .helpers import ProposalFixtures, shared_food, simple_ai_estimate


class ProposalFollowUpTests(ProposalFixtures, TestCase):
    def test_follow_up_addition_reuses_a_matching_catalog_food(self):
        shared_food(name="Burger")
        kfc_fries = shared_food(
            name="KFC Crinkle Cut Fries",
            provider_name="KFC",
            origin_type=FoodItem.OriginType.RESTAURANT,
        )
        proposal_response = self.client.post(
            "/api/meal-proposals/",
            {"description": "Burger", "entry_date": "2026-08-16"},
            format="json",
        )
        addition = simple_ai_estimate(
            name="KFC Secret Recipe Fries",
            calories="320",
        )["items"][0]
        addition.update(
            {
                "provider_name": "KFC",
                "origin_type": FoodItem.OriginType.RESTAURANT,
                "_catalog_search": {
                    "search_name": "fries",
                    "provider_name": "KFC",
                    "quantity": 1,
                    "defining_terms": ["fries"],
                    "aliases": ["Crinkle Cut Fries"],
                },
            }
        )
        provider = Mock()
        provider.follow_up.return_value = {
            "name": "Burger & KFC Fries",
            "message": "Added one order of KFC fries.",
            "confidence_score": Decimal("0.8"),
            "remove_keys": [],
            "serving_updates": [],
            "items_to_add": [addition],
            "provider_name": "OpenAI",
            "provider_model": "gpt-test",
            "provider_response_id": "resp_follow_up",
        }
        food_count = FoodItem.objects.count()

        with patch(
            "apps.estimates.views.get_estimation_provider", return_value=provider
        ):
            response = self.client.post(
                f"/api/meal-proposals/{proposal_response.data['id']}/follow-up/",
                {
                    "follow_up": "I also had fries from KFC",
                    "name": proposal_response.data["name"],
                    "items": proposal_response.data["items"],
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["proposal"]["name"], "Burger & KFC Fries")
        self.assertEqual(FoodItem.objects.count(), food_count)
        self.assertEqual(
            response.data["proposal"]["items"][1]["food_item_id"],
            kfc_fries.pk,
        )
        self.assertEqual(
            response.data["proposal"]["items"][1]["nutrients"]["calories"],
            "100",
        )

    def test_ai_generated_proposal_round_trips_through_follow_up_validation(self):
        provider = Mock()
        provider.estimate.return_value = simple_ai_estimate(name="Apple", calories="95")

        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            proposal_response = self.client.post(
                "/api/meal-proposals/",
                {"description": "A single apple", "entry_date": "2026-08-16"},
                format="json",
            )

        self.assertEqual(proposal_response.status_code, 201)
        self.assertNotIn("_catalog_search", proposal_response.data["items"][0])
        provider.follow_up.return_value = {
            "name": "Half Apple",
            "message": "Changed the apple to half a serving.",
            "confidence_score": Decimal("0.9"),
            "remove_keys": [],
            "serving_updates": [
                {"key": proposal_response.data["items"][0]["key"], "servings": 0.5}
            ],
            "items_to_add": [],
            "provider_name": "OpenAI",
            "provider_model": "gpt-test",
            "provider_response_id": "resp_follow_up_round_trip",
        }

        with patch(
            "apps.estimates.views.get_estimation_provider", return_value=provider
        ):
            response = self.client.post(
                f"/api/meal-proposals/{proposal_response.data['id']}/follow-up/",
                {
                    "follow_up": "I only ate half the apple",
                    "name": proposal_response.data["name"],
                    "notes": "Use the homemade version.",
                    "entry_date": "2026-08-18",
                    "items": proposal_response.data["items"],
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["applied"])
        self.assertEqual(
            Decimal(response.data["proposal"]["items"][0]["servings"]),
            Decimal("0.5"),
        )
        self.assertEqual(response.data["proposal"]["name"], "Half Apple")
        self.assertEqual(
            response.data["proposal"]["notes"], "Use the homemade version."
        )
        self.assertEqual(str(response.data["proposal"]["entry_date"]), "2026-08-18")
        self.assertEqual(
            response.data["proposal"]["revisions"][-1]["message"],
            "Changed the apple to half a serving.",
        )
        self.assertEqual(
            response.data["proposal"]["revisions"][-1]["follow_up"],
            "I only ate half the apple",
        )
        self.assertEqual(
            response.data["proposal"]["revisions"][-1]["notes"],
            "Use the homemade version.",
        )

        provider.follow_up.return_value = {
            "name": "Quarter Apple",
            "message": "Changed the apple to a quarter serving.",
            "confidence_score": Decimal("0.85"),
            "remove_keys": [],
            "serving_updates": [
                {
                    "key": response.data["proposal"]["items"][0]["key"],
                    "servings": 0.25,
                }
            ],
            "items_to_add": [],
            "provider_name": "OpenAI",
            "provider_model": "gpt-test",
            "provider_response_id": "resp_second_follow_up",
        }
        with patch(
            "apps.estimates.views.get_estimation_provider", return_value=provider
        ):
            second_response = self.client.post(
                f"/api/meal-proposals/{proposal_response.data['id']}/follow-up/",
                {
                    "follow_up": "Actually, I only ate a quarter",
                    "name": response.data["proposal"]["name"],
                    "items": response.data["proposal"]["items"],
                },
                format="json",
            )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.data["proposal"]["name"], "Quarter Apple")
        accepted = self.client.post(
            f"/api/meal-proposals/{proposal_response.data['id']}/accept/"
        )
        self.assertEqual(accepted.status_code, 201)
        self.assertEqual(str(accepted.data["entry_date"]), "2026-08-18")
        self.assertEqual(accepted.data["name"], "Quarter Apple")
        self.assertEqual(
            accepted.data["notes"],
            "Use the homemade version.\n\n"
            "Estimated from: A single apple\n\n"
            "AI adjustments:\n"
            "- I only ate half the apple\n"
            "- Actually, I only ate a quarter",
        )

    def test_follow_up_persists_reviewed_fields_when_no_food_change_applies(self):
        shared_food(name="Apple")
        proposal_response = self.client.post(
            "/api/meal-proposals/",
            {"description": "Apple", "entry_date": "2026-08-16"},
            format="json",
        )
        provider = Mock()
        provider.follow_up.return_value = {
            "name": proposal_response.data["name"],
            "message": "No applicable food changes were found.",
            "confidence_score": Decimal("0.9"),
            "remove_keys": [],
            "serving_updates": [],
            "items_to_add": [],
            "provider_name": "OpenAI",
            "provider_model": "gpt-test",
            "provider_response_id": "resp_no_food_change",
        }

        with patch(
            "apps.estimates.views.get_estimation_provider", return_value=provider
        ):
            response = self.client.post(
                f"/api/meal-proposals/{proposal_response.data['id']}/follow-up/",
                {
                    "follow_up": "Move this meal to Monday",
                    "name": proposal_response.data["name"],
                    "notes": "Move this entry, but keep my note.",
                    "entry_date": "2026-08-17",
                    "items": proposal_response.data["items"],
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["applied"])
        self.assertEqual(
            response.data["proposal"]["notes"],
            "Move this entry, but keep my note.",
        )
        self.assertEqual(str(response.data["proposal"]["entry_date"]), "2026-08-17")
        proposal = MealProposal.objects.get(pk=proposal_response.data["id"])
        self.assertEqual(proposal.entry_date, date(2026, 8, 17))
        self.assertEqual(proposal.notes, "Move this entry, but keep my note.")
