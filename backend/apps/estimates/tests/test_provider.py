from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import TestCase, override_settings
from pydantic import ValidationError as PydanticValidationError

from ..provider import (
    SYSTEM_PROMPT,
    EstimatedFood,
    EstimatedMeal,
    EstimatedMealFollowUp,
    EstimatedNutrients,
    EstimatedSource,
    FoodSearchIntent,
    GeneratedMealName,
    MealSearchPlan,
    OpenAIMealEstimationProvider,
)


@override_settings(
    OPENAI_API_KEY="test-key",
    OPENAI_MEAL_ESTIMATION_MODEL="gpt-test",
    OPENAI_MEAL_ESTIMATION_TIMEOUT=10,
)
class OpenAIProviderTests(TestCase):
    def test_source_url_schema_is_supported_and_still_validated(self):
        source_url_schema = EstimatedMeal.model_json_schema()["$defs"][
            "EstimatedSource"
        ]["properties"]["url"]

        self.assertEqual(source_url_schema["type"], "string")
        self.assertNotIn("format", source_url_schema)
        servings_schema = EstimatedMeal.model_json_schema()["$defs"]["EstimatedFood"][
            "properties"
        ]["servings"]
        self.assertEqual(servings_schema["type"], "number")
        self.assertNotIn("pattern", servings_schema)
        with self.assertRaises(PydanticValidationError):
            EstimatedSource(
                title="Unsafe source",
                provider="Example",
                url="ftp://example.com/label",
            )

    def test_provider_extracts_catalog_search_intents_without_web_search(self):
        parsed = MealSearchPlan(
            name="KFC & McDonald's Fries",
            items=[
                FoodSearchIntent(
                    raw_text="fries from KFC",
                    search_name="fries",
                    provider_name="KFC",
                    quantity=1,
                    defining_terms=["fries"],
                    aliases=["Crinkle Cut Fries"],
                ),
                FoodSearchIntent(
                    raw_text="fries from McDonald's",
                    search_name="fries",
                    provider_name="McDonald's",
                    quantity=1,
                    defining_terms=["fries"],
                    aliases=["World Famous Fries"],
                ),
            ],
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            id="resp_intents",
            output_parsed=parsed,
        )

        result = OpenAIMealEstimationProvider(client=client).extract_intents(
            "I had fries from KFC and fries from McDonald's"
        )

        request = client.responses.parse.call_args.kwargs
        self.assertNotIn("tools", request)
        self.assertEqual(request["text_format"], MealSearchPlan)
        self.assertFalse(request["store"])
        self.assertEqual(
            [item["provider_name"] for item in result["items"]],
            ["KFC", "McDonald's"],
        )
        self.assertEqual(result["name"], "KFC & McDonald's Fries")
        self.assertEqual(result["provider_response_id"], "resp_intents")

    def test_provider_generates_a_meal_name_without_web_search(self):
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            id="resp_meal_name",
            output_parsed=GeneratedMealName(name="Example Bakery Toast & Apple"),
        )

        result = OpenAIMealEstimationProvider(client=client).generate_name(
            [
                {"name": "Apple", "provider_name": "", "servings": "2.0000"},
                {
                    "name": "Toast",
                    "provider_name": "Example Bakery",
                    "servings": "1.0000",
                },
            ]
        )

        request = client.responses.parse.call_args.kwargs
        self.assertNotIn("tools", request)
        self.assertEqual(request["text_format"], GeneratedMealName)
        self.assertFalse(request["store"])
        self.assertIn('"selected_foods"', request["input"][1]["content"])
        self.assertEqual(result, "Example Bakery Toast & Apple")

    def test_provider_uses_web_search_structured_output_and_retains_metadata(self):
        parsed = EstimatedMeal(
            name="Toast",
            confidence_score=Decimal("0.7"),
            items=[
                EstimatedFood(
                    name="Toast",
                    serving_quantity=40,
                    serving_unit="g",
                    serving_label="40 g slice",
                    serving_weight_grams=40,
                    confidence_score=Decimal("0.7"),
                    nutrients=EstimatedNutrients(calories=Decimal("80")),
                    sources=[
                        EstimatedSource(
                            title="Official label",
                            provider="Example",
                            url="https://example.com/label",
                            is_official=True,
                        )
                    ],
                )
            ],
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            id="resp_123", output_parsed=parsed
        )

        result = OpenAIMealEstimationProvider(client=client).estimate("toast")

        request = client.responses.parse.call_args.kwargs
        self.assertEqual(request["tools"], [{"type": "web_search"}])
        self.assertEqual(request["text_format"], EstimatedMeal)
        self.assertFalse(request["store"])
        self.assertEqual(result["provider_model"], "gpt-test")
        self.assertEqual(result["provider_response_id"], "resp_123")
        self.assertEqual(
            result["items"][0]["sources"][0]["url"], "https://example.com/label"
        )
        self.assertEqual(
            result["items"][0]["portion_options"][0]["unit_label"], "serving"
        )
        self.assertEqual(result["items"][0]["portion_options"][1]["key"], "g")
        self.assertEqual(result["items"][0]["selected_portion_key"], "g")

    def test_provider_returns_a_refreshed_follow_up_meal_name(self):
        parsed = EstimatedMealFollowUp(
            name="Burger & Fries",
            message="Added fries.",
            confidence_score=Decimal("0.9"),
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            id="resp_follow_up_name",
            output_parsed=parsed,
        )

        result = OpenAIMealEstimationProvider(client=client).follow_up(
            original_description="A burger",
            meal_name="Burger",
            items=[],
            follow_up="Add fries",
        )

        request = client.responses.parse.call_args.kwargs
        self.assertEqual(request["text_format"], EstimatedMealFollowUp)
        self.assertEqual(result["name"], "Burger & Fries")
        self.assertEqual(result["message"], "Added fries.")

    def test_provider_normalizes_declared_total_nutrients_to_one_base_serving(self):
        parsed = EstimatedMeal(
            name="McDonald's Hash Browns",
            confidence_score=Decimal("0.93"),
            items=[
                EstimatedFood(
                    name="Hash Browns",
                    provider_name="McDonald's",
                    origin_type="restaurant",
                    servings=Decimal("5.5"),
                    serving_quantity=1,
                    serving_unit="item",
                    serving_label="1 hash brown",
                    serving_weight_grams=53,
                    nutrient_basis="total_consumed",
                    confidence_score=Decimal("0.93"),
                    nutrients=EstimatedNutrients(
                        calories=770,
                        protein=Decimal("5.5"),
                        carbohydrates=99,
                        fat=44,
                        fiber=11,
                        sugar=0,
                        sodium=1705,
                        cholesterol=0,
                    ),
                )
            ],
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            id="resp_hash_browns", output_parsed=parsed
        )

        item = OpenAIMealEstimationProvider(client=client).estimate(
            "5.5 McDonald's hash browns"
        )["items"][0]

        self.assertEqual(item["servings"], 5.5)
        self.assertEqual(Decimal(str(item["nutrients"]["calories"])), Decimal("140"))
        self.assertEqual(
            Decimal(str(item["nutrients"]["carbohydrates"])), Decimal("18")
        )
        self.assertEqual(Decimal(str(item["nutrients"]["fat"])), Decimal("8"))
        self.assertEqual(Decimal(str(item["nutrients"]["sodium"])), Decimal("310"))
        self.assertNotIn("nutrient_basis", item)

    def test_provider_detects_implausible_totals_even_when_basis_is_mislabeled(self):
        parsed = EstimatedMeal(
            name="McDonald's Hash Browns",
            confidence_score=Decimal("0.93"),
            items=[
                EstimatedFood(
                    name="Hash Browns",
                    servings=Decimal("5.5"),
                    serving_quantity=1,
                    serving_unit="item",
                    serving_label="1 hash brown",
                    serving_weight_grams=53,
                    nutrient_basis="per_base_serving",
                    confidence_score=Decimal("0.93"),
                    nutrients=EstimatedNutrients(
                        calories=770,
                        protein=Decimal("5.5"),
                        carbohydrates=99,
                        fat=44,
                        fiber=11,
                        sugar=0,
                        sodium=1705,
                        cholesterol=0,
                    ),
                )
            ],
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            id="resp_mislabeled_hash_browns", output_parsed=parsed
        )

        item = OpenAIMealEstimationProvider(client=client).estimate(
            "5.5 McDonald's hash browns"
        )["items"][0]

        self.assertEqual(Decimal(str(item["nutrients"]["calories"])), Decimal("140"))
        self.assertEqual(
            Decimal(str(item["nutrients"]["carbohydrates"])), Decimal("18")
        )

    def test_provider_keeps_valid_per_serving_nutrients_for_multiple_servings(self):
        parsed = EstimatedMeal(
            name="McDonald's Hash Browns",
            confidence_score=Decimal("0.93"),
            items=[
                EstimatedFood(
                    name="Hash Browns",
                    servings=Decimal("5.5"),
                    serving_quantity=1,
                    serving_unit="item",
                    serving_label="1 hash brown",
                    serving_weight_grams=53,
                    nutrient_basis="per_base_serving",
                    confidence_score=Decimal("0.93"),
                    nutrients=EstimatedNutrients(
                        calories=140,
                        protein=1,
                        carbohydrates=18,
                        fat=8,
                        fiber=2,
                        sugar=0,
                        sodium=310,
                        cholesterol=0,
                    ),
                )
            ],
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            id="resp_per_serving_hash_browns", output_parsed=parsed
        )

        item = OpenAIMealEstimationProvider(client=client).estimate(
            "5.5 McDonald's hash browns"
        )["items"][0]

        self.assertEqual(Decimal(str(item["nutrients"]["calories"])), Decimal("140"))
        self.assertEqual(
            Decimal(str(item["nutrients"]["carbohydrates"])), Decimal("18")
        )

    def test_provider_defaults_beverages_to_natural_containers(self):
        parsed = EstimatedMeal(
            name="Modelo",
            confidence_score=Decimal("0.8"),
            items=[
                EstimatedFood(
                    name="Modelo beer",
                    servings=6,
                    serving_quantity=1,
                    serving_unit="serving",
                    serving_label="1 can",
                    serving_weight_grams=355,
                    serving_volume_ml=Decimal("354.88235475"),
                    confidence_score=Decimal("0.8"),
                    nutrients=EstimatedNutrients(calories=Decimal("144")),
                )
            ],
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            id="resp_modelo", output_parsed=parsed
        )

        result = OpenAIMealEstimationProvider(client=client).estimate(
            "6 cans of Modelo"
        )

        item = result["items"][0]
        options = {option["key"]: option for option in item["portion_options"]}
        self.assertEqual(item["servings"], 6)
        self.assertEqual(item["serving_quantity"], 1)
        self.assertEqual(item["serving_label"], "1 can")
        self.assertEqual(item["selected_portion_key"], "base")
        self.assertEqual(options["fl_oz"]["serving_multiplier"], str(Decimal("1") / 12))

    def test_provider_defaults_nested_components_to_measurement_units(self):
        parsed = EstimatedMeal(
            name="California Burrito",
            confidence_score=Decimal("0.8"),
            items=[
                EstimatedFood(
                    name="California burrito",
                    serving_quantity=1,
                    serving_unit="item",
                    serving_label="1 burrito",
                    serving_weight_grams=600,
                    confidence_score=Decimal("0.8"),
                    nutrients=EstimatedNutrients(calories=Decimal("1200")),
                    components=[
                        EstimatedFood(
                            name="Carne asada",
                            serving_quantity=1,
                            serving_unit="serving",
                            serving_label="1 portion",
                            serving_weight_grams=140,
                            confidence_score=Decimal("0.8"),
                            nutrients=EstimatedNutrients(calories=Decimal("275")),
                        ),
                        EstimatedFood(
                            name="Salsa",
                            serving_quantity=1,
                            serving_unit="serving",
                            serving_label="1 portion",
                            serving_weight_grams=60,
                            serving_volume_ml=60,
                            confidence_score=Decimal("0.8"),
                            nutrients=EstimatedNutrients(calories=Decimal("10")),
                        ),
                    ],
                )
            ],
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            id="resp_burrito", output_parsed=parsed
        )

        result = OpenAIMealEstimationProvider(client=client).estimate(
            "California burrito"
        )

        burrito = result["items"][0]
        self.assertEqual(burrito["selected_portion_key"], "base")
        self.assertEqual(burrito["components"][0]["selected_portion_key"], "g")
        self.assertEqual(burrito["components"][1]["selected_portion_key"], "fl_oz")

    def test_prompt_forbids_medical_advice(self):
        self.assertIn("Do not provide dietary", SYSTEM_PROMPT)
        self.assertIn("medical", SYSTEM_PROMPT)

    def test_prompt_anchors_grams_to_a_concise_stable_serving(self):
        self.assertIn("meal-level name", SYSTEM_PROMPT)
        self.assertIn("stable serving_quantity", SYSTEM_PROMPT)
        self.assertIn('"1 burger"', SYSTEM_PROMPT)
        self.assertIn("serving_weight_grams", SYSTEM_PROMPT)
        self.assertIn('serving_label "1 can"', SYSTEM_PROMPT)
        self.assertIn("serving_volume_ml", SYSTEM_PROMPT)
        self.assertIn("5.5 hash browns", SYSTEM_PROMPT)
        self.assertIn("nutrient_basis", SYSTEM_PROMPT)
        self.assertIn("Never multiply nutrients by servings", SYSTEM_PROMPT)

    def test_prompt_requires_atomic_meal_components(self):
        self.assertIn("atomic ingredient-level components", SYSTEM_PROMPT)
        self.assertIn(
            "Each component must represent exactly one distinct", SYSTEM_PROMPT
        )
        self.assertIn(
            "ingredient or one conventional cohesive prepared food", SYSTEM_PROMPT
        )
        self.assertIn(
            "sour cream, tomato, and salsa as three components", SYSTEM_PROMPT
        )
        self.assertIn("return cabbage, tomato, onion, and", SYSTEM_PROMPT)
        self.assertIn("cilantro as four components", SYSTEM_PROMPT)
        self.assertIn("cohesive sauces", SYSTEM_PROMPT)

    def test_prompt_keeps_shared_food_fields_free_of_personal_context(self):
        self.assertIn("may be published in a shared food catalog", SYSTEM_PROMPT)
        self.assertIn("Never include a person's name", SYSTEM_PROMPT)
        self.assertIn("other personal/request-specific context", SYSTEM_PROMPT)
