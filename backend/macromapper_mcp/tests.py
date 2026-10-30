"""Offline business/ownership/confirmation regressions; never call a real provider."""

import asyncio
import json
from copy import deepcopy
from datetime import date, timedelta
from threading import Event
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import Mock, patch

from asgiref.sync import async_to_sync, sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import Http404
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from estimates.models import MealProposal
from estimates.services import create_proposal
from estimates.tests import ai_estimate
from foods.models import FoodItem
from foods.services import create_food_item, create_food_version
from meals.models import MealEntry
from notifications.models import Notification

from . import services
from .auth import ESTIMATE, READ, WRITE
from .models import Confirmation


def definition(calories="100"):
    return {
        "serving_quantity": "1",
        "serving_unit": "item",
        "serving_label": "one item",
        "provenance": "user_entered",
        "confidence_score": "0.900",
        "nutrients": {"calories": calories},
        "sources": [],
        "components": [],
    }


class DisabledDiscoveryTests(SimpleTestCase):
    def test_domain_app_and_registry_import_do_not_require_enabled_oauth_models(self):
        from .server import Action

        self.assertIn("meal.delete", Action.__args__)
        self.assertEqual(len(services.OPERATIONS), 19)


class Fixtures:
    def setUp(self):
        from oauth2_provider.models import AccessToken, Application

        self.user = get_user_model().objects.create_user(
            "mcp-owner", email="mcp-owner@example.test"
        )
        self.other = get_user_model().objects.create_user(
            "mcp-other", email="mcp-other@example.test"
        )
        self.application = Application.objects.create(
            name="MCP fixture",
            client_id="mcp-fixture",
            client_type="public",
            authorization_grant_type="authorization-code",
            redirect_uris="https://client.example/callback",
        )
        self.token = AccessToken.objects.create(
            user=self.user,
            application=self.application,
            token="fixture-local-token",
            scope=" ".join([READ, WRITE, ESTIMATE]),
            expires=timezone.now() + timedelta(hours=1),
            resource=[settings.MCP_RESOURCE_URL],
        )
        self.raw = "fixture-local-token"
        self.food = create_food_item(
            name="Apple",
            scope="shared",
            origin_type="generic",
            provider_name="",
            owner=None,
            definition=definition(),
            created_by=None,
        )

    def meal_payload(self):
        return {
            "entry_date": "2026-10-30",
            "name": "Lunch",
            "notes": "exact preview",
            "item_inputs": [{"food_item": self.food.pk, "servings": "1", "order": 0}],
        }

    def preview(self, action="meal.create", target=None, payload=None):
        return services.preview_change(
            self.raw,
            action,
            target,
            payload if payload is not None else self.meal_payload(),
            services.OPERATIONS[action].paid,
        )

    def confirm(self, pending):
        return services.confirm_change(
            self.raw, pending["confirmation_id"], True, pending["paid"]
        )

    def make_meal(self):
        return MealEntry.objects.get(
            pk=self.confirm(self.preview())["result"]["data"]["id"]
        )


@skipUnless(settings.MCP_ENABLED, "Run the enabled app-owned OAuth profile")
class DomainTests(Fixtures, TestCase):
    def test_preview_then_single_confirm_update_delete_and_no_ai(self):
        with patch(
            "meals.views.generate_meal_name",
            side_effect=AssertionError("No implicit AI"),
        ):
            preview = self.preview()
            self.assertFalse(MealEntry.objects.exists())
            meal = MealEntry.objects.get(
                pk=self.confirm(preview)["result"]["data"]["id"]
            )
        with self.assertRaises(ValidationError):
            self.confirm(preview)
        self.assertEqual(MealEntry.objects.count(), 1)
        update = self.preview("meal.update", meal.pk, {"name": "Updated"})
        self.confirm(update)
        meal.refresh_from_db()
        self.assertEqual(meal.name, "Updated")
        delete = self.preview("meal.delete", meal.pk, {})
        self.confirm(delete)
        self.assertFalse(MealEntry.objects.exists())

    def test_ownership_and_shared_catalog_are_not_staff_bypassable(self):
        foreign = MealEntry.objects.create(
            owner=self.other, entry_date=date.today(), name="Private"
        )
        with self.assertRaises(Http404):
            self.preview("meal.delete", foreign.pk, {})
        with self.assertRaises(Http404):
            services.get_record(self.raw, "meals", foreign.pk)
        self.user.is_staff = True
        self.user.save()
        with self.assertRaises(APIException):
            self.preview("food.archive", self.food.pk, {})
        self.assertTrue(MealEntry.objects.filter(pk=foreign.pk).exists())

    def test_personal_food_create_update_archive_uses_rest_validation(self):
        payload = {
            "name": "Personal food",
            "origin_type": "generic",
            "provider_name": "",
            "definition": definition(),
        }
        food_id = self.confirm(self.preview("food.create", payload=payload))["result"][
            "data"
        ]["id"]
        food = FoodItem.objects.get(pk=food_id)
        self.assertEqual(food.owner_id, self.user.pk)
        self.confirm(self.preview("food.update", food_id, {"name": "Renamed"}))
        self.confirm(self.preview("food.archive", food_id, {}))
        food.refresh_from_db()
        self.assertIsNotNone(food.archived_at)

    def test_state_and_catalog_changes_reject_stale_confirmation(self):
        meal = self.make_meal()
        pending = self.preview("meal.update", meal.pk, {"name": "Would overwrite"})
        meal.name = "Website changed"
        meal.save()
        with self.assertRaises(ValidationError):
            self.confirm(pending)
        meal.refresh_from_db()
        self.assertEqual(meal.name, "Website changed")
        pending = self.preview()
        create_food_version(
            food_item=self.food, definition=definition("200"), created_by=self.user
        )
        with self.assertRaises(ValidationError):
            self.confirm(pending)
        self.assertEqual(MealEntry.objects.count(), 1)

    def test_scopes_expiry_revocation_resource_and_unknown_bearers(self):
        from oauth2_provider.models import AccessToken

        self.token.scope = READ
        self.token.save()
        self.assertEqual(
            len(services.list_records(self.raw, "foods", {}, 10, 0)["data"]), 1
        )
        with self.assertRaises(PermissionDenied):
            self.preview()
        self.token.scope = " ".join([READ, WRITE])
        self.token.save()
        with self.assertRaises(PermissionDenied):
            self.preview(
                "proposal.estimate",
                payload={"description": "An unknown meal", "entry_date": "2026-10-30"},
            )
        self.token.resource = ["https://notoli.judeandrewalaba.com/mcp"]
        self.token.save()
        with self.assertRaises(PermissionDenied):
            services.list_records(self.raw, "foods", {}, 10, 0)
        self.token.delete()
        for raw in [self.raw, "eyJ.central-issuer-token", "rest-jwt-fixture"]:
            with self.assertRaises(PermissionDenied):
                services.list_records(raw, "foods", {}, 10, 0)
        self.assertFalse(AccessToken.objects.exists())

    def test_paid_and_nonpaid_tool_kinds_cannot_be_mixed_or_consume_approval(self):
        nonpaid = self.preview()
        paid = self.preview(
            "proposal.estimate",
            payload={"description": "Apple", "entry_date": "2026-10-30"},
        )
        for pending, wrong_kind in [(paid, False), (nonpaid, True), (paid, 1)]:
            with self.assertRaises(ValidationError):
                services.confirm_change(
                    self.raw, pending["confirmation_id"], True, wrong_kind
                )
            self.assertTrue(
                Confirmation.objects.filter(pk=pending["confirmation_id"]).exists()
            )
        with self.assertRaises(ValidationError):
            services.preview_change(
                self.raw,
                "proposal.estimate",
                None,
                {"description": "Apple", "entry_date": "2026-10-30"},
                False,
            )
        with self.assertRaises(ValidationError):
            services.preview_change(
                self.raw, "meal.create", None, self.meal_payload(), True
            )
        self.token.scope = " ".join([READ, WRITE])
        self.token.save()
        with self.assertRaises(PermissionDenied):
            services.confirm_change(self.raw, paid["confirmation_id"], True, True)
        self.assertTrue(
            Confirmation.objects.filter(pk=paid["confirmation_id"]).exists()
        )
        self.assertTrue(self.confirm(nonpaid)["applied"])
        self.assertFalse(MealProposal.objects.exists())

    def test_confirmation_binds_owner_client_token_and_requires_real_boolean(self):
        from oauth2_provider.models import AccessToken, Application

        pending = self.preview()
        other_client = Application.objects.create(
            name="Other",
            client_id="other-client",
            client_type="public",
            authorization_grant_type="authorization-code",
            redirect_uris="https://other.example/callback",
        )
        for user, application in [
            (self.other, self.application),
            (self.user, other_client),
            (self.user, self.application),
        ]:
            token = AccessToken.objects.create(
                user=user,
                application=application,
                token="different-" + str(user.pk) + application.client_id,
                scope=" ".join([READ, WRITE]),
                expires=timezone.now() + timedelta(hours=1),
                resource=[settings.MCP_RESOURCE_URL],
            )
            with self.assertRaises(ValidationError):
                services.confirm_change(
                    token.token, pending["confirmation_id"], True, False
                )
        for value in [False, 1, "true"]:
            with self.assertRaises(ValidationError):
                services.confirm_change(
                    self.raw, pending["confirmation_id"], value, False
                )
        Confirmation.objects.filter(pk=pending["confirmation_id"]).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        with self.assertRaises(ValidationError):
            self.confirm(pending)
        self.assertFalse(MealEntry.objects.exists())

    def test_unknown_readonly_nested_nonfinite_and_unbounded_inputs(self):
        for payload in [
            {**self.meal_payload(), "owner": self.other.pk},
            {**self.meal_payload(), "id": 999},
            {
                **self.meal_payload(),
                "item_inputs": [
                    {"food_item": self.food.pk, "servings": "NaN", "order": 0}
                ],
            },
            {
                **self.meal_payload(),
                "item_inputs": [
                    {
                        "food_item": self.food.pk,
                        "servings": "1",
                        "order": 0,
                        "unknown": True,
                    }
                ],
            },
        ]:
            with self.assertRaises((ValidationError, ValueError)):
                self.preview(payload=payload)
        for limit, offset in [(21, 0), (0, 0), (True, 0), (10, 1001)]:
            with self.assertRaises(ValidationError):
                services.list_records(self.raw, "foods", {}, limit, offset)
        for coerced in [True, str(self.food.pk)]:
            with self.assertRaises(ValidationError):
                self.preview(
                    payload=self.meal_payload()
                    | {
                        "item_inputs": [
                            {"food_item": coerced, "servings": "1", "order": 0}
                        ]
                    }
                )
        with self.assertRaises(ValidationError):
            services.json_value({"items": list(range(101))})
        with self.assertRaises(ValidationError):
            self.preview(target=True)
        self.assertFalse(MealEntry.objects.exists())

    def test_notifications_all_six_capabilities_and_arrival_isolation(self):
        notification = Notification.objects.create(
            recipient=self.user, title="Own", message="A notification"
        )
        foreign = Notification.objects.create(
            recipient=self.other, title="Foreign", message="Private"
        )
        self.assertEqual(
            len(services.list_records(self.raw, "notifications", {}, 10, 0)["data"]), 1
        )
        self.assertEqual(
            services.get_record(self.raw, "notifications", notification.pk)["data"][
                "id"
            ],
            notification.pk,
        )
        with self.assertRaises(Http404):
            services.get_record(self.raw, "notifications", foreign.pk)
        self.confirm(
            self.preview("notification.update", notification.pk, {"is_read": True})
        )
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)
        all_read = self.preview("notification.mark_all_read", payload={})
        arrived = Notification.objects.create(
            recipient=self.user, title="New", message="After preview"
        )
        self.confirm(all_read)
        arrived.refresh_from_db()
        self.assertFalse(arrived.is_read)
        clear = self.preview("notification.clear_all", payload={})
        later = Notification.objects.create(
            recipient=self.user, title="Later", message="Keep"
        )
        self.confirm(clear)
        self.assertEqual(
            Notification.objects.filter(pk__in=[foreign.pk, later.pk]).count(), 2
        )
        self.confirm(self.preview("notification.delete", later.pk, {}))
        self.assertFalse(Notification.objects.filter(pk=later.pk).exists())

    def test_schema_exposes_typed_writable_fields_and_no_querysets(self):
        schema = services.operation_schema(self.raw, "food.create")["data"]
        self.assertIn("definition", schema["fields"])
        self.assertTrue(schema["fields"]["definition"]["required"])
        self.assertNotIn("scope", schema["fields"])
        self.assertIn("nutrients", schema["fields"]["definition"]["fields"])
        self.assertNotIn("owner", schema["fields"])
        paid = services.operation_schema(self.raw, "proposal.estimate")["data"]
        self.assertEqual(set(paid["fields"]), {"description", "entry_date"})
        self.assertTrue(paid["paid"])

    def test_catalog_drafts_proposal_review_acceptance_and_bounded_reads(self):
        from estimates.services import (
            _catalog_food,
            create_builder_proposal,
            prepare_builder_proposal,
        )

        fields = dict(
            owner=self.user,
            entry_date=date(2026, 10, 30),
            name="Draft",
            notes="",
            items=[_catalog_food(self.food.current_version)],
        )
        # The extracted preparation helper is pure; the existing REST helper
        # still persists exactly the same proposal and initial revision policy.
        prepared = prepare_builder_proposal(**fields)
        self.assertFalse(MealProposal.objects.exists())
        proposal = create_builder_proposal(**fields)
        self.assertEqual(proposal.name, prepared["name"])
        updated = self.confirm(
            self.preview("proposal.update", proposal.pk, {"name": "Reviewed"})
        )
        self.assertEqual(updated["result"]["data"]["name"], "Reviewed")
        with self.assertRaises(ValidationError):
            self.preview(
                "proposal.update", proposal.pk, {"description": "ignored by REST"}
            )
        self.confirm(self.preview("proposal.delete", proposal.pk, {}))
        draft = self.confirm(
            self.preview(
                "meal.draft_create",
                payload={
                    "entry_date": "2026-10-30",
                    "name": "Catalog diary",
                    "notes": "",
                    "items": fields["items"],
                },
            )
        )
        meal_id = draft["result"]["data"]["id"]
        with self.assertRaises(ValidationError):
            self.preview(
                "meal.draft_update",
                meal_id,
                {"entry_date": "2026-10-30", "notes": "", "items": fields["items"]},
            )
        self.assertTrue(
            services.operation_schema(self.raw, "meal.draft_update")["data"]["fields"][
                "name"
            ]["required"]
        )
        self.confirm(
            self.preview(
                "meal.draft_update",
                meal_id,
                {
                    "entry_date": "2026-10-30",
                    "name": "Renamed",
                    "notes": "",
                    "items": fields["items"],
                },
            )
        )
        listing = services.list_records(self.raw, "meals", {"date": "2026-10-30"}, 1, 0)
        self.assertEqual(listing["data"][0]["name"], "Renamed")
        self.assertEqual(
            services.nutrition_totals(self.raw, date(2026, 10, 30), date(2026, 10, 30))[
                "data"
            ]["meal_count"],
            1,
        )
        with self.assertRaises(ValidationError):
            services.nutrition_totals(self.raw, date(2026, 1, 1), date(2026, 2, 1))
        self.assertEqual(
            services.list_records(self.raw, "foods", {"search": "Apple"}, 10, 0)[
                "data"
            ][0]["id"],
            self.food.pk,
        )
        # Build through the existing catalog service, then separately confirm
        # acceptance into the diary rather than treating estimates as meals.
        proposal = create_builder_proposal(
            **(fields | {"items": [_catalog_food(self.food.current_version)]})
        )
        accepted = self.confirm(self.preview("proposal.accept", proposal.pk, {}))
        self.assertTrue(
            MealEntry.objects.filter(
                pk=accepted["result"]["data"]["id"], owner=self.user
            ).exists()
        )
        with self.assertRaises(ValidationError):
            self.preview("proposal.update", proposal.pk, {"name": "Too late"})

    def test_pending_confirmation_budget_and_stale_notification(self):
        notice = Notification.objects.create(
            recipient=self.user, title="Bound", message="Old"
        )
        pending = self.preview("notification.delete", notice.pk, {})
        Notification.objects.filter(pk=notice.pk).update(message="Changed")
        with self.assertRaises(ValidationError):
            self.confirm(pending)
        for _ in range(9):
            self.preview()
        with self.assertRaises(ValidationError):
            self.preview()
        self.assertFalse(MealEntry.objects.exists())


@skipUnless(settings.MCP_ENABLED, "Run the enabled app-owned OAuth profile")
class PaidOperationTests(Fixtures, TransactionTestCase):
    def test_oversized_paid_estimate_returns_receipt_for_committed_proposal(self):
        estimate = deepcopy(ai_estimate())
        estimate["items"] = []
        for index in range(20):
            item = deepcopy(ai_estimate()["items"][0])
            item.update(key=f"ai-{index}", name=f"Different restaurant food {index}")
            item["components"][0]["key"] = f"ai-{index}.0"
            estimate["items"].append(item)
        provider = self.provider()
        provider.estimate.side_effect = None
        provider.estimate.return_value = estimate
        with patch("estimates.services.get_estimation_provider", return_value=provider):
            result = self.confirm(
                self.preview(
                    "proposal.estimate",
                    payload={
                        "description": "A varied unknown buffet",
                        "entry_date": "2026-10-30",
                    },
                )
            )
        self.assertTrue(result["applied"])
        self.assertTrue(result["result"]["truncated"])
        receipt = result["result"]["data"]
        proposal = MealProposal.objects.get(pk=receipt["proposal_id"])
        self.assertTrue(receipt["proposal_retained"])
        self.assertEqual(receipt["item_count"], len(proposal.items))
        self.assertFalse(receipt["diary_mutated"])
        self.assertLess(len(json.dumps(receipt).encode()), 65536)
        self.assertFalse(MealEntry.objects.exists())

    def test_oversized_temporary_adjustment_returns_honest_bounded_summary(self):
        from estimates.services import _catalog_food

        meal = self.make_meal()
        pending = self.preview(
            "meal.adjustment",
            meal.pk,
            {
                "entry_date": "2026-10-30",
                "name": "Adjusted",
                "notes": "",
                "items": [_catalog_food(self.food.current_version)],
                "adjustment": "Smaller",
            },
        )
        # Valid existing proposal data can become large through revision snapshots.
        # Use the actual service/write/delete path; inflate only its serializer output.
        from estimates.serializers import MealProposalSerializer

        original = MealProposalSerializer.to_representation

        def large_representation(serializer, instance):
            output = original(serializer, instance)
            output["revisions"] = [
                {"items": [{"notes": "x" * 2000} for _ in range(20)]} for _ in range(20)
            ]
            return output

        provider = Mock(
            follow_up=Mock(return_value={"applied": False, "message": "No change"})
        )
        with (
            patch("estimates.provider.get_estimation_provider", return_value=provider),
            patch.object(
                MealProposalSerializer, "to_representation", large_representation
            ),
        ):
            result = self.confirm(pending)
        self.assertTrue(result["result"]["truncated"])
        receipt = result["result"]["data"]
        self.assertEqual(receipt["source_meal_id"], meal.pk)
        self.assertEqual(receipt["effect"], "temporary_adjustment_only")
        self.assertIsNone(receipt["proposal_id"])
        self.assertIsInstance(receipt["temporary_proposal_id"], int)
        self.assertFalse(receipt["proposal_retained"])
        self.assertFalse(receipt["diary_mutated"])
        self.assertEqual(receipt["items"][0]["name"], self.food.name)
        self.assertFalse(MealProposal.objects.exists())
        meal.refresh_from_db()
        self.assertEqual(meal.name, "Lunch")

    def test_paid_wait_does_not_block_other_users_or_auth_and_cancellation_holds_slot(
        self,
    ):
        from oauth2_provider.models import AccessToken

        from mcp_framework.server import DjangoTokenVerifier

        from . import server

        other_raw = "other-worker-token"
        AccessToken.objects.create(
            user=self.other,
            application=self.application,
            token=other_raw,
            scope=READ,
            resource=[settings.MCP_RESOURCE_URL],
            expires=timezone.now() + timedelta(hours=1),
        )
        pending = self.preview(
            "proposal.estimate",
            payload={
                "description": "An unknown restaurant dish",
                "entry_date": "2026-10-30",
            },
        )
        unstarted = self.preview()
        started, release, finished = Event(), Event(), Event()
        invoke = server.invocation

        def track_invocation(*args):
            try:
                return invoke(*args)
            finally:
                if args[0] is services.confirm_change:
                    finished.set()

        def provider_wait():
            started.set()
            if not release.wait(5):
                raise AssertionError("Test did not release provider")

        async def exercise():
            with patch.object(
                server,
                "get_access_token",
                side_effect=[
                    SimpleNamespace(token=self.raw),
                    SimpleNamespace(token=self.raw),
                    SimpleNamespace(token=other_raw),
                ],
            ):
                paid = asyncio.create_task(
                    server.call(
                        services.confirm_change, pending["confirmation_id"], True, True
                    )
                )
                try:
                    self.assertTrue(await asyncio.to_thread(started.wait, 3))
                    # Cancel only the request; its synchronous authorized operation
                    # must retain its bounded slot until the provider/worker ends.
                    paid.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        self.assertIsNone(await paid)
                    acquired = 0
                    try:
                        for _ in range(3):
                            self.assertTrue(server._SLOTS.acquire(blocking=False))
                            acquired += 1
                        self.assertFalse(server._SLOTS.acquire(blocking=False))
                        with self.assertRaises(server.ToolError):
                            await server.call(
                                services.confirm_change,
                                unstarted["confirmation_id"],
                                True,
                                False,
                            )
                    finally:
                        for _ in range(acquired):
                            server._SLOTS.release()
                    read, verified = await asyncio.wait_for(
                        asyncio.gather(
                            server.call(services.list_records, "foods", {}, 10, 0),
                            DjangoTokenVerifier().verify_token(other_raw),
                        ),
                        timeout=2,
                    )
                    self.assertEqual(read["data"][0]["id"], self.food.pk)
                    self.assertEqual(verified.subject, str(self.other.pk))
                finally:
                    release.set()
                    self.assertTrue(await asyncio.to_thread(finished.wait, 5))

        with (
            patch(
                "estimates.services.get_estimation_provider",
                return_value=self.provider(provider_wait),
            ),
            patch.object(server, "invocation", side_effect=track_invocation),
        ):
            async_to_sync(exercise)()
        self.assertEqual(MealProposal.objects.filter(owner=self.user).count(), 1)
        self.assertFalse(
            Confirmation.objects.filter(pk=pending["confirmation_id"]).exists()
        )
        self.assertTrue(
            Confirmation.objects.filter(pk=unstarted["confirmation_id"]).exists()
        )

    def test_catalog_only_optional_hook_is_atomic_and_default_unchanged(self):
        def denied():
            self.assertTrue(connection.in_atomic_block)
            self.assertFalse(MealProposal.objects.exists())
            raise PermissionDenied("Revoked")

        with patch(
            "estimates.services.get_estimation_provider",
            side_effect=AssertionError("No provider for catalog match"),
        ):
            with self.assertRaises(PermissionDenied):
                create_proposal(
                    owner=self.user,
                    description="Apple",
                    entry_date=date.today(),
                    before_apply=denied,
                )
            self.assertFalse(MealProposal.objects.exists())
            proposal = create_proposal(
                owner=self.user, description="Apple", entry_date=date.today()
            )
            self.assertEqual(proposal.generator, MealProposal.Generator.CATALOG)

    def provider(self, callback=None):
        provider = Mock()
        provider.extract_intents.return_value = None

        def estimate(description):
            self.assertFalse(
                connection.in_atomic_block,
                "Provider cannot hold a database writer transaction",
            )
            if callback:
                callback()
            return deepcopy(ai_estimate())

        provider.estimate.side_effect = estimate
        return provider

    def test_paid_estimate_is_confirmed_one_use_and_default_rest_still_works(self):
        payload = {
            "description": "A completely unknown restaurant dish",
            "entry_date": "2026-10-30",
        }
        provider = self.provider()
        with patch("estimates.services.get_estimation_provider", return_value=provider):
            pending = self.preview("proposal.estimate", payload=payload)
            provider.estimate.assert_not_called()
            self.confirm(pending)
            self.assertEqual(MealProposal.objects.filter(owner=self.user).count(), 1)
            with self.assertRaises(ValidationError):
                self.confirm(pending)
            self.assertEqual(provider.estimate.call_count, 1)
            # Existing caller omits the new optional hook and retains its behavior.
            create_proposal(
                owner=self.user,
                description="Another unknown dish",
                entry_date=date.today(),
            )
            self.assertEqual(MealProposal.objects.filter(owner=self.user).count(), 2)

    def test_revocation_or_inactive_user_during_provider_prevents_all_data_apply(self):
        for mutation in [
            "revoke",
            "deactivate",
            "scope",
            "resource",
            "owner",
            "client",
        ]:
            with self.subTest(mutation=mutation):
                self.token.refresh_from_db()
                self.token.scope = " ".join([READ, WRITE, ESTIMATE])
                self.token.resource = [settings.MCP_RESOURCE_URL]
                self.token.user = self.user
                self.token.application = self.application
                self.token.expires = timezone.now() + timedelta(hours=1)
                self.token.save()
                self.user.is_active = True
                self.user.save()
                pending = self.preview(
                    "proposal.estimate",
                    payload={
                        "description": "An unknown dish",
                        "entry_date": "2026-10-30",
                    },
                )
                initial_foods = FoodItem.objects.count()

                def revoke():
                    if mutation == "revoke":
                        self.token.expires = timezone.now() - timedelta(seconds=1)
                        self.token.save()
                    elif mutation == "deactivate":
                        get_user_model().objects.filter(pk=self.user.pk).update(
                            is_active=False
                        )
                    elif mutation == "scope":
                        type(self.token).objects.filter(pk=self.token.pk).update(
                            scope=READ
                        )
                    elif mutation == "resource":
                        type(self.token).objects.filter(pk=self.token.pk).update(
                            resource=["https://other.example/mcp"]
                        )
                    elif mutation == "owner":
                        type(self.token).objects.filter(pk=self.token.pk).update(
                            user=self.other
                        )
                    else:
                        type(self.application).objects.filter(
                            pk=self.application.pk
                        ).update(client_id="changed-client")

                with patch(
                    "estimates.services.get_estimation_provider",
                    return_value=self.provider(revoke),
                ):
                    with self.assertRaises(PermissionDenied):
                        self.confirm(pending)
                self.assertFalse(MealProposal.objects.exists())
                self.assertEqual(FoodItem.objects.count(), initial_foods)
                self.assertFalse(
                    Confirmation.objects.filter(pk=pending["confirmation_id"]).exists()
                )
                self.application.client_id = "mcp-fixture"
                self.application.save()

    def test_adjustment_wait_has_no_business_writes_and_rejects_stale_meal(self):
        from estimates.services import _catalog_food

        meal = self.make_meal()
        payload = {
            "entry_date": "2026-10-30",
            "name": "Adjusted",
            "notes": "",
            "items": [_catalog_food(self.food.current_version)],
            "adjustment": "Less apple",
        }
        for stale in [False, True]:
            pending = self.preview("meal.adjustment", meal.pk, payload)
            initial_foods = FoodItem.objects.count()

            def follow_up(**kwargs):
                self.assertFalse(connection.in_atomic_block)
                self.assertFalse(MealProposal.objects.exists())
                self.assertEqual(FoodItem.objects.count(), initial_foods)
                if stale:
                    MealEntry.objects.filter(pk=meal.pk).update(
                        notes="Concurrent website edit"
                    )
                return {"applied": False, "message": "No safe adjustment", "items": []}

            provider = Mock(follow_up=Mock(side_effect=follow_up))
            with patch(
                "estimates.provider.get_estimation_provider", return_value=provider
            ):
                if stale:
                    with self.assertRaises(ValidationError):
                        self.confirm(pending)
                else:
                    outcome = self.confirm(pending)
                    self.assertFalse(outcome["result"]["data"]["applied"])
            self.assertFalse(MealProposal.objects.exists())
            self.assertEqual(FoodItem.objects.count(), initial_foods)
            self.assertFalse(
                Confirmation.objects.filter(pk=pending["confirmation_id"]).exists()
            )

    def test_proposal_follow_up_rechecks_state_and_scope_after_provider(self):
        from estimates.services import _catalog_food, create_builder_proposal

        proposal = create_builder_proposal(
            owner=self.user,
            entry_date=date(2026, 10, 30),
            name="Review",
            notes="",
            items=[_catalog_food(self.food.current_version)],
        )
        payload = {
            "name": proposal.name,
            "items": proposal.items,
            "follow_up": "A smaller serving",
        }
        for mutation in ["stale", "scope"]:
            pending = self.preview("proposal.follow_up", proposal.pk, payload)
            revisions = proposal.revisions.count()

            def follow_up(**kwargs):
                self.assertFalse(connection.in_atomic_block)
                if mutation == "scope":
                    type(self.token).objects.filter(pk=self.token.pk).update(scope=READ)
                else:
                    MealProposal.objects.filter(pk=proposal.pk).update(
                        notes="Website edit"
                    )
                return {"applied": False, "message": "No change", "items": []}

            with patch(
                "estimates.provider.get_estimation_provider",
                return_value=Mock(follow_up=Mock(side_effect=follow_up)),
            ):
                with self.assertRaises((PermissionDenied, ValidationError)):
                    self.confirm(pending)
            self.assertEqual(proposal.revisions.count(), revisions)
            self.assertFalse(MealEntry.objects.exists())

    def test_new_adjustment_revocation_prevents_even_temporary_proposal_writes(self):
        from estimates.services import _catalog_food

        pending = self.preview(
            "proposal.adjustment",
            payload={
                "entry_date": "2026-10-30",
                "name": "Unpersisted builder",
                "notes": "",
                "items": [_catalog_food(self.food.current_version)],
                "adjustment": "Smaller portion",
            },
        )

        def follow_up(**kwargs):
            self.assertFalse(connection.in_atomic_block)
            self.assertFalse(MealProposal.objects.exists())
            type(self.token).objects.filter(pk=self.token.pk).delete()
            return {"applied": False, "message": "No change", "items": []}

        with patch(
            "estimates.provider.get_estimation_provider",
            return_value=Mock(follow_up=Mock(side_effect=follow_up)),
        ):
            with self.assertRaises(PermissionDenied):
                self.confirm(pending)
        self.assertFalse(MealProposal.objects.exists())
        self.assertEqual(FoodItem.objects.count(), 1)


@skipUnless(settings.MCP_ENABLED, "Run the enabled app-owned OAuth profile")
class ProtocolTests(Fixtures, TransactionTestCase):
    def test_actual_factory_discovery_read_confirmation_and_revocation(self):
        import httpx2
        from django.core.asgi import get_asgi_application

        from mcp_framework.asgi import create_application

        application = create_application(get_asgi_application())

        async def exercise():
            async with application.router.lifespan_context(application):
                async with httpx2.AsyncClient(
                    transport=httpx2.ASGITransport(app=application),
                    base_url=settings.MCP_BASE_URL,
                ) as client:
                    headers = {
                        "Accept": "application/json, text/event-stream",
                        "MCP-Protocol-Version": "2025-11-25",
                    }

                    async def rpc(method, params=None):
                        return await client.post(
                            "/mcp",
                            headers=headers,
                            json={
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": method,
                                "params": params or {},
                            },
                        )

                    self.assertEqual((await rpc("tools/list")).status_code, 401)
                    metadata = await client.get(
                        "/.well-known/oauth-protected-resource/mcp"
                    )
                    self.assertEqual(
                        metadata.json()["resource"], settings.MCP_RESOURCE_URL
                    )
                    headers["Authorization"] = f"Bearer {self.raw}"
                    self.assertEqual(
                        (
                            await rpc(
                                "initialize",
                                {
                                    "protocolVersion": "2025-11-25",
                                    "capabilities": {},
                                    "clientInfo": {
                                        "name": "domain-test",
                                        "version": "1",
                                    },
                                },
                            )
                        ).status_code,
                        200,
                    )
                    listing = (await rpc("tools/list")).json()["result"]["tools"]
                    tools = {tool["name"]: tool for tool in listing}
                    self.assertEqual(len(tools), 18)
                    self.assertNotIn("connection_status", tools)
                    self.assertTrue(
                        tools["search_foods"]["annotations"]["readOnlyHint"]
                    )
                    self.assertTrue(
                        tools["confirm_change"]["annotations"]["destructiveHint"]
                    )
                    self.assertFalse(
                        tools["confirm_change"]["annotations"]["openWorldHint"]
                    )
                    self.assertTrue(
                        tools["confirm_paid_change"]["annotations"]["openWorldHint"]
                    )
                    for name in ["preview_change", "confirm_change"]:
                        self.assertEqual(
                            tools[name]["_meta"]["securitySchemes"],
                            [{"type": "oauth2", "scopes": [READ, WRITE]}],
                        )
                    for name in ["preview_paid_change", "confirm_paid_change"]:
                        self.assertEqual(
                            tools[name]["_meta"]["securitySchemes"],
                            [{"type": "oauth2", "scopes": [READ, WRITE, ESTIMATE]}],
                        )
                    self.assertEqual(
                        tools["search_foods"]["_meta"]["securitySchemes"],
                        [{"type": "oauth2", "scopes": [READ]}],
                    )
                    nonpaid_actions = set(
                        tools["preview_change"]["inputSchema"]["properties"]["action"][
                            "enum"
                        ]
                    )
                    paid_actions = set(
                        tools["preview_paid_change"]["inputSchema"]["properties"][
                            "action"
                        ]["enum"]
                    )
                    self.assertEqual(
                        paid_actions,
                        {
                            "proposal.estimate",
                            "proposal.follow_up",
                            "proposal.adjustment",
                            "meal.adjustment",
                        },
                    )
                    self.assertFalse(nonpaid_actions & paid_actions)
                    self.assertEqual(
                        nonpaid_actions | paid_actions, set(services.OPERATIONS)
                    )
                    self.assertIn(
                        "meal.delete",
                        tools["preview_change"]["inputSchema"]["properties"]["action"][
                            "enum"
                        ],
                    )

                    async def tool(name, arguments):
                        response = await rpc(
                            "tools/call", {"name": name, "arguments": arguments}
                        )
                        self.assertEqual(response.status_code, 200, response.text)
                        return response.json()["result"]

                    foods = await tool("search_foods", {"query": "Apple"})
                    self.assertEqual(
                        foods["structuredContent"]["data"][0]["id"], self.food.pk
                    )
                    pending = await tool(
                        "preview_change",
                        {"action": "meal.create", "changes": self.meal_payload()},
                    )
                    confirmation = pending["structuredContent"]["confirmation_id"]
                    applied = await tool(
                        "confirm_change",
                        {"confirmation_id": confirmation, "confirmed": True},
                    )
                    self.assertTrue(applied["structuredContent"]["applied"])
                    paid_arguments = {
                        "action": "proposal.estimate",
                        "changes": {"description": "Apple", "entry_date": "2026-10-30"},
                    }
                    self.assertTrue(
                        (await tool("preview_change", paid_arguments))["isError"]
                    )
                    paid_preview = (await tool("preview_paid_change", paid_arguments))[
                        "structuredContent"
                    ]
                    paid_confirmation = {
                        "confirmation_id": paid_preview["confirmation_id"],
                        "confirmed": True,
                    }
                    self.assertIn("confirm_paid_change", paid_preview["instruction"])
                    self.assertTrue(
                        (await tool("confirm_change", paid_confirmation))["isError"]
                    )
                    nonpaid_preview = (
                        await tool(
                            "preview_change",
                            {"action": "meal.create", "changes": self.meal_payload()},
                        )
                    )["structuredContent"]
                    nonpaid_confirmation = {
                        "confirmation_id": nonpaid_preview["confirmation_id"],
                        "confirmed": True,
                    }
                    self.assertTrue(
                        (await tool("confirm_paid_change", nonpaid_confirmation))[
                            "isError"
                        ]
                    )
                    await sync_to_async(
                        type(self.token).objects.filter(pk=self.token.pk).update
                    )(scope=" ".join([READ, WRITE]))
                    self.assertTrue(
                        (await tool("preview_paid_change", paid_arguments))["isError"]
                    )
                    self.assertTrue(
                        (await tool("confirm_paid_change", paid_confirmation))[
                            "isError"
                        ]
                    )
                    self.assertTrue(
                        (await tool("confirm_change", nonpaid_confirmation))[
                            "structuredContent"
                        ]["applied"]
                    )
                    # Regrant the separate paid permission: the earlier mismatches
                    # and insufficient-scope calls must not have consumed approval.
                    await sync_to_async(
                        type(self.token).objects.filter(pk=self.token.pk).update
                    )(scope=" ".join([READ, WRITE, ESTIMATE]))
                    self.assertTrue(
                        (await tool("confirm_paid_change", paid_confirmation))[
                            "structuredContent"
                        ]["applied"]
                    )
                    self.assertTrue(
                        (
                            await tool(
                                "confirm_change",
                                {"confirmation_id": confirmation, "confirmed": True},
                            )
                        )["isError"]
                    )
                    self.assertTrue(
                        (
                            await tool(
                                "preview_change",
                                {
                                    "action": "meal.create",
                                    "changes": self.meal_payload(),
                                    "target_id": True,
                                },
                            )
                        )["isError"]
                    )
                    await sync_to_async(
                        type(self.token).objects.filter(pk=self.token.pk).update
                    )(scope=READ)
                    self.assertTrue(
                        (
                            await tool(
                                "preview_change",
                                {
                                    "action": "meal.create",
                                    "changes": self.meal_payload(),
                                },
                            )
                        )["isError"]
                    )
                    await sync_to_async(self.token.delete)()
                    self.assertEqual((await rpc("tools/list")).status_code, 401)

        async_to_sync(exercise)()
