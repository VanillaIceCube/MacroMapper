from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Error, register


@register()
def mcp_config_check(app_configs, **kwargs):
    if (
        settings.MCP_ENABLED
        and not settings.DEBUG
        and not settings.MCP_INTROSPECTION_SECRET
    ):
        return [
            Error(
                "Enabled production MCP requires its dedicated introspection secret.",
                id="app_mcp.E001",
            )
        ]
    return []


class AppMCPConfig(AppConfig):
    name = "app_mcp"
