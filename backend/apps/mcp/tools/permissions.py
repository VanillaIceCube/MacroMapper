"""Recheck the actual local OAuth grant and active account on every invocation."""

from django.db.models import F

from apps.mcp.framework.errors import ConnectionPermissionDenied

READ = "macromapper:read"
WRITE = "macromapper:write"
ESTIMATE = "macromapper:estimate"


def principal(raw, *, write=False, paid=False, lock=False):
    # Lazy import keeps the normal MCP-disabled Django profile discoverable.
    from apps.mcp.framework.oauth import resolve_token

    required = [READ] + ([WRITE] if write else []) + ([ESTIMATE] if paid else [])

    def resolve():
        try:
            if not isinstance(raw, str) or not raw or len(raw) > 4096:
                raise ConnectionPermissionDenied("Connect your MacroMapper account.")
            token = resolve_token(raw, READ)
            if not set(required) <= set(token.scope.split()):
                raise ConnectionPermissionDenied(
                    "This connection lacks required permissions.", "insufficient_scope"
                )
            return token
        except ConnectionPermissionDenied as error:
            error.required_scopes = required
            raise

    token = resolve()
    if lock:
        from .models import ActorLock

        actor, _ = ActorLock.objects.get_or_create(owner=token.user)
        ActorLock.objects.filter(pk=actor.pk).update(revision=F("revision"))
        ActorLock.objects.select_for_update().get(pk=actor.pk)
        type(token.user).objects.select_for_update().get(pk=token.user_id)
        type(token).objects.select_for_update().get(pk=token.pk)
        token = resolve()
    return token
