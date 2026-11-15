"""Paid duplicate protection, bounded provider waits and guarded atomic receipts."""

import asyncio
import json
from copy import deepcopy
from datetime import date, timedelta
from threading import Event
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import Mock, patch

from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import Http404
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.estimates.models import MealProposal
from apps.estimates.services import _catalog_food, create_proposal
from apps.estimates.tests.helpers import ai_estimate
from apps.foods.models import FoodItem
from apps.meals.models import MealEntry

from .. import queries, services
from ..models import Execution
from ..permissions import ESTIMATE, READ, WRITE
from .helpers import MCPToolFixtures


@skipUnless(settings.MCP_ENABLED, "Run the enabled app-owned OAuth profile")
class PaidOperationTests(MCPToolFixtures, TransactionTestCase):
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
        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            result = self.execute(
                self.request(
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
        # A successful paid receipt must remain recoverable without another
        # provider call, even when its full revision snapshots exceed the budget.
        listing = queries.list_records(self.raw, "proposals", {}, 10, 0)
        self.assertEqual(listing["data"][0]["id"], proposal.pk)
        detail = queries.get_record(self.raw, "proposals", proposal.pk)
        self.assertEqual(detail["data"]["id"], proposal.pk)
        reviewed = []
        while True:
            self.assertFalse(detail["truncated"])
            self.assertNotIn("revisions", detail["data"])
            reviewed.extend(detail["data"]["items"])
            self.assertLess(len(json.dumps(detail).encode()), 65536)
            if not detail["has_more"]:
                break
            detail = queries.get_proposal(
                self.raw, proposal.pk, 20, detail["next_offset"]
            )
        self.assertEqual(reviewed, proposal.items)
        self.assertEqual(provider.estimate.call_count, 1)
        with self.assertRaises(Http404):
            queries.get_proposal(self.raw, proposal.pk + 1000)
        for limit, offset in [(True, 0), (1, -1), (21, 0), (1, True)]:
            with self.assertRaises(ValidationError):
                queries.get_proposal(self.raw, proposal.pk, limit, offset)
        # A single large component tree must produce an honest summary, not
        # partial editable items or a new opaque failure.
        item = deepcopy(proposal.items[0])
        child = deepcopy(item["components"][0])
        child["components"] = [deepcopy(child) for _ in range(20)]
        item["components"] = [deepcopy(child) for _ in range(20)]
        proposal.items = [item]
        proposal.save(update_fields=["items"])
        oversized = queries.get_proposal(self.raw, proposal.pk, 1, 0)
        self.assertTrue(oversized["truncated"])
        self.assertEqual(oversized["data"]["id"], proposal.pk)
        self.assertNotIn("items", oversized["data"])
        self.assertIn("MacroMapper", oversized["data"]["detail"])
        for partial_item in [
            deepcopy(reviewed[0])
            | {
                "components": [
                    deepcopy(reviewed[0]["components"][0]) for _ in range(21)
                ]
            },
            deepcopy(proposal.items[0]) | {"name": "x" * 2001, "components": []},
        ]:
            proposal.items = [partial_item]
            proposal.save(update_fields=["items"])
            partial = queries.get_proposal(self.raw, proposal.pk)
            self.assertTrue(partial["truncated"])
            self.assertNotIn("items", partial["data"])
            self.assertIn("review/edit/accept", partial["data"]["detail"])
        other_proposal = MealProposal.objects.create(
            owner=self.other,
            description="Other private meal",
            entry_date=date(2026, 10, 31),
            name="Private",
            generator="catalog",
            items=[],
        )
        with self.assertRaises(Http404):
            queries.get_proposal(self.raw, other_proposal.pk)
        self.assertEqual(provider.estimate.call_count, 1)

    def test_paid_estimate_review_portion_accept_and_replay_log_exactly_once(self):
        estimate = deepcopy(ai_estimate())
        dessert = deepcopy(estimate["items"][0])
        dessert.update(key="dessert", name="Full dessert", components=[])
        estimate["items"].append(dessert)
        provider = self.provider()
        provider.estimate.side_effect = None
        provider.estimate.return_value = estimate
        pending = self.request(
            "proposal.estimate",
            payload={
                "description": "Unknown recipe plus dessert",
                "entry_date": "2026-10-31",
            },
        )
        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            created = self.execute(pending)
            self.assertTrue(self.execute(pending)["replayed"])
        proposal_id = created["result"]["data"]["id"]
        self.assertEqual(provider.estimate.call_count, 1)
        self.assertFalse(MealEntry.objects.exists())
        review = queries.get_proposal(self.raw, proposal_id)["data"]
        self.assertFalse(
            queries.list_records(self.raw, "proposals", {}, 10, 0)["has_more"]
        )
        review["items"][0]["servings"] = "0.7"
        review["items"][1]["servings"] = "1"
        self.execute(
            self.request(
                "proposal.update",
                proposal_id,
                {"name": "Reviewed breakfast", "items": review["items"]},
            )
        )
        acceptance = self.request("proposal.accept", proposal_id, {})
        saved = self.execute(acceptance)
        self.assertTrue(self.execute(acceptance)["replayed"])
        meal = MealEntry.objects.get(pk=saved["result"]["data"]["id"])
        self.assertEqual(MealEntry.objects.count(), 1)
        self.assertEqual(
            [str(item.servings) for item in meal.items.order_by("order")],
            ["0.7000", "1.0000"],
        )
        self.assertEqual(
            MealProposal.objects.get(pk=proposal_id).accepted_meal_id, meal.pk
        )
        self.assertEqual(provider.estimate.call_count, 1)

    def test_oversized_temporary_adjustment_returns_honest_bounded_summary(self):

        meal = self.make_meal()
        pending = self.request(
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
        from apps.estimates.serializers import MealProposalSerializer

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
            patch(
                "apps.estimates.provider.get_estimation_provider", return_value=provider
            ),
            patch.object(
                MealProposalSerializer, "to_representation", large_representation
            ),
        ):
            result = self.execute(pending)
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

        from apps.mcp.framework.server import DjangoTokenVerifier

        from .. import server

        other_raw = "other-worker-token"
        AccessToken.objects.create(
            user=self.other,
            application=self.application,
            token=other_raw,
            scope=READ,
            resource=[settings.MCP_RESOURCE_URL],
            expires=timezone.now() + timedelta(hours=1),
        )
        pending = self.request(
            "proposal.estimate",
            payload={
                "description": "An unknown restaurant dish",
                "entry_date": "2026-10-30",
            },
        )
        unstarted = self.request()
        pending_arguments = self.prepare_approved(pending)
        unstarted_arguments = self.prepare_approved(unstarted)
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
                        services.confirm_change,
                        *pending_arguments,
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
                                *unstarted_arguments,
                            )
                    finally:
                        for _ in range(acquired):
                            server._SLOTS.release()
                    read, verified = await asyncio.wait_for(
                        asyncio.gather(
                            server.call(queries.list_records, "foods", {}, 10, 0),
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
                "apps.estimates.services.get_estimation_provider",
                return_value=self.provider(provider_wait),
            ),
            patch.object(server, "invocation", side_effect=track_invocation),
        ):
            async_to_sync(exercise)()
        self.assertEqual(MealProposal.objects.filter(owner=self.user).count(), 1)
        self.assertEqual(
            Execution.objects.get(pk=pending["request_id"]).state,
            Execution.State.COMPLETED,
        )
        self.assertEqual(
            Execution.objects.get(pk=unstarted["request_id"]).state,
            Execution.State.APPROVED,
        )

    def test_catalog_only_optional_hook_is_atomic_and_default_unchanged(self):
        def denied():
            self.assertTrue(connection.in_atomic_block)
            self.assertFalse(MealProposal.objects.exists())
            raise PermissionDenied("Revoked")

        with patch(
            "apps.estimates.services.get_estimation_provider",
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

    def test_paid_estimate_executes_once_and_default_rest_still_works(self):
        payload = {
            "description": "A completely unknown restaurant dish",
            "entry_date": "2026-10-30",
        }
        provider = self.provider()
        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            pending = self.request("proposal.estimate", payload=payload)
            provider.estimate.assert_not_called()
            self.execute(pending)
            self.assertEqual(MealProposal.objects.filter(owner=self.user).count(), 1)
            self.assertTrue(self.execute(pending)["replayed"])
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
                pending = self.request(
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
                    "apps.estimates.services.get_estimation_provider",
                    return_value=self.provider(revoke),
                ):
                    with self.assertRaises(PermissionDenied):
                        self.execute(pending)
                self.assertFalse(MealProposal.objects.exists())
                self.assertEqual(FoodItem.objects.count(), initial_foods)
                self.assertEqual(
                    Execution.objects.get(pk=pending["request_id"]).state,
                    Execution.State.UNCERTAIN,
                )
                self.application.client_id = "mcp-fixture"
                self.application.save()

    def test_adjustment_wait_has_no_business_writes_and_rejects_stale_meal(self):

        meal = self.make_meal()
        payload = {
            "entry_date": "2026-10-30",
            "name": "Adjusted",
            "notes": "",
            "items": [_catalog_food(self.food.current_version)],
            "adjustment": "Less apple",
        }
        for stale in [False, True]:
            pending = self.request("meal.adjustment", meal.pk, payload)
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
                "apps.estimates.provider.get_estimation_provider", return_value=provider
            ):
                if stale:
                    with self.assertRaises(ValidationError):
                        self.execute(pending)
                else:
                    outcome = self.execute(pending)
                    self.assertFalse(outcome["result"]["data"]["applied"])
                    self.assertFalse(outcome["applied"])
                    self.assertEqual(outcome["status"], "completed")
            self.assertFalse(MealProposal.objects.exists())
            self.assertEqual(FoodItem.objects.count(), initial_foods)
            self.assertEqual(
                Execution.objects.get(pk=pending["request_id"]).state,
                Execution.State.UNCERTAIN if stale else Execution.State.COMPLETED,
            )

    def test_proposal_follow_up_rechecks_state_and_scope_after_provider(self):
        from apps.estimates.services import create_builder_proposal

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
            pending = self.request("proposal.follow_up", proposal.pk, payload)
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
                "apps.estimates.provider.get_estimation_provider",
                return_value=Mock(follow_up=Mock(side_effect=follow_up)),
            ):
                with self.assertRaises((PermissionDenied, ValidationError)):
                    self.execute(pending)
            self.assertEqual(proposal.revisions.count(), revisions)
            self.assertFalse(MealEntry.objects.exists())

    def test_new_adjustment_revocation_prevents_even_temporary_proposal_writes(self):

        pending = self.request(
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
            "apps.estimates.provider.get_estimation_provider",
            return_value=Mock(follow_up=Mock(side_effect=follow_up)),
        ):
            with self.assertRaises(PermissionDenied):
                self.execute(pending)
        self.assertFalse(MealProposal.objects.exists())
        self.assertEqual(FoodItem.objects.count(), 1)

    def test_receipt_failure_rolls_back_catalog_and_provider_publication_without_retry(
        self,
    ):
        from django.db import DatabaseError

        for description in ["Apple", "Completely unknown receipt failure dish"]:
            with self.subTest(description=description):
                request = self.request(
                    "proposal.estimate",
                    payload={"description": description, "entry_date": "2026-10-30"},
                )
                provider = self.provider()
                before = FoodItem.objects.count()
                with patch(
                    "apps.estimates.services.get_estimation_provider",
                    return_value=provider,
                ):
                    with patch.object(
                        services,
                        "_complete",
                        side_effect=DatabaseError("receipt write failed"),
                    ):
                        with self.assertRaises(DatabaseError):
                            self.execute(request)
                    recovered = self.execute(request)
                self.assertEqual(recovered["status"], "uncertain")
                self.assertIsNone(recovered["applied"])
                self.assertTrue(recovered["replayed"])
                self.assertFalse(MealProposal.objects.exists())
                self.assertEqual(FoodItem.objects.count(), before)
                self.assertEqual(
                    provider.estimate.call_count, 0 if description == "Apple" else 1
                )

    def test_ambiguous_provider_failure_is_durable_and_never_retried(self):
        request = self.request(
            "proposal.estimate",
            payload={
                "description": "Unknown ambiguous dish",
                "entry_date": "2026-10-30",
            },
        )
        provider = self.provider()
        provider.estimate.side_effect = TimeoutError("private provider body")
        with patch(
            "apps.estimates.services.get_estimation_provider", return_value=provider
        ):
            with self.assertRaises(TimeoutError):
                self.execute(request)
            recovered = self.execute(request)
        self.assertEqual(recovered["status"], "uncertain")
        self.assertIsNone(recovered["applied"])
        self.assertNotIn("private provider body", str(recovered))
        self.assertEqual(provider.estimate.call_count, 1)
        self.assertFalse(MealProposal.objects.exists())

    def test_concurrent_duplicate_observes_reservation_then_cached_success(self):
        from .. import server

        request = self.request(
            "proposal.estimate",
            payload={
                "description": "Concurrent unknown dish",
                "entry_date": "2026-10-30",
            },
        )
        started, release = Event(), Event()

        def wait_for_release():
            started.set()
            if not release.wait(5):
                raise AssertionError("Provider test was not released")

        provider = self.provider(wait_for_release)
        confirmation_arguments = self.prepare_approved(request)

        async def exercise():
            first = asyncio.create_task(
                server.call(services.confirm_change, *confirmation_arguments)
            )
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 3))
                duplicate = await server.call(
                    services.confirm_change, *confirmation_arguments
                )
                self.assertEqual(duplicate["status"], "in_progress")
                self.assertIsNone(duplicate["applied"])
            finally:
                release.set()
            completed = await first
            replay = await server.call(services.confirm_change, *confirmation_arguments)
            self.assertEqual(completed["status"], "completed")
            self.assertTrue(replay["replayed"])
            self.assertEqual(replay["result"], completed["result"])

        with (
            patch.object(
                server, "get_access_token", return_value=SimpleNamespace(token=self.raw)
            ),
            patch(
                "apps.estimates.services.get_estimation_provider", return_value=provider
            ),
        ):
            async_to_sync(exercise)()
        self.assertEqual(provider.estimate.call_count, 1)
        self.assertEqual(MealProposal.objects.count(), 1)
