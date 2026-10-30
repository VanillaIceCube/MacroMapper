from django.conf import settings
from django.http import JsonResponse
from django.urls import path

from .auth import ISSUER, READ, RESOURCE, WRITE


def resource_metadata(request):
    response = JsonResponse(
        {
            "resource": RESOURCE,
            "authorization_servers": [ISSUER],
            "scopes_supported": [READ, WRITE],
            "bearer_methods_supported": ["header"],
            "resource_name": "MacroMapper",
        }
    )
    response["Cache-Control"] = "no-store"
    return response


def urlpatterns():
    if not settings.MCP_ENABLED:
        return []
    return [
        path(".well-known/oauth-protected-resource", resource_metadata),
        path(".well-known/oauth-protected-resource/mcp", resource_metadata),
    ]
