from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Error, register
from django.core.exceptions import ImproperlyConfigured


@register()
def mcp_config_check(app_configs, **kwargs):
    errors = []
    if settings.MCP_ENABLED and not settings.DEBUG:
        if not settings.MCP_INTROSPECTION_SECRET:
            errors.append(
                Error(
                    "Enabled production MCP requires its dedicated introspection secret.",
                    id="app_mcp.E001",
                )
            )
        if settings.TRUSTED_PROXY_IPS != ["172.20.0.3"]:
            errors.append(
                Error(
                    "Enabled production MCP requires DJANGO_TRUSTED_PROXY_IPS=172.20.0.3 (the reviewed ingress peer).",
                    id="app_mcp.E002",
                )
            )
    return errors


class AppMCPConfig(AppConfig):
    name = "app_mcp"

    def ready(self):
        errors = mcp_config_check(None)
        if errors:
            raise ImproperlyConfigured(" ".join(error.msg for error in errors))
