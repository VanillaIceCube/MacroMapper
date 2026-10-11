from django.conf import settings
from django.db.models import F
from django.utils import timezone

from .models import DailyAIUsage
from .provider import EstimationProviderError


def reserve_ai_request():
    limit = settings.OPENAI_MEAL_ESTIMATION_DAILY_REQUEST_LIMIT
    if limit <= 0:
        return
    day = timezone.now().date()
    DailyAIUsage.objects.get_or_create(date=day)
    reserved = DailyAIUsage.objects.filter(date=day, requests__lt=limit).update(
        requests=F("requests") + 1
    )
    if not reserved:
        raise EstimationProviderError("The daily AI request budget is exhausted.")
