"""One-use confirmations enforce live authorization, input validation and state."""

from datetime import date, timedelta
from unittest import skipUnless
from unittest.mock import patch

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

from .. import services
from ..auth import READ, WRITE
from ..models import Confirmation
from .helpers import MCPToolFixtures, definition


@skipUnless(settings.MCP_ENABLED, "Run the enabled app-owned OAuth profile")
class MCPConfirmationTests(MCPToolFixtures, TestCase):
    def test_preview_then_single_confirm_update_delete_and_no_ai(self):
        with patch(
            "apps.meals.views.generate_meal_name",
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
