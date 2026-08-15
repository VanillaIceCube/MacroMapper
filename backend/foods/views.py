from django.utils import timezone
from rest_framework import filters, mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import FoodItem, NutrientDefinition
from .permissions import IsPersonalFoodOwnerOrReadOnly
from .serializers import FoodItemSerializer, NutrientDefinitionSerializer


class FoodItemViewSet(viewsets.ModelViewSet):
    serializer_class = FoodItemSerializer
    permission_classes = [IsAuthenticated, IsPersonalFoodOwnerOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "provider_name"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name", "id"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return (
            FoodItem.objects.active()
            .visible_to(self.request.user)
            .select_related("owner", "current_version")
            .prefetch_related(
                "current_version__nutrient_amounts__nutrient",
                "current_version__sources",
                "current_version__components__child_version__food_item",
            )
        )

    def perform_destroy(self, instance):
        instance.archived_at = timezone.now()
        instance.save(update_fields=["archived_at", "updated_at"])


class NutrientDefinitionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = NutrientDefinition.objects.all()
    serializer_class = NutrientDefinitionSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "key"
