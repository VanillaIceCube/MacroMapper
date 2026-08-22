from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from meals.serializers import MealEntrySerializer

from .models import MealProposal
from .provider import EstimationProviderError
from .serializers import MealProposalSerializer
from .services import accept_proposal


class MealProposalViewSet(viewsets.ModelViewSet):
    serializer_class = MealProposalSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return MealProposal.objects.filter(owner=self.request.user).select_related(
            "accepted_meal"
        )

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except EstimationProviderError as error:
            return Response(
                {"detail": str(error)},
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
