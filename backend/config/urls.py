from django.contrib import admin
from django.urls import include, path

from apps.mcp.framework.routing import urlpatterns as mcp_urlpatterns

admin.site.site_header = "MacroMapper administration"
admin.site.site_title = "MacroMapper admin"
admin.site.index_title = "Data management"

urlpatterns = mcp_urlpatterns() + [
    path("admin/", admin.site.urls),
    path("api/", include("apps.foods.urls")),
    path("api/", include("apps.estimates.urls")),
    path("api/", include("apps.meals.urls")),
    path("api/", include("apps.notifications.urls")),
    path("auth/", include("apps.authentication.urls")),
]
