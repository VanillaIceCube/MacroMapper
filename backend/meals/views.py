from django.db.models import Prefetch
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import MealEntry, MealItem
from .serializers import MealEntrySerializer
from .services import daily_totals


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
                    queryset=MealItem.objects.select_related("food_version"),
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
