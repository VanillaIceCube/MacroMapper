from django.utils import timezone
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import FoodItem
from .permissions import IsPersonalFoodOwnerOrReadOnly
from .serializers import FoodItemSerializer


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
                "current_version__sources",
                "current_version__components__child_version__food_item",
            )
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        try:
            requested_limit = int(request.query_params.get("limit", 0))
        except (TypeError, ValueError):
            requested_limit = 0
        if requested_limit > 0:
            queryset = queryset[: min(requested_limit, 100)]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_destroy(self, instance):
        instance.archived_at = timezone.now()
        instance.save(update_fields=["archived_at", "updated_at"])
