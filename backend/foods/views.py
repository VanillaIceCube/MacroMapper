from collections import defaultdict

from django.utils import timezone
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import FoodComponent, FoodItem
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
            .prefetch_related("current_version__sources")
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        try:
            requested_limit = int(request.query_params.get("limit", 0))
        except (TypeError, ValueError):
            requested_limit = 0
        if requested_limit > 0:
            queryset = queryset[: min(requested_limit, 100)]
        foods = list(queryset)
        component_map = defaultdict(list)
        pending_version_ids = {
            food.current_version_id for food in foods if food.current_version_id
        }
        visited_version_ids = set()
        while pending_version_ids:
            pending_version_ids -= visited_version_ids
            if not pending_version_ids:
                break
            components = list(
                FoodComponent.objects.filter(parent_version_id__in=pending_version_ids)
                .select_related("child_version__food_item")
                .prefetch_related("child_version__sources")
            )
            visited_version_ids.update(pending_version_ids)
            pending_version_ids = set()
            for component in components:
                component_map[component.parent_version_id].append(component)
                if component.child_version_id not in visited_version_ids:
                    pending_version_ids.add(component.child_version_id)
        serializer = self.get_serializer(
            foods,
            many=True,
            context={"request": request, "component_map": component_map},
        )
        return Response(serializer.data)

    def perform_destroy(self, instance):
        instance.archived_at = timezone.now()
        instance.save(update_fields=["archived_at", "updated_at"])
