"""Test-only canonical OAuth profile; production uses app.settings and central auth."""

from mcp_framework.config import optional_settings

from .settings import *  # noqa: F403

globals().update(optional_settings("MacroMapper", "macromapper", sample=True))
ROOT_URLCONF = "app_mcp.framework_test_urls"
