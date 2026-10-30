"""Isolated canonical provider contract tests; never selected by the app runtime."""

from app.urls import urlpatterns as app_patterns
from mcp_framework.routing import urlpatterns as framework_patterns

urlpatterns = framework_patterns() + app_patterns
