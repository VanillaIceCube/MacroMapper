"""Test-only canonical OAuth profile; production uses app.settings and central auth."""

from mcp_framework.config import optional_settings

from .settings import *  # noqa: F403

globals().update(optional_settings("MacroMapper", "macromapper", sample=True))
ROOT_URLCONF = "app_mcp.framework_test_urls"
TRUSTED_PROXY_IPS = [
    "172.20.0.3"
]  # Reviewed peer value; isolated fixtures never connect to the host.
