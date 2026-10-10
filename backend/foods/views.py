from django.db.models import (
    Case,
    DateField,
    IntegerField,
    OuterRef,
    Subquery,
    Value,
    When,
)
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from meals.models import MealItem

from .models import FoodItem, FoodItemVersion
from .permissions import IsPersonalFoodOwnerOrReadOnly
from .serializers import FoodItemSerializer
from .services import build_component_map


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
    ordering_fields = [
        "id",
        "name",
        "created_at",
        "updated_at",
        "relevance",
        "has_logged",
        "last_logged_on",
    ]
    ordering = ["name", "id"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = (
            FoodItem.objects.active()
            .visible_to(self.request.user)
            .select_related("owner", "current_version")
            .prefetch_related("current_version__sources")
        )
        latest_log = (
            MealItem.objects.filter(
                meal_entry__owner=self.request.user,
                food_version__food_item_id=OuterRef("pk"),
            )
            .order_by(
                "-meal_entry__entry_date",
                "-meal_entry__created_at",
                "-id",
            )
            .values("meal_entry__entry_date")[:1]
        )
        queryset = queryset.annotate(
            last_logged_on=Subquery(latest_log, output_field=DateField())
        ).annotate(
            has_logged=Case(
                When(last_logged_on__isnull=False, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        search_query = self.request.query_params.get("search", "").strip()
        if search_query:
            queryset = queryset.annotate(
                relevance=Case(
                    When(name__iexact=search_query, then=Value(0)),
                    When(name__istartswith=search_query, then=Value(1)),
                    When(provider_name__iexact=search_query, then=Value(2)),
                    When(name__icontains=search_query, then=Value(3)),
                    When(provider_name__istartswith=search_query, then=Value(4)),
                    default=Value(5),
                    output_field=IntegerField(),
                )
            )
        else:
            queryset = queryset.annotate(
                relevance=Value(0, output_field=IntegerField())
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
        try:
            requested_offset = max(int(request.query_params.get("offset", 0)), 0)
        except (TypeError, ValueError):
            requested_offset = 0
        if requested_limit > 0:
            requested_limit = min(requested_limit, 100)
            queryset = queryset[requested_offset : requested_offset + requested_limit]
        elif requested_offset > 0:
            queryset = queryset[requested_offset:]
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
        instance = serializer.instance
        version_ids = (
            [instance.current_version_id] if instance.current_version_id else []
        )
        component_map = build_component_map(version_ids)
        output_serializer = self.get_serializer(
            instance,
            context={"request": request, "component_map": component_map},
        )
        headers = self.get_success_headers(output_serializer.data)
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
