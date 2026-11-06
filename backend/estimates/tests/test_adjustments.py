from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from meals.models import MealEntry

from ..models import MealProposal, MealProposalRevision
from ..provider import EstimationProviderError
from ..services import apply_proposal_follow_up
from .helpers import shared_food


class MealAdjustmentLifecycleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="owner", email="owner@example.com", password="secret-pass"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        shared_food(name="Apple")
        response = self.client.post(
            "/api/meal-proposals/",
            {"description": "Apple", "entry_date": "2026-08-16"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.proposal = MealProposal.objects.get(pk=response.data["id"])
        self.payload = {
            "adjustment": "Make that two apples",
            "entry_date": "2026-08-16",
            "name": "Apple",
            "items": response.data["items"],
        }
        self.meal = MealEntry.objects.create(
            owner=self.user, entry_date=date(2026, 8, 16), name="Saved apple"
        )
        self.endpoints = (
            ("/api/meal-proposals/adjustments/", "estimates.views"),
            (f"/api/meals/{self.meal.pk}/adjustments/", "meals.views"),
        )
        self.provider = Mock()
        self.provider.follow_up.return_value = {
            "serving_updates": [
                {"key": self.payload["items"][0]["key"], "servings": "2"}
            ],
        }
        self.original_proposals = list(MealProposal.objects.values())
        self.original_revisions = list(MealProposalRevision.objects.values())

    def assert_original_proposals_preserved(self):
        self.assertEqual(list(MealProposal.objects.values()), self.original_proposals)
        self.assertEqual(
            list(MealProposalRevision.objects.values()), self.original_revisions
        )
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.name, "Saved apple")

    def test_provider_failure_cleans_up_both_adjustment_endpoints(self):
        self.provider.follow_up.side_effect = EstimationProviderError("Unavailable")
        for url, view in self.endpoints:
            with self.subTest(url=url):
                with patch(
                    f"{view}.get_estimation_provider", return_value=self.provider
                ):
                    response = self.client.post(url, self.payload, format="json")
                self.assertEqual(response.status_code, 503, response.data)
                self.assert_original_proposals_preserved()

    def test_provider_resolution_failure_cleans_up_both_adjustment_endpoints(self):
        for url, view in self.endpoints:
            with self.subTest(url=url):
                with patch(
                    f"{view}.get_estimation_provider",
                    side_effect=RuntimeError("Provider initialization failed"),
                ):
                    with self.assertRaisesMessage(
                        RuntimeError, "initialization failed"
                    ):
                        self.client.post(url, self.payload, format="json")
                self.assert_original_proposals_preserved()

    def test_follow_up_processing_failure_cleans_up_both_adjustment_endpoints(self):
        for url, view in self.endpoints:
            for error in (
                DjangoValidationError("Invalid follow-up"),
                RuntimeError("Follow-up processing failed"),
            ):
                with self.subTest(url=url, error=type(error).__name__):
                    self.provider.follow_up.reset_mock()
                    with (
                        patch(
                            f"{view}.get_estimation_provider",
                            return_value=self.provider,
                        ),
                        patch(
                            "estimates.services.apply_proposal_follow_up",
                            side_effect=error,
                        ),
                    ):
                        if isinstance(error, DjangoValidationError):
                            response = self.client.post(
                                url, self.payload, format="json"
                            )
                            self.assertEqual(response.status_code, 400, response.data)
                        else:
                            with self.assertRaisesMessage(
                                RuntimeError, "processing failed"
                            ):
                                self.client.post(url, self.payload, format="json")
                    self.provider.follow_up.assert_called_once()
                    self.assert_original_proposals_preserved()

    def test_serialization_failure_cleans_up_both_adjustment_endpoints(self):
        for url, view in self.endpoints:
            with self.subTest(url=url):
                with (
                    patch(
                        f"{view}.get_estimation_provider", return_value=self.provider
                    ),
                    patch(
                        "estimates.serializers.MealProposalSerializer.to_representation",
                        side_effect=RuntimeError("Response serialization failed"),
                    ),
                ):
                    with self.assertRaisesMessage(RuntimeError, "serialization failed"):
                        self.client.post(url, self.payload, format="json")
                self.assert_original_proposals_preserved()

    def test_missing_follow_up_fields_preserve_confidence_and_provider_metadata(self):
        self.proposal.provider_name = "Original provider"
        self.proposal.provider_model = "Original model"
        self.proposal.provider_response_id = "Original response"
        self.proposal.save()
        optional_fields = (
            "remove_keys",
            "items_to_add",
            "provider_name",
            "provider_model",
            "provider_response_id",
            "name",
            "message",
            "confidence_score",
        )
        for fields in ({}, dict.fromkeys(optional_fields)):
            with self.subTest(fields=fields):
                outcome = apply_proposal_follow_up(
                    proposal=self.proposal,
                    owner=self.user,
                    follow_up="Change servings",
                    items=self.proposal.items,
                    result={
                        **fields,
                        "serving_updates": [
                            {"key": self.proposal.items[0]["key"], "servings": "2"}
                        ],
                    },
                )
                self.assertTrue(outcome["applied"])
                self.assertEqual(outcome["message"], "")
                self.proposal.refresh_from_db()
                self.assertEqual(self.proposal.confidence_score, Decimal("0.990"))
                self.assertEqual(self.proposal.provider_name, "Original provider")
                self.assertEqual(self.proposal.provider_model, "Original model")
                self.assertEqual(
                    self.proposal.provider_response_id, "Original response"
                )
                self.assertEqual(self.proposal.name, "Apple")
                self.assertEqual(
                    Decimal(self.proposal.items[0]["servings"]), Decimal("2")
                )

    def test_absent_follow_up_collections_leave_proposal_unchanged(self):
        for fields in (
            {},
            {"remove_keys": None, "serving_updates": None, "items_to_add": None},
        ):
            with self.subTest(fields=fields):
                outcome = apply_proposal_follow_up(
                    proposal=self.proposal,
                    owner=self.user,
                    follow_up="No changes",
                    items=self.proposal.items,
                    result=fields,
                )
                self.assertFalse(outcome["applied"])
                self.assert_original_proposals_preserved()
