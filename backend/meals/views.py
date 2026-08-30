from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from estimates.provider import EstimationProviderError, get_estimation_provider
from estimates.serializers import (
    MapYourMealAdjustmentSerializer,
    MapYourMealDraftSerializer,
    MealProposalSerializer,
)
from estimates.services import apply_proposal_follow_up, save_meal_draft

from .models import MealEntry, MealItem
from .serializers import MealEntrySerializer
from .services import daily_totals, generate_meal_name

PROVIDER_UNAVAILABLE_DETAIL = (
    "The meal estimation service is temporarily unavailable. "
    "Try again without losing your meal."
)


class MealEntryViewSet(viewsets.ModelViewSet):
    serializer_class = MealEntrySerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = (
            MealEntry.objects.filter(owner=self.request.user)
            .prefetch_related(
                Prefetch(
                    "items",
                    queryset=MealItem.objects.select_related(
                        "food_version",
                        "food_version__food_item",
                    ).prefetch_related("food_version__sources"),
                )
            )
            .select_related("owner", "accepted_proposal")
        )
        requested_date = self.request.query_params.get("date")
        if requested_date is not None:
            parsed_date = parse_date(requested_date)
            if parsed_date is None:
                raise ValidationError(
                    {"date": "Supply a valid date in YYYY-MM-DD format."}
                )
            queryset = queryset.filter(entry_date=parsed_date)
        return queryset

    def perform_create(self, serializer):
        if serializer.validated_data.get("name"):
            serializer.save()
            return
        serializer.save(
            name=generate_meal_name(
                owner=self.request.user,
                entry_date=serializer.validated_data["entry_date"],
                item_inputs=serializer.validated_data["items"],
            )
        )

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
        self.get_object()
        serializer = MapYourMealAdjustmentSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        proposal = None
        try:
            proposal = serializer.create_proposal()
            result = get_estimation_provider().follow_up(
                original_description="",
                meal_name=proposal.name,
                items=proposal.items,
                follow_up=serializer.validated_data["adjustment"],
            )
            outcome = apply_proposal_follow_up(
                proposal=proposal,
                owner=request.user,
                follow_up=serializer.validated_data["adjustment"],
                items=proposal.items,
                result=result,
            )
        except EstimationProviderError:
            if proposal is not None:
                proposal.delete()
            return Response(
                {"detail": PROVIDER_UNAVAILABLE_DETAIL},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except DjangoValidationError as error:
            if proposal is not None:
                proposal.delete()
            raise ValidationError(error.messages) from error

        updated_proposal = outcome["proposal"]
        updated_proposal.refresh_from_db()
        proposal_data = MealProposalSerializer(
            updated_proposal,
            context={"request": request},
        ).data
        updated_proposal.delete()
        return Response(
            {
                "applied": outcome["applied"],
                "message": outcome["message"],
                "proposal": proposal_data,
            }
        )

    def _save_draft(self, request, meal=None):
        serializer = MapYourMealDraftSerializer(
            data=request.data,
            context={"request": request, "meal": meal},
        )
        serializer.is_valid(raise_exception=True)
        try:
            saved_meal = save_meal_draft(
                owner=request.user,
                meal=meal,
                **serializer.validated_data,
            )
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
