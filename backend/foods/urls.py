from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FoodItemViewSet, NutrientDefinitionViewSet

router = DefaultRouter()
router.register(r"foods", FoodItemViewSet, basename="food-item")
router.register(r"nutrients", NutrientDefinitionViewSet, basename="nutrient")

urlpatterns = [
    path("", include(router.urls)),
]
