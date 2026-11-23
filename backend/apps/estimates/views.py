from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.meals.serializers import MealEntrySerializer

from .provider import EstimationProviderError, get_estimation_provider
from .serializers import (
    MapYourMealAdjustmentSerializer,
    MealProposalFollowUpSerializer,
    MealProposalOutcomeSerializer,
    MealProposalSerializer,
)
from .services import (
    accept_reviewed_proposal,
    adjust_meal,
    delete_proposal,
    estimate_proposal,
    follow_up_proposal,
    proposals_for,
    update_proposal,
)

PROVIDER_UNAVAILABLE_DETAIL = (
    "The meal estimation service is temporarily unavailable. "
    "Try again or log the meal manually."
)


class MealProposalViewSet(viewsets.ModelViewSet):
    serializer_class = MealProposalSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return proposals_for(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            proposal = estimate_proposal(request.user, serializer.validated_data)
        except EstimationProviderError:
            return Response(
                {"detail": PROVIDER_UNAVAILABLE_DETAIL},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        response_data = self.get_serializer(proposal).data
        return Response(
            response_data,
            status=status.HTTP_201_CREATED,
            headers=self.get_success_headers(response_data),
        )

    def perform_update(self, serializer):
        serializer.instance = update_proposal(
            self.request.user, serializer.instance, serializer.validated_data
        )

    def perform_destroy(self, instance):
        delete_proposal(self.request.user, instance)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        proposal = self.get_object()
        try:
            meal = accept_reviewed_proposal(request.user, proposal)
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error
        return Response(
            MealEntrySerializer(meal, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="follow-up")
    def follow_up(self, request, pk=None):
        proposal = self.get_object()
        serializer = MealProposalFollowUpSerializer(
            data=request.data,
            context={"request": request, "proposal": proposal},
        )
        serializer.is_valid(raise_exception=True)
        try:
            outcome = follow_up_proposal(
                request.user,
                proposal,
                serializer.validated_data,
                get_provider=get_estimation_provider,
            )
        except EstimationProviderError:
            return Response(
                {"detail": PROVIDER_UNAVAILABLE_DETAIL},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error

        outcome["proposal"].refresh_from_db()
        return Response(
            MealProposalOutcomeSerializer(
                outcome, context=self.get_serializer_context()
            ).data
        )

    @action(detail=False, methods=["post"], url_path="adjustments")
    def create_adjustment(self, request):
        serializer = MapYourMealAdjustmentSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        try:
            with adjust_meal(
                request.user,
                serializer.validated_data,
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
