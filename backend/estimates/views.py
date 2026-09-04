from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from meals.serializers import MealEntrySerializer

from .models import MealProposal
from .provider import EstimationProviderError, get_estimation_provider
from .serializers import (
    MapYourMealAdjustmentSerializer,
    MealProposalFollowUpSerializer,
    MealProposalSerializer,
)
from .services import (
    accept_proposal,
    process_map_your_meal_adjustment,
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
        return (
            MealProposal.objects.filter(owner=self.request.user)
            .select_related("accepted_meal")
            .prefetch_related("revisions")
        )

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except EstimationProviderError:
            return Response(
                {"detail": PROVIDER_UNAVAILABLE_DETAIL},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    def perform_destroy(self, instance):
        if instance.status != MealProposal.Status.DRAFT:
            raise ValidationError("Accepted proposals cannot be deleted.")
        instance.delete()

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        proposal = self.get_object()
        try:
            meal = accept_proposal(proposal=proposal)
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
            result = get_estimation_provider().follow_up(
                original_description=proposal.description,
                meal_name=serializer.validated_data["name"],
                items=serializer.validated_data["items"],
                follow_up=serializer.validated_data["follow_up"],
            )
            outcome = serializer.apply(result)
        except EstimationProviderError:
            return Response(
                {"detail": PROVIDER_UNAVAILABLE_DETAIL},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error

        updated_proposal = outcome["proposal"]
        updated_proposal.refresh_from_db()
        return Response(
            {
                "applied": outcome["applied"],
                "message": outcome["message"],
                "proposal": MealProposalSerializer(
                    updated_proposal,
                    context={"request": request},
                ).data,
            }
        )

    @action(detail=False, methods=["post"], url_path="adjustments")
    def create_adjustment(self, request):
        serializer = MapYourMealAdjustmentSerializer(
            data=request.data,
            context={"request": request},
        )
        return process_map_your_meal_adjustment(
            request=request,
            serializer=serializer,
            get_provider=get_estimation_provider,
            cleanup_proposal=False,
        )
