"""Trusted app approvals, live authorization and durable duplicate protection."""

from datetime import date, timedelta
from unittest import skipUnless
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from apps.estimates.models import MealProposal
from apps.foods.services import create_food_version
from apps.meals.models import MealEntry
from apps.notifications.models import Notification

from .. import queries, results, services
from ..models import Confirmation, Execution
from ..permissions import ESTIMATE, READ, WRITE
from .helpers import MCPToolFixtures, definition


@skipUnless(settings.MCP_ENABLED, "Run the enabled app-owned OAuth profile")
class MCPExecutionTests(MCPToolFixtures, TestCase):
    def test_direct_create_replay_update_delete_and_no_ai(self):
        with patch(
            "apps.meals.services.generate_meal_name",
            side_effect=AssertionError("No implicit AI"),
        ):
            request = self.request()
            self.assertFalse(MealEntry.objects.exists())
            meal = MealEntry.objects.get(
                pk=self.execute(request)["result"]["data"]["id"]
            )
        self.assertTrue(self.execute(request)["replayed"])
        self.assertEqual(MealEntry.objects.count(), 1)
        update = self.request("meal.update", meal.pk, {"name": "Updated"})
        self.execute(update)
        meal.refresh_from_db()
        self.assertEqual(meal.name, "Updated")
        delete = self.request("meal.delete", meal.pk, {})
        self.execute(delete)
        self.assertFalse(MealEntry.objects.exists())

    def test_ownership_and_shared_catalog_are_not_staff_bypassable(self):
        foreign = MealEntry.objects.create(
            owner=self.other, entry_date=date.today(), name="Private"
        )
        with self.assertRaises(Http404):
            self.execute(self.request("meal.delete", foreign.pk, {}))
        with self.assertRaises(Http404):
            queries.get_record(self.raw, "meals", foreign.pk)
        self.user.is_staff = True
        self.user.save()
        with self.assertRaises(APIException):
            self.execute(self.request("food.archive", self.food.pk, {}))
        self.assertTrue(MealEntry.objects.filter(pk=foreign.pk).exists())

    def test_cached_success_does_not_overwrite_later_record_or_catalog_changes(self):
        meal = self.make_meal()
        request = self.request("meal.update", meal.pk, {"name": "Requested"})
        completed = self.execute(request)
        MealEntry.objects.filter(pk=meal.pk).update(name="Website changed")
        replay = self.execute(request)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["result"], completed["result"])
        meal.refresh_from_db()
        self.assertEqual(meal.name, "Website changed")
        request = self.request()
        created = self.execute(request)
        create_food_version(
            food_item=self.food, definition=definition("200"), created_by=self.user
        )
        self.assertEqual(self.execute(request)["result"], created["result"])
        self.assertEqual(MealEntry.objects.count(), 2)

    def test_scopes_expiry_revocation_resource_and_unknown_bearers(self):
        from oauth2_provider.models import AccessToken

        self.token.scope = READ
        self.token.save()
        self.assertEqual(
            len(queries.list_records(self.raw, "foods", {}, 10, 0)["data"]), 1
        )
        with self.assertRaises(PermissionDenied):
            self.execute(self.request())
        self.token.scope = " ".join([READ, WRITE])
        self.token.save()
        with self.assertRaises(PermissionDenied):
            self.execute(
                self.request(
                    "proposal.estimate",
                    payload={
                        "description": "An unknown meal",
                        "entry_date": "2026-10-30",
                    },
                )
            )
        self.token.resource = ["https://notoli.judeandrewalaba.com/mcp"]
        self.token.save()
        with self.assertRaises(PermissionDenied):
            queries.list_records(self.raw, "foods", {}, 10, 0)
        self.token.delete()
        for raw in [self.raw, "eyJ.central-issuer-token", "rest-jwt-fixture"]:
            with self.assertRaises(PermissionDenied):
                queries.list_records(raw, "foods", {}, 10, 0)
        self.assertFalse(AccessToken.objects.exists())

    def test_paid_and_nonpaid_tools_cannot_be_mixed_or_reserve_invalid_requests(self):
        nonpaid = self.request()
        paid = self.request(
            "proposal.estimate",
            payload={"description": "Apple", "entry_date": "2026-10-30"},
        )
        for request, wrong_kind in [(paid, False), (nonpaid, True), (paid, 1)]:
            with self.assertRaises(ValidationError):
                self.execute(request | {"authorized_paid": wrong_kind})
            self.assertFalse(
                Execution.objects.filter(pk=request["request_id"]).exists()
            )
        self.token.scope = " ".join([READ, WRITE])
        self.token.save()
        with self.assertRaises(PermissionDenied):
            self.execute(paid)
        self.assertFalse(Execution.objects.filter(pk=paid["request_id"]).exists())
        self.assertTrue(self.execute(nonpaid)["applied"])
        self.assertFalse(MealProposal.objects.exists())

    def test_scopes_independently_gate_delete_and_paid_work_before_reservation(self):
        meal = self.make_meal()
        delete = self.request("meal.delete", meal.pk, {})
        paid = self.request(
            "proposal.estimate",
            payload={"description": "An unknown meal", "entry_date": "2026-10-30"},
        )
        with patch("apps.mcp.tools.operations.invoke_paid") as provider:
            for scopes in ([READ], [READ, ESTIMATE], [WRITE, ESTIMATE]):
                with self.subTest(scopes=scopes):
                    self.token.scope = " ".join(scopes)
                    self.token.save()
                    for request in (delete, paid):
                        with self.assertRaises(PermissionDenied):
                            self.execute(request)
                        self.assertFalse(
                            Execution.objects.filter(pk=request["request_id"]).exists()
                        )
                    self.assertTrue(MealEntry.objects.filter(pk=meal.pk).exists())
            self.token.scope = " ".join([READ, WRITE])
            self.token.save()
            with self.assertRaises(PermissionDenied):
                self.execute(paid)
            self.assertFalse(Execution.objects.filter(pk=paid["request_id"]).exists())
            self.assertTrue(self.execute(delete)["applied"])
            provider.assert_not_called()
        self.assertFalse(MealEntry.objects.filter(pk=meal.pk).exists())

    def test_receipts_bind_owner_client_and_require_current_token_authorization(self):
        from oauth2_provider.models import AccessToken, Application

        request = self.request()
        outcome = self.execute(request)
        other_client = Application.objects.create(
            name="Other",
            client_id="other-client",
            client_type="public",
            authorization_grant_type="authorization-code",
            redirect_uris="https://other.example/callback",
        )
        for user, app in [(self.other, self.application), (self.user, other_client)]:
            token = AccessToken.objects.create(
                user=user,
                application=app,
                token="different-" + str(user.pk) + app.client_id,
                scope=" ".join([READ, WRITE]),
                expires=timezone.now() + timedelta(hours=1),
                resource=[settings.MCP_RESOURCE_URL],
            )
            with self.assertRaises(PermissionDenied):
                self.execute(request, raw=token.token)
        # Refresh/replacement credentials for the same owner/client can recover
        # the receipt without starting another operation.
        replacement = AccessToken.objects.create(
            user=self.user,
            application=self.application,
            token="replacement-token",
            scope=" ".join([READ, WRITE]),
            expires=timezone.now() + timedelta(hours=1),
            resource=[settings.MCP_RESOURCE_URL],
        )
        self.assertEqual(
            self.execute(request, raw=replacement.token)["result"], outcome["result"]
        )
        self.token.expires = timezone.now() - timedelta(seconds=1)
        self.token.save()
        with self.assertRaises(PermissionDenied):
            self.execute(request)
        replacement.delete()
        with self.assertRaises(PermissionDenied):
            self.execute(request, raw="replacement-token")
        self.assertEqual(MealEntry.objects.count(), 1)

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
                self.execute(self.request(payload=payload))
        for limit, offset in [(21, 0), (0, 0), (True, 0), (10, 1001)]:
            with self.assertRaises(ValidationError):
                queries.list_records(self.raw, "foods", {}, limit, offset)
        for coerced in [True, str(self.food.pk)]:
            with self.assertRaises(ValidationError):
                self.execute(
                    self.request(
                        payload=self.meal_payload()
                        | {
                            "item_inputs": [
                                {"food_item": coerced, "servings": "1", "order": 0}
                            ]
                        }
                    )
                )
        with self.assertRaises(ValidationError):
            results.json_value({"items": list(range(101))})
        with self.assertRaises(ValidationError):
            self.execute(self.request(target=True))
        self.assertFalse(MealEntry.objects.exists())

    def test_notifications_all_six_capabilities_and_execution_selection_isolation(self):
        from apps.notifications import services as notifications

        notice = Notification.objects.create(
            recipient=self.user, title="Own", message="Activity"
        )
        foreign = Notification.objects.create(
            recipient=self.other, title="Foreign", message="Private"
        )
        self.assertEqual(
            len(queries.list_records(self.raw, "notifications", {}, 10, 0)["data"]), 1
        )
        self.assertEqual(
            queries.get_record(self.raw, "notifications", notice.pk)["data"]["id"],
            notice.pk,
        )
        with self.assertRaises(Http404):
            queries.get_record(self.raw, "notifications", foreign.pk)
        self.execute(self.request("notification.update", notice.pk, {"is_read": True}))
        notice.refresh_from_db()
        self.assertTrue(notice.is_read)
        self.assertIsNotNone(notice.read_at)
        original_mark = notifications.mark_all_read
        arrived = []

        def arrival(actor, ids):
            arrived.append(
                Notification.objects.create(
                    recipient=self.user, title="New", message="After selection"
                )
            )
            return original_mark(actor, ids)

        with patch.object(notifications, "mark_all_read", side_effect=arrival):
            self.execute(self.request("notification.mark_all_read", payload={}))
        arrived[0].refresh_from_db()
        self.assertFalse(arrived[0].is_read)
        clear = self.request("notification.clear_all", payload={})
        self.execute(clear)
        later = Notification.objects.create(
            recipient=self.user, title="Later", message="Keep"
        )
        self.assertTrue(self.execute(clear)["replayed"])
        self.assertEqual(
            Notification.objects.filter(pk__in=[foreign.pk, later.pk]).count(), 2
        )
        deletion = self.request("notification.delete", later.pk, {})
        self.execute(deletion)
        self.assertTrue(self.execute(deletion)["replayed"])
        self.assertFalse(Notification.objects.filter(pk=later.pk).exists())

    def test_request_uuid_conflicts_and_deleted_target_replays_are_safe(self):
        notice = Notification.objects.create(
            recipient=self.user, title="Bound", message="Old"
        )
        request = self.request("notification.delete", notice.pk, {})
        with self.assertRaisesMessage(ValidationError, "request UUID"):
            self.execute(request | {"request_id": "invalid"})
        self.assertTrue(Notification.objects.filter(pk=notice.pk).exists())
        outcome = self.execute(request)
        self.assertFalse(Notification.objects.filter(pk=notice.pk).exists())
        self.assertEqual(self.execute(request)["result"], outcome["result"])
        with self.assertRaisesMessage(ValidationError, "different arguments"):
            self.execute(request | {"payload": {"unexpected": "changed"}})
        self.assertEqual(Execution.objects.count(), 1)

    def test_bearer_and_session_cannot_approve_even_with_stolen_ticket(self):
        from uuid import uuid4

        from django.test import Client

        request = self.request()
        prepared = self.prepare(request)
        reference = prepared["result"]["data"]["confirmation_id"]
        link = urlsplit(prepared["result"]["data"]["approval_url"])
        self.assertEqual(parse_qs(link.query), {"approval_id": [reference]})
        self.assertNotIn(self.raw, link.geturl())
        client = self.approval_client()
        preview = client.get("/auth/mcp/action-approval/", {"approval_id": reference})
        self.assertEqual(preview.status_code, 200)
        ticket = preview.json()["ticket"]
        self.assertEqual(preview.json()["approval"]["changes"], request["payload"])
        self.assertEqual(
            preview.json()["approval"]["application"]["client_id"],
            self.application.client_id,
        )
        self.assertIn("no-store", preview["Cache-Control"])
        cookie = Client()
        cookie.force_login(self.user)
        for attacker in (
            Client(),
            Client(HTTP_AUTHORIZATION=f"Bearer {self.raw}"),
            cookie,
        ):
            self.assertEqual(
                attacker.get(
                    "/auth/mcp/action-approval/", {"approval_id": reference}
                ).status_code,
                401,
            )
            self.assertEqual(
                attacker.post(
                    "/auth/mcp/action-approval/",
                    {"ticket": ticket, "decision": "allow", "confirmed": True},
                ).status_code,
                401,
            )
        foreign = self.approval_client(self.other)
        self.assertEqual(
            foreign.get(
                "/auth/mcp/action-approval/", {"approval_id": reference}
            ).status_code,
            404,
        )
        self.assertEqual(
            foreign.post(
                "/auth/mcp/action-approval/", {"ticket": ticket, "decision": "allow"}
            ).status_code,
            400,
        )
        waiting = services.confirm_change(self.raw, request["request_id"], reference)
        self.assertEqual(waiting["status"], "prepared")
        self.assertFalse(MealEntry.objects.exists())
        with self.assertRaises(ValidationError):
            services.confirm_change(self.raw, request["request_id"], str(uuid4()))
        self.assertEqual(
            client.post(
                "/auth/mcp/action-approval/", {"ticket": ticket, "decision": "allow"}
            ).status_code,
            200,
        )
        applied = services.confirm_change(self.raw, request["request_id"], reference)
        self.assertTrue(applied["applied"])
        self.assertFalse(Confirmation.objects.filter(pk=reference).exists())
        self.assertTrue(
            services.confirm_change(self.raw, request["request_id"], reference)[
                "replayed"
            ]
        )
        self.assertEqual(MealEntry.objects.count(), 1)

    def test_ticket_tampering_expiry_and_state_change_cannot_approve(self):
        import time
        from unittest.mock import patch

        client = self.approval_client()
        request = self.request()
        reference = self.prepare(request)["result"]["data"]["confirmation_id"]
        preview = client.get(
            "/auth/mcp/action-approval/", {"approval_id": reference}
        ).json()
        for ticket, decision in [
            (preview["ticket"] + "tampered", "allow"),
            (preview["ticket"], "yes"),
        ]:
            self.assertEqual(
                client.post(
                    "/auth/mcp/action-approval/",
                    {"ticket": ticket, "decision": decision},
                ).status_code,
                400,
            )
        with patch("django.core.signing.time.time", return_value=time.time() + 301):
            self.assertEqual(
                client.post(
                    "/auth/mcp/action-approval/",
                    {"ticket": preview["ticket"], "decision": "allow"},
                ).status_code,
                400,
            )
        Confirmation.objects.filter(pk=reference).update(
            payload=self.meal_payload() | {"name": "Changed"}
        )
        self.assertEqual(
            client.post(
                "/auth/mcp/action-approval/",
                {"ticket": preview["ticket"], "decision": "allow"},
            ).status_code,
            409,
        )
        self.assertEqual(
            Execution.objects.get(pk=request["request_id"]).state,
            Execution.State.CANCELLED,
        )
        self.assertFalse(MealEntry.objects.exists())

    def test_live_grant_required_at_app_approval_and_consumption(self):
        from oauth2_provider.models import AccessToken

        client = self.approval_client()
        request = self.request()
        reference = self.prepare(request)["result"]["data"]["confirmation_id"]
        ticket = client.get(
            "/auth/mcp/action-approval/", {"approval_id": reference}
        ).json()["ticket"]
        for updates in (
            {"scope": READ},
            {"resource": ["https://foreign.example/mcp"]},
            {"expires": timezone.now() - timedelta(seconds=1)},
        ):
            old = {key: getattr(self.token, key) for key in updates}
            AccessToken.objects.filter(pk=self.token.pk).update(**updates)
            self.assertEqual(
                client.post(
                    "/auth/mcp/action-approval/",
                    {"ticket": ticket, "decision": "allow"},
                ).status_code,
                403,
            )
            AccessToken.objects.filter(pk=self.token.pk).update(**old)
        self.approve(reference)
        replacement = AccessToken.objects.create(
            user=self.user,
            application=self.application,
            token="same-client-new-token",
            scope=self.token.scope,
            expires=self.token.expires,
            resource=self.token.resource,
        )
        with self.assertRaises(PermissionDenied):
            services.confirm_change(replacement.token, request["request_id"], reference)
        self.token.delete()
        self.assertEqual(
            client.get(
                "/auth/mcp/action-approval/", {"approval_id": reference}
            ).status_code,
            403,
        )
        with self.assertRaises(PermissionDenied):
            services.confirm_change(self.raw, request["request_id"], reference)
        self.assertFalse(MealEntry.objects.exists())

    def test_approved_target_and_catalog_changes_cancel_without_mutation(self):
        meal = self.make_meal()
        request = self.request("meal.delete", meal.pk, {})
        arguments = self.prepare_approved(request)
        MealEntry.objects.filter(pk=meal.pk).update(name="Changed after approval")
        self.assertEqual(
            services.confirm_change(self.raw, *arguments)["status"], "cancelled"
        )
        self.assertTrue(MealEntry.objects.filter(pk=meal.pk).exists())
        request = self.request()
        arguments = self.prepare_approved(request)
        create_food_version(
            food_item=self.food, definition=definition("200"), created_by=self.user
        )
        self.assertEqual(
            services.confirm_change(self.raw, *arguments)["status"], "cancelled"
        )
        self.assertEqual(MealEntry.objects.count(), 1)

    def test_cancel_expiry_and_pending_limit_preserve_terminal_request_ids(self):
        request = self.request()
        reference = self.prepare(request)["result"]["data"]["confirmation_id"]
        self.approve(reference, "cancel")
        self.assertEqual(
            services.confirm_change(self.raw, request["request_id"], reference)[
                "status"
            ],
            "cancelled",
        )
        self.assertEqual(self.prepare(request)["status"], "cancelled")
        expired = self.request()
        reference = self.prepare(expired)["result"]["data"]["confirmation_id"]
        Confirmation.objects.filter(pk=reference).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(
            services.confirm_change(self.raw, expired["request_id"], reference)[
                "status"
            ],
            "expired",
        )
        self.assertFalse(Confirmation.objects.exists())
        for _ in range(10):
            self.prepare(self.request())
        with self.assertRaises(ValidationError):
            self.prepare(self.request())
        self.assertEqual(Confirmation.objects.count(), 10)
        Confirmation.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.prepare(self.request())
        self.assertEqual(Confirmation.objects.count(), 1)
        self.assertEqual(
            Execution.objects.filter(state=Execution.State.EXPIRED).count(), 11
        )
        self.assertFalse(MealEntry.objects.exists())

    def test_paid_preparation_and_unapproved_confirmation_never_call_provider(self):
        request = self.request(
            "proposal.estimate",
            payload={"description": "Unknown meal", "entry_date": "2026-10-30"},
        )
        with patch("apps.mcp.tools.operations.invoke_paid") as provider:
            prepared = self.prepare(request)
            reference = prepared["result"]["data"]["confirmation_id"]
            self.assertFalse(prepared["applied"])
            self.assertEqual(
                services.confirm_change(
                    self.raw, request["request_id"], reference, True
                )["status"],
                "prepared",
            )
            preview = (
                self.approval_client()
                .get("/auth/mcp/action-approval/", {"approval_id": reference})
                .json()["approval"]
            )
            self.assertTrue(preview["paid"])
            self.assertEqual(preview["changes"], request["payload"])
            provider.assert_not_called()
        self.assertFalse(MealProposal.objects.exists())

    def test_complete_approval_preview_does_not_trim_long_data_or_batch_members(self):
        notice = Notification.objects.create(
            recipient=self.user, title="Notice", message="A" * 5000
        )
        reference = self.prepare(self.request("notification.clear_all", payload={}))[
            "result"
        ]["data"]["confirmation_id"]
        preview = (
            self.approval_client()
            .get("/auth/mcp/action-approval/", {"approval_id": reference})
            .json()["approval"]
        )
        self.assertTrue(preview["destructive"])
        selected = preview["current"]["notifications"]
        self.assertEqual([row["id"] for row in selected], [notice.pk])
        self.assertEqual(selected[0]["message"], "A" * 5000)
        self.assertFalse(preview.get("truncated", False))
