import asyncio
import base64
import io
import json
import threading
import time
import unittest
import uuid
from datetime import date, timedelta
from unittest.mock import patch

import httpx2
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from mcp.server.auth.provider import AccessToken
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from foods.models import FoodItem
from foods.services import create_food_item, create_food_version
from meals.models import MealEntry
from meals.tests import definition

from . import services
from .auth import (
    INTROSPECTION,
    ISSUER,
    READ,
    RESOURCE,
    WRITE,
    CentralTokenVerifier,
)
from .models import IdentityLink, MealConfirmation


def claims(subject):
    return {
        "active": True,
        "iss": ISSUER,
        "sub": str(subject),
        "aud": RESOURCE,
        "client_id": "macromapper-chatgpt",
        "scope": READ + " " + WRITE,
        "iat": int(time.time()) - 1,
        "exp": int(time.time()) + 899,
    }


def token(subject, **overrides):
    values = dict(
        token="synthetic-access",
        subject=str(subject),
        resource=RESOURCE,
        client_id="macromapper-chatgpt",
        scopes=[READ, WRITE],
        expires_at=int(time.time()) + 600,
        claims={"iss": ISSUER},
    )
    return AccessToken(**(values | overrides))


class Fixtures:
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(
            "mcp-owner", email="owner@example.test"
        )
        self.other = get_user_model().objects.create_user("mcp-other")
        self.link = IdentityLink.objects.create(subject=uuid.uuid4(), user=self.user)
        self.other_link = IdentityLink.objects.create(
            subject=uuid.uuid4(), user=self.other
        )
        self.token = token(self.link.subject)
        self.food = self.make_food(self.user)
        self.foreign = self.make_food(self.other)
        self.payload = {
            "meal_id": None,
            "entry_date": "2026-10-29",
            "name": "Lunch",
            "notes": "",
            "item_inputs": [{"food_item": self.food.pk, "servings": "2", "order": 0}],
        }

    def make_food(self, owner):
        return create_food_item(
            name="Apple",
            scope=FoodItem.Scope.PERSONAL,
            origin_type=FoodItem.OriginType.GENERIC,
            provider_name="",
            owner=owner,
            definition=definition(calories="95", protein="0.5"),
            created_by=owner,
        )


@override_settings(MCP_INTROSPECTION_SECRET="synthetic-introspector")
class IntrospectionTests(Fixtures, TestCase):
    def verify(self, body, *, status=200, headers=None, delay=0):
        real_client = httpx2.AsyncClient
        received = []

        class Body(httpx2.AsyncByteStream):
            async def __aiter__(self):
                if delay:
                    await asyncio.sleep(delay)
                yield body

        def handler(request):
            received.append(request)
            return httpx2.Response(
                status,
                headers=headers or {"Content-Type": "application/json"},
                stream=Body(),
            )

        def client(**kwargs):
            self.assertIs(kwargs["verify"], True)
            self.assertIs(kwargs["trust_env"], False)
            self.assertIs(kwargs["follow_redirects"], False)
            self.assertEqual(kwargs["timeout"], 3)
            return real_client(**kwargs, transport=httpx2.MockTransport(handler))

        with patch("app_mcp.auth.httpx2.AsyncClient", side_effect=client):
            result = async_to_sync(CentralTokenVerifier().verify_token)(
                "synthetic-access"
            )
        self.assertEqual(len(received), 1)
        request = received[0]
        self.assertEqual(str(request.url), INTROSPECTION)
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.content, b"token=synthetic-access")
        self.assertEqual(
            request.headers["authorization"],
            "Basic "
            + base64.b64encode(
                b"macromapper-introspection:synthetic-introspector"
            ).decode(),
        )
        return result

    def test_exact_contract_and_no_cached_positive_or_negative_result(self):
        data = claims(self.link.subject)
        for audience in (RESOURCE, [RESOURCE]):
            with self.subTest(audience=audience):
                result = self.verify(json.dumps(data | {"aud": audience}).encode())
                self.assertEqual(result.subject, str(self.link.subject))
        self.assertIsNone(self.verify(b'{"active":false}'))
        self.assertIsNotNone(self.verify(json.dumps(data).encode()))

    def test_malformed_claims_rejected(self):
        data = claims(self.link.subject)
        for change in (
            {"active": 1},
            {"active": "true"},
            {"active": False},
            {"iss": ISSUER + "/"},
            {"sub": "mcp-owner"},
            {"sub": str(self.link.subject).upper()},
            {"sub": 123},
            {"aud": [RESOURCE, "https://ynab.judeandrewalaba.com/mcp"]},
            {"aud": "https://notoli.judeandrewalaba.com/mcp"},
            {"aud": [RESOURCE, RESOURCE]},
            {"client_id": "ynab-chatgpt"},
            {"client_id": []},
            {"client_id": None},
            {"scope": WRITE},
            {"scope": READ + " ynab:read"},
            {"scope": [READ]},
            {"iat": True},
            {"exp": float(data["exp"])},
            {"iat": int(time.time()) + 60},
            {"exp": int(time.time())},
            {"exp": data["iat"] + 901},
        ):
            with self.subTest(change=change):
                self.assertIsNone(self.verify(json.dumps(data | change).encode()))
        for key in data:
            with self.subTest(missing=key):
                self.assertIsNone(
                    self.verify(
                        json.dumps({k: v for k, v in data.items() if k != key}).encode()
                    )
                )

    def test_bounded_response_deadline_redirect_and_static_failure(self):
        for body in (
            b"x" * 16385,
            b"not json",
            b"[]",
            b'{"active":true,"active":false}',
            b"\xff",
        ):
            self.assertIsNone(self.verify(body))
        self.assertIsNone(self.verify(b"{}", status=302, headers={"Location": ISSUER}))
        self.assertIsNone(self.verify(b"{}", status=503))
        self.assertIsNone(self.verify(b"{}", headers={"Content-Type": "text/html"}))
        self.assertIsNone(
            self.verify(
                b"{}",
                headers={
                    "Content-Type": "application/json",
                    "Content-Encoding": "gzip",
                },
            )
        )
        started = time.monotonic()
        self.assertIsNone(
            self.verify(json.dumps(claims(self.link.subject)).encode(), delay=3.1)
        )
        self.assertLess(time.monotonic() - started, 3.1)

    def test_tls_network_error_and_missing_secret_fail_closed(self):
        with patch(
            "app_mcp.auth.httpx2.AsyncClient",
            side_effect=httpx2.ConnectError("sensitive upstream detail"),
        ):
            self.assertIsNone(
                async_to_sync(CentralTokenVerifier().verify_token)("synthetic-access")
            )
        with (
            override_settings(MCP_INTROSPECTION_SECRET=""),
            patch("app_mcp.auth.httpx2.AsyncClient") as client,
        ):
            self.assertIsNone(
                async_to_sync(CentralTokenVerifier().verify_token)("synthetic-access")
            )
            client.assert_not_called()

    def test_unknown_link_disabled_link_and_disabled_local_account(self):
        self.assertIsNone(self.verify(json.dumps(claims(uuid.uuid4())).encode()))
        self.link.active = False
        self.link.save()
        self.assertIsNone(self.verify(json.dumps(claims(self.link.subject)).encode()))
        self.link.active = True
        self.link.save()
        self.user.is_active = False
        self.user.save()
        self.assertIsNone(self.verify(json.dumps(claims(self.link.subject)).encode()))


class ToolServiceTests(Fixtures, TestCase):
    def preview(self, **changes):
        return services.preview_meal(self.token, self.payload | changes)

    def save(self):
        preview = self.preview()
        return services.confirm_meal(self.token, preview["confirmation_id"], True)[
            "meal"
        ]

    def test_reads_use_existing_visibility_and_owner_boundaries(self):
        shared = create_food_item(
            name="Shared",
            scope="shared",
            origin_type="generic",
            provider_name="",
            owner=None,
            definition=definition() | {"confidence_score": "1"},
            created_by=self.user,
        )
        result = services.search_foods(self.token, "", 20, 0)
        self.assertEqual(
            {food["id"] for food in result["foods"]}, {self.food.pk, shared.pk}
        )
        self.save()
        services.preview_meal(
            token(self.other_link.subject),
            self.payload
            | {
                "item_inputs": [
                    {"food_item": self.foreign.pk, "servings": "1", "order": 0}
                ]
            },
        )
        MealEntry.objects.create(
            owner=self.other, entry_date="2026-10-29", name="Private"
        )
        self.assertEqual(
            len(services.read_diary(self.token, date(2026, 10, 29), 20, 0)["meals"]), 1
        )
        total = services.nutrition_totals(
            self.token, date(2026, 10, 29), date(2026, 10, 29)
        )
        self.assertEqual(total["meal_count"], 1)
        self.assertEqual(
            next(n["amount"] for n in total["nutrients"] if n["key"] == "calories"),
            "190.0000",
        )
        self.assertIsNone(
            next(n["amount"] for n in total["nutrients"] if n["key"] == "sodium")
        )
        with self.assertRaises(ValidationError):
            services.nutrition_totals(self.token, date(2026, 9, 1), date(2026, 10, 29))

    @patch(
        "meals.services.get_estimation_provider",
        side_effect=AssertionError("No AI calls allowed"),
    )
    def test_explicit_preview_exact_confirmation_and_replay(self, provider):
        preview = self.preview()
        self.assertEqual(MealEntry.objects.count(), 0)
        self.assertEqual(preview["selected_foods"][0]["name"], "Apple")
        self.assertEqual(
            preview["selected_foods"][0]["nutrients"]["calories"], "190.00000000"
        )
        for confirmed in (False, 1, "true"):
            with self.assertRaises(ValidationError):
                services.confirm_meal(self.token, preview["confirmation_id"], confirmed)
        saved = services.confirm_meal(self.token, preview["confirmation_id"], True)
        self.assertTrue(saved["saved"])
        self.assertEqual(MealEntry.objects.count(), 1)
        with self.assertRaises(ValidationError):
            services.confirm_meal(self.token, preview["confirmation_id"], True)
        provider.assert_not_called()

    def test_read_only_scope_cannot_prepare_or_confirm(self):
        preview = self.preview()
        read_only = token(self.link.subject, scopes=[READ])
        with self.assertRaises(PermissionDenied):
            services.preview_meal(read_only, self.payload)
        with self.assertRaises(PermissionDenied):
            services.confirm_meal(read_only, preview["confirmation_id"], True)
        self.assertEqual(MealEntry.objects.count(), 0)

    def test_cross_user_cross_client_expired_confirmation_denied(self):
        preview = self.preview()
        for foreign_token in (
            token(self.other_link.subject),
            token(self.link.subject, client_id="macromapper-codex"),
        ):
            with self.assertRaises(ValidationError):
                services.confirm_meal(foreign_token, preview["confirmation_id"], True)
        MealConfirmation.objects.update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        with self.assertRaises(ValidationError):
            services.confirm_meal(self.token, preview["confirmation_id"], True)
        self.assertEqual(MealEntry.objects.count(), 0)

    def test_catalog_update_archive_or_permission_loss_requires_new_preview(self):
        preview = self.preview()
        create_food_version(
            food_item=self.food,
            definition=definition(calories="120"),
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            services.confirm_meal(self.token, preview["confirmation_id"], True)
        preview = self.preview()
        self.food.archived_at = timezone.now()
        self.food.save()
        with self.assertRaises(ValidationError):
            services.confirm_meal(self.token, preview["confirmation_id"], True)
        with self.assertRaises(ValidationError):
            self.preview(
                item_inputs=[
                    {"food_item": self.foreign.pk, "servings": "1", "order": 0}
                ]
            )

    def test_replacement_checks_current_owner_and_stale_meal(self):
        saved = self.save()
        preview = self.preview(meal_id=saved["id"], name="Dinner")
        self.assertEqual(preview["replaces"]["name"], "Lunch")
        meal = MealEntry.objects.get(pk=saved["id"])
        meal.name = "Website edit"
        meal.save()
        with self.assertRaises(ValidationError):
            services.confirm_meal(self.token, preview["confirmation_id"], True)
        preview = self.preview(meal_id=saved["id"], name="Dinner")
        result = services.confirm_meal(self.token, preview["confirmation_id"], True)
        self.assertEqual(result["meal"]["name"], "Dinner")
        meal.owner = self.other
        meal.save()
        with self.assertRaises(ValidationError):
            self.preview(meal_id=saved["id"])

    def test_disable_or_unlink_rechecked_for_every_operation(self):
        preview = self.preview()
        self.user.is_active = False
        self.user.save()
        with self.assertRaises(PermissionDenied):
            services.confirm_meal(self.token, preview["confirmation_id"], True)
        with self.assertRaises(PermissionDenied):
            services.read_diary(self.token, date(2026, 10, 29), 10, 0)
        self.assertEqual(MealEntry.objects.count(), 0)

    def test_preview_limit_and_link_management_refuse_auto_link_or_overwrite(self):
        for _ in range(10):
            self.preview()
        with self.assertRaises(ValidationError):
            self.preview()
        output = io.StringIO()
        with self.assertRaises(CommandError):
            call_command(
                "link_mcp_identity",
                subject=str(self.link.subject),
                user_id=self.other.pk,
                stdout=output,
            )
        call_command(
            "revoke_mcp_identity", subject=str(self.link.subject), stdout=output
        )
        self.link.refresh_from_db()
        self.assertFalse(self.link.active)
        self.assertEqual(MealConfirmation.objects.filter(link=self.link).count(), 0)
        unknown = uuid.uuid4()
        with self.assertRaises(CommandError):
            call_command(
                "link_mcp_identity", subject=str(unknown), user_id=999999, stdout=output
            )
        self.assertFalse(IdentityLink.objects.filter(subject=unknown).exists())

    def test_website_jwt_and_central_token_remain_separate(self):
        self.save()
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION="Bearer "
            + str(RefreshToken.for_user(self.user).access_token)
        )
        self.assertEqual(client.get("/api/meals/").status_code, 200)
        client.credentials(HTTP_AUTHORIZATION="Bearer synthetic-access")
        self.assertEqual(client.get("/api/meals/").status_code, 401)

    def test_snapshot_failure_rolls_back_confirmation_consumption_and_meal(self):
        preview = self.preview()
        with patch(
            "meals.serializers.replace_meal_items",
            side_effect=ValidationError("fixture failure"),
        ):
            with self.assertRaises(ValidationError):
                services.confirm_meal(self.token, preview["confirmation_id"], True)
        self.assertEqual(MealEntry.objects.count(), 0)
        self.assertTrue(
            MealConfirmation.objects.filter(pk=preview["confirmation_id"]).exists()
        )
        self.assertTrue(
            services.confirm_meal(self.token, preview["confirmation_id"], True)["saved"]
        )

    def test_local_link_disable_and_oversized_nutrients_fail_without_mutation(self):
        self.link.active = False
        self.link.save()
        with self.assertRaises(PermissionDenied):
            self.preview()
        self.link.active = True
        self.link.save()
        create_food_version(
            food_item=self.food,
            definition=definition(calories="99999999"),
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            self.preview(
                item_inputs=[{"food_item": self.food.pk, "servings": "999", "order": 0}]
            )
        self.assertEqual(MealEntry.objects.count(), 0)

    @override_settings(MCP_ENABLED=True, DEBUG=False, MCP_INTROSPECTION_SECRET="")
    def test_enabled_production_secret_failure_is_visible(self):
        from .apps import mcp_config_check

        self.assertEqual(
            [issue.id for issue in mcp_config_check(None)], ["app_mcp.E001"]
        )


@unittest.skipUnless(settings.MCP_ENABLED, "Run the enabled file-backed app profile")
class ConcurrentConfirmationTests(Fixtures, TransactionTestCase):
    def setUp(self):
        super().setUp()
        if connection.vendor != "sqlite" or "memory" in str(
            connection.settings_dict["NAME"]
        ):
            self.skipTest("Use app.mcp_test_settings for real SQLite WAL concurrency")
        with connection.cursor() as cursor:
            self.assertEqual(
                cursor.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal"
            )
        first = services.preview_meal(self.token, self.payload)
        self.saved = services.confirm_meal(self.token, first["confirmation_id"], True)[
            "meal"
        ]
        self.preview = services.preview_meal(
            self.token,
            self.payload | {"meal_id": self.saved["id"], "name": "MCP replacement"},
        )

    def race_committed_change(self, writer):
        principal_read = threading.Event()
        writer_committed = threading.Event()
        outcome = []
        original = services.principal

        def pause_after_identity_read(*args, **kwargs):
            result = original(*args, **kwargs)
            principal_read.set()
            if not writer_committed.wait(5):
                raise AssertionError("Concurrent writer did not finish")
            return result

        def confirm():
            close_old_connections()
            try:
                outcome.append(
                    services.confirm_meal(
                        self.token, self.preview["confirmation_id"], True
                    )
                )
            except (DatabaseError, ValidationError) as error:
                outcome.append(error)
            finally:
                close_old_connections()

        with patch.object(services, "principal", side_effect=pause_after_identity_read):
            thread = threading.Thread(target=confirm)
            thread.start()
            try:
                self.assertTrue(principal_read.wait(5))
                # WAL permits this independent connection to commit while the MCP
                # transaction still holds its earlier read snapshot.
                writer()
            finally:
                writer_committed.set()
                thread.join(6)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(outcome), 1)
        self.assertIsInstance(outcome[0], (DatabaseError, ValidationError))
        self.assertTrue(
            MealConfirmation.objects.filter(pk=self.preview["confirmation_id"]).exists()
        )
        self.assertEqual(MealEntry.objects.count(), 1)

    def test_concurrent_website_meal_commit_rejects_confirmation(self):
        def website_write():
            client = APIClient()
            client.force_authenticate(self.user)
            response = client.patch(
                f"/api/meals/{self.saved['id']}/",
                {"name": "Website edit"},
                format="json",
            )
            self.assertEqual(response.status_code, 200, response.data)

        self.race_committed_change(website_write)
        self.assertEqual(
            MealEntry.objects.get(pk=self.saved["id"]).name, "Website edit"
        )
        self.assertEqual(
            MealEntry.objects.get(pk=self.saved["id"]).items.get().calories, 190
        )

    def test_concurrent_catalog_commit_rejects_confirmation(self):
        def catalog_write():
            create_food_version(
                food_item=self.food,
                definition=definition(calories="120"),
                created_by=self.user,
            )

        self.race_committed_change(catalog_write)
        self.food.refresh_from_db()
        self.assertEqual(self.food.current_version.calories, 120)
        meal = MealEntry.objects.get(pk=self.saved["id"])
        self.assertEqual(meal.name, "Lunch")
        self.assertEqual(meal.items.get().calories, 190)


@unittest.skipUnless(settings.MCP_ENABLED, "Run the separate app MCP profile")
@override_settings(ALLOWED_HOSTS=["macromapper.judeandrewalaba.com", "testserver"])
class HTTPTests(Fixtures, TransactionTestCase):
    def test_transport_discovery_schemas_permissions_and_revocation(self):
        from django.core.asgi import get_asgi_application

        from mcp_framework.asgi import create_application

        from .server import create_server

        app = create_application(get_asgi_application(), create_server())
        verification_calls = []
        revoked = False

        async def verify(verifier, bearer):
            verification_calls.append(bearer)
            return self.token if bearer == "synthetic-access" and not revoked else None

        async def exercise():
            nonlocal revoked
            async with app.router.lifespan_context(app):
                async with httpx2.AsyncClient(
                    transport=httpx2.ASGITransport(app=app),
                    base_url=settings.MCP_BASE_URL,
                ) as client:
                    headers = {
                        "Accept": "application/json, text/event-stream",
                        "MCP-Protocol-Version": "2025-11-25",
                    }
                    payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/list",
                        "params": {},
                    }
                    result = await client.post("/mcp", headers=headers, json=payload)
                    self.assertEqual(result.status_code, 401)
                    self.assertIn(
                        "oauth-protected-resource/mcp",
                        result.headers["www-authenticate"],
                    )
                    self.assertEqual(
                        (
                            await client.get(
                                "/.well-known/oauth-protected-resource/mcp"
                            )
                        ).json()["authorization_servers"],
                        [ISSUER],
                    )
                    self.assertEqual(
                        (
                            await client.get("/.well-known/oauth-authorization-server")
                        ).status_code,
                        404,
                    )
                    self.assertEqual(
                        (await client.get("/auth/mcp/authorize/")).status_code, 404
                    )
                    for bearer in ("bad", str(self.jwt)):
                        self.assertEqual(
                            (
                                await client.post(
                                    "/mcp",
                                    headers=headers
                                    | {"Authorization": "Bearer " + bearer},
                                    json=payload,
                                )
                            ).status_code,
                            401,
                        )
                    headers["Authorization"] = "Bearer synthetic-access"
                    result = await client.post("/mcp", headers=headers, json=payload)
                    self.assertEqual(result.status_code, 200, result.text)
                    advertised = {
                        tool["name"]: tool for tool in result.json()["result"]["tools"]
                    }
                    self.assertEqual(
                        set(advertised),
                        {
                            "search_foods",
                            "meal_diary",
                            "nutrition_totals",
                            "preview_meal",
                            "confirm_meal",
                        },
                    )
                    self.assertTrue(
                        advertised["search_foods"]["annotations"]["readOnlyHint"]
                    )
                    self.assertFalse(
                        advertised["confirm_meal"]["annotations"]["readOnlyHint"]
                    )

                    async def call(name, arguments):
                        result = await client.post(
                            "/mcp",
                            headers=headers,
                            json=payload
                            | {
                                "method": "tools/call",
                                "params": {"name": name, "arguments": arguments},
                            },
                        )
                        self.assertEqual(result.status_code, 200, result.text)
                        return result.json()["result"]

                    before = len(verification_calls)
                    data = await call("search_foods", {"query": "Apple"})
                    self.assertEqual(
                        len(verification_calls) - before, 2
                    )  # transport AND operation
                    self.assertEqual(
                        [f["id"] for f in data["structuredContent"]["foods"]],
                        [self.food.pk],
                    )
                    for name, args in (
                        ("search_foods", {"query": "Apple", "limit": 21}),
                        ("search_foods", {"query": "Apple", "limit": True}),
                        (
                            "preview_meal",
                            {
                                "day": "2026-10-29",
                                "name": "Lunch",
                                "items": [{"food_item": self.food.pk, "servings": "0"}],
                            },
                        ),
                        (
                            "confirm_meal",
                            {"confirmation_id": str(uuid.uuid4()), "confirmed": "true"},
                        ),
                    ):
                        self.assertTrue((await call(name, args))["isError"])
                    preview = await call(
                        "preview_meal",
                        {
                            "day": "2026-10-29",
                            "name": "Lunch",
                            "items": [{"food_item": self.food.pk, "servings": "1"}],
                        },
                    )
                    confirmation = preview["structuredContent"]["confirmation_id"]
                    saved = await call(
                        "confirm_meal",
                        {"confirmation_id": confirmation, "confirmed": True},
                    )
                    self.assertTrue(saved["structuredContent"]["saved"])
                    self.assertTrue(
                        (
                            await call(
                                "confirm_meal",
                                {"confirmation_id": confirmation, "confirmed": True},
                            )
                        )["isError"]
                    )
                    revoked = True
                    self.assertEqual(
                        (
                            await client.post("/mcp", headers=headers, json=payload)
                        ).status_code,
                        401,
                    )
                    revoked = False
                    self.assertNotEqual(
                        (
                            await client.post("/mcp/", headers=headers, json=payload)
                        ).status_code,
                        200,
                    )
                    self.assertEqual(
                        (
                            await client.post(
                                "/mcp",
                                headers=headers | {"Origin": "https://evil.example"},
                                json=payload,
                            )
                        ).status_code,
                        403,
                    )

        self.jwt = RefreshToken.for_user(self.user).access_token
        with patch.object(CentralTokenVerifier, "verify_token", verify):
            async_to_sync(exercise)()
