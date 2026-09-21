from collections import defaultdict

from django.utils import timezone
from rest_framework import filters, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import FoodComponent, FoodItem, FoodItemVersion
from .permissions import IsPersonalFoodOwnerOrReadOnly
from .serializers import FoodItemSerializer


class FoodItemViewSet(viewsets.ModelViewSet):
    serializer_class = FoodItemSerializer
    permission_classes = [IsAuthenticated, IsPersonalFoodOwnerOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "name",
        "provider_name",
        "current_version__sources__title",
        "current_version__sources__provider",
    ]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name", "id"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = (
            FoodItem.objects.active()
            .visible_to(self.request.user)
            .select_related("owner", "current_version")
            .prefetch_related("current_version__sources")
        )
        scope = self.request.query_params.get("scope", "").strip()
        if scope:
            if scope not in FoodItem.Scope.values:
                raise ValidationError({"scope": "Choose personal or shared."})
            queryset = queryset.filter(scope=scope)

        provider = self.request.query_params.get("provider", "").strip()
        if provider:
            queryset = queryset.filter(provider_name__icontains=provider)

        provenance = self.request.query_params.get("provenance", "").strip()
        if provenance:
            requested = {
                value.strip() for value in provenance.split(",") if value.strip()
            }
            invalid = requested - set(FoodItemVersion.Provenance.values)
            if invalid:
                raise ValidationError({"provenance": "Choose a valid provenance."})
            queryset = queryset.filter(current_version__provenance__in=requested)

        origin_type = self.request.query_params.get("origin_type", "").strip()
        if origin_type:
            if origin_type not in FoodItem.OriginType.values:
                raise ValidationError({"origin_type": "Choose a valid food type."})
            queryset = queryset.filter(origin_type=origin_type)
        return queryset

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
