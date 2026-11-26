from rest_framework.routers import DefaultRouter

from .views import MealProposalViewSet

router = DefaultRouter()
router.register(r"meal-proposals", MealProposalViewSet, basename="meal-proposal")

urlpatterns = router.urls
