from unittest.mock import MagicMock

from django.test import TestCase, override_settings

from .limits import reserve_ai_request
from .models import DailyAIUsage
from .provider import EstimationProviderError, OpenAIMealEstimationProvider


class AIRequestBudgetTests(TestCase):
    @override_settings(OPENAI_MEAL_ESTIMATION_DAILY_REQUEST_LIMIT=2)
    def test_persisted_budget_survives_new_provider_instances(self):
        reserve_ai_request()
        reserve_ai_request()
        client = MagicMock()
        provider = OpenAIMealEstimationProvider(client=client)
        with self.assertRaises(EstimationProviderError):
            provider.estimate("toast")
        client.responses.parse.assert_not_called()
        self.assertEqual(DailyAIUsage.objects.get().requests, 2)

    @override_settings(OPENAI_MEAL_ESTIMATION_DAILY_REQUEST_LIMIT=2)
    def test_failed_attempt_consumes_budget_and_bounds_output(self):
        client = MagicMock()
        client.responses.parse.side_effect = RuntimeError("private provider error")
        with self.assertRaises(EstimationProviderError):
            OpenAIMealEstimationProvider(client=client).estimate("toast")
        self.assertEqual(DailyAIUsage.objects.get().requests, 1)
        kwargs = client.responses.parse.call_args.kwargs
        self.assertEqual(kwargs["max_output_tokens"], 8192)
        self.assertEqual(kwargs["max_tool_calls"], 2)
