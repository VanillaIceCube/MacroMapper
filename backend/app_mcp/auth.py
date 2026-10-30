"""Fixed central introspection boundary; no token cache or identity auto-linking."""

import asyncio
import json
import time
import uuid

import httpx2
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import DatabaseError
from mcp.server.auth.provider import AccessToken, TokenVerifier

from .models import IdentityLink

ISSUER = "https://auth.judeandrewalaba.com"
RESOURCE = "https://macromapper.judeandrewalaba.com/mcp"
INTROSPECTION = ISSUER + "/o/introspect/"
CLIENTS = {"macromapper-chatgpt", "macromapper-codex"}
READ = "macromapper:read"
WRITE = "macromapper:write"


def validate_claims(data):
    now = time.time()
    if not isinstance(data, dict):
        return False
    scope = data.get("scope")
    issued, expires = data.get("iat"), data.get("exp")
    try:
        subject = data.get("sub")
        if not isinstance(subject, str) or str(uuid.UUID(subject)) != subject:
            return False
    except (ValueError, AttributeError):
        return False
    return (
        data.get("active") is True
        and data.get("iss") == ISSUER
        and (data.get("aud") == RESOURCE or data.get("aud") == [RESOURCE])
        and isinstance(data.get("client_id"), str)
        and data["client_id"] in CLIENTS
        and isinstance(scope, str)
        and READ in scope.split()
        and set(scope.split()) <= {READ, WRITE}
        and type(issued) is int
        and type(expires) is int
        and 0 <= issued <= now < expires <= issued + 900
    )


def linked_user(subject):
    return (
        IdentityLink.objects.select_related("user")
        .filter(issuer=ISSUER, subject=subject, active=True, user__is_active=True)
        .first()
    )


class CentralTokenVerifier(TokenVerifier):
    async def verify_token(self, token):
        secret = settings.MCP_INTROSPECTION_SECRET
        if not secret or not isinstance(token, str) or not 1 <= len(token) <= 8192:
            return None
        try:
            # timeout_at covers connect, headers AND all body chunks (slow trickles too).
            async with asyncio.timeout(3):
                async with httpx2.AsyncClient(
                    verify=True,
                    trust_env=False,
                    follow_redirects=False,
                    timeout=3,
                    auth=httpx2.BasicAuth("macromapper-introspection", secret),
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "identity",
                        "Cache-Control": "no-store",
                    },
                ) as client:
                    async with client.stream(
                        "POST", INTROSPECTION, data={"token": token}
                    ) as response:
                        if (
                            response.status_code != 200
                            or response.headers.get("content-type", "").split(";")[0]
                            != "application/json"
                        ):
                            return None
                        # Reject compression so the wire bound also bounds decoded JSON.
                        if (
                            response.headers.get("content-encoding", "identity")
                            != "identity"
                        ):
                            return None
                        raw = bytearray()
                        async for chunk in response.aiter_raw():
                            if len(raw) + len(chunk) > 16384:
                                return None
                            raw.extend(chunk)
                        data = json.loads(raw, object_pairs_hook=unique_object)
                if not validate_claims(data):
                    return None
                link = await sync_to_async(linked_user, thread_sensitive=True)(
                    data["sub"]
                )
                if link is None:
                    return None
                return AccessToken(
                    token=token,
                    client_id=data["client_id"],
                    scopes=data["scope"].split(),
                    expires_at=data["exp"],
                    subject=data["sub"],
                    resource=RESOURCE,
                    claims={"iss": ISSUER},
                )
        except (
            TimeoutError,
            httpx2.HTTPError,
            ValueError,
            UnicodeError,
            TypeError,
            DatabaseError,
        ):
            return None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON member")
        result[key] = value
    return result
