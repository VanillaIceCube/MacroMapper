from rest_framework.routers import DefaultRouter

from .views import FoodItemViewSet

router = DefaultRouter()
router.register(r"foods", FoodItemViewSet, basename="food-item")

urlpatterns = router.urls
