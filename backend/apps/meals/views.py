from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.estimates.provider import EstimationProviderError, get_estimation_provider
from apps.estimates.serializers import (
    MapYourMealAdjustmentSerializer,
    MapYourMealDraftSerializer,
    MealProposalOutcomeSerializer,
)
from apps.estimates.services import adjust_meal, save_draft

from .serializers import MealEntrySerializer
from .services import daily_totals, delete_meal, meals_for

PROVIDER_UNAVAILABLE_DETAIL = (
    "The meal estimation service is temporarily unavailable. "
    "Try again without losing your meal."
)


class MealEntryViewSet(viewsets.ModelViewSet):
    serializer_class = MealEntrySerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return meals_for(self.request.user, self.request.query_params)

    def perform_create(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        delete_meal(self.request.user, instance)

    @action(detail=False, methods=["get"], url_path="daily")
    def daily(self, request):
        requested_date = request.query_params.get("date")
        parsed_date = parse_date(requested_date or "")
        if parsed_date is None:
            return Response(
                {"date": "Supply a valid date in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        meals = list(self.get_queryset().filter(entry_date=parsed_date))
        return Response(
            {
                "date": parsed_date,
                "meals": self.get_serializer(meals, many=True).data,
                "totals": daily_totals(meals),
            }
        )

    @action(detail=True, methods=["post"], url_path="adjustments")
    def adjustment(self, request, pk=None):
        meal = self.get_object()
        serializer = MapYourMealAdjustmentSerializer(
            data=request.data,
            context={"request": request, "meal": meal},
        )
        serializer.is_valid(raise_exception=True)
        try:
            with adjust_meal(
                request.user,
                serializer.validated_data,
                meal=meal,
                get_provider=get_estimation_provider,
            ) as outcome:
                response_data = MealProposalOutcomeSerializer(
                    outcome, context=self.get_serializer_context()
                ).data
        except EstimationProviderError:
            return Response(
                {"detail": PROVIDER_UNAVAILABLE_DETAIL},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error
        return Response(response_data)

    def _save_draft(self, request, meal=None):
        serializer = MapYourMealDraftSerializer(
            data=request.data, context={"request": request, "meal": meal}
        )
        serializer.is_valid(raise_exception=True)
        try:
            saved_meal = save_draft(request.user, serializer.validated_data, meal)
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error
        return Response(
            MealEntrySerializer(saved_meal, context={"request": request}).data,
            status=status.HTTP_200_OK if meal is not None else status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="drafts")
    def create_draft(self, request):
        return self._save_draft(request)

    @action(detail=True, methods=["put", "patch"], url_path="draft")
    def update_draft(self, request, pk=None):
        return self._save_draft(request, meal=self.get_object())
