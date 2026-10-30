"""Recheck the actual local OAuth grant and active account on every invocation."""

from django.core.exceptions import PermissionDenied
from django.db.models import F

READ = "macromapper:read"
WRITE = "macromapper:write"
ESTIMATE = "macromapper:estimate"


def principal(raw, *, write=False, paid=False, lock=False):
    # Lazy import keeps the normal MCP-disabled Django profile discoverable.
    from mcp_framework.oauth import resolve_token

    if not isinstance(raw, str) or not raw or len(raw) > 4096:
        raise PermissionDenied("MCP permission denied.")
    token = resolve_token(raw, READ)
    required = {READ} | ({WRITE} if write else set()) | ({ESTIMATE} if paid else set())
    if not required <= set(token.scope.split()):
        raise PermissionDenied("MCP permission denied.")
    if lock:
        from .models import ActorLock

        actor, _ = ActorLock.objects.get_or_create(owner=token.user)
        ActorLock.objects.filter(pk=actor.pk).update(revision=F("revision"))
        ActorLock.objects.select_for_update().get(pk=actor.pk)
        type(token.user).objects.select_for_update().get(pk=token.user_id)
        type(token).objects.select_for_update().get(pk=token.pk)
        token = resolve_token(raw, READ)
        if not required <= set(token.scope.split()):
            raise PermissionDenied("MCP permission denied.")
    return token
