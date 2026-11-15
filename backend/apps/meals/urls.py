from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MealEntryViewSet

router = DefaultRouter()
router.register(r"meals", MealEntryViewSet, basename="meal-entry")

urlpatterns = [path("", include(router.urls))]
