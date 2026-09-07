from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import FoodItem
from .permissions import IsPersonalFoodOwnerOrReadOnly
from .serializers import FoodItemSerializer
from .services import build_component_map


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
        component_map = build_component_map(
            food.current_version_id for food in foods if food.current_version_id
        )
        serializer = self.get_serializer(
            foods,
            many=True,
            context={"request": request, "component_map": component_map},
        )
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        version_ids = (
            [instance.current_version_id] if instance.current_version_id else []
        )
        component_map = build_component_map(version_ids)
        serializer = self.get_serializer(
            instance,
            context={"request": request, "component_map": component_map},
        )
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        instance = serializer.instance
        version_ids = (
            [instance.current_version_id] if instance.current_version_id else []
        )
        component_map = build_component_map(version_ids)
        output_serializer = self.get_serializer(
            instance,
            context={"request": request, "component_map": component_map},
        )
        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(instance, "_prefetched_objects_cache", None):
            instance._prefetched_objects_cache = {}
        version_ids = (
            [instance.current_version_id] if instance.current_version_id else []
        )
        component_map = build_component_map(version_ids)
        output_serializer = self.get_serializer(
            instance,
            context={"request": request, "component_map": component_map},
        )
        return Response(output_serializer.data)

    def perform_destroy(self, instance):
        instance.archived_at = timezone.now()
        instance.save(update_fields=["archived_at", "updated_at"])
