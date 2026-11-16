"""Natural serving units, measurements and safe portion conversions."""

from decimal import Decimal

from django.test import TestCase

from ..models import (
    FoodItemVersion,
)
from ..nutrients import NUTRIENT_METADATA
from ..portions import portion_options_for_serving
from .helpers import FoodModelFixtures


class FoodServingOptionTests(FoodModelFixtures, TestCase):
    def test_core_nutrient_metadata_has_canonical_units(self):
        expected = {
            "calories": "kcal",
            "protein": "g",
            "carbohydrates": "g",
            "fat": "g",
            "fiber": "g",
            "sugar": "g",
            "sodium": "mg",
            "cholesterol": "mg",
        }

        actual = {key: metadata["unit"] for key, metadata in NUTRIENT_METADATA.items()}

        self.assertEqual(actual, expected)

    def test_portion_options_convert_back_to_one_stable_base_serving(self):
        options = portion_options_for_serving(
            quantity="150",
            unit=FoodItemVersion.ServingUnit.GRAM,
            label="150 g cooked rice",
        )
        by_key = {option["key"]: option for option in options}

        self.assertEqual(by_key["base"]["serving_multiplier"], "1")
        self.assertEqual(by_key["base"]["unit_label"], "serving")
        self.assertEqual(Decimal(by_key["g"]["serving_multiplier"]), Decimal("1") / 150)
        self.assertEqual(
            Decimal(by_key["oz"]["serving_multiplier"]),
            Decimal("28.349523125") / 150,
        )

    def test_countable_serving_weight_adds_grams(self):
        options = portion_options_for_serving(
            quantity="1",
            unit=FoodItemVersion.ServingUnit.ITEM,
            label="1 medium carrot",
            weight_grams="61",
        )
        by_key = {option["key"]: option for option in options}

        self.assertEqual(by_key["base"]["label"], "1 medium carrot")
        self.assertEqual(Decimal(by_key["g"]["serving_multiplier"]), Decimal("1") / 61)
        self.assertEqual(
            Decimal(by_key["oz"]["serving_multiplier"]), Decimal("28.349523125") / 61
        )

    def test_natural_beverage_serving_adds_volume_units(self):
        options = portion_options_for_serving(
            quantity="1",
            unit=FoodItemVersion.ServingUnit.SERVING,
            label="1 can",
            weight_grams="355.2",
            volume_milliliters="355",
        )
        by_key = {option["key"]: option for option in options}

        self.assertEqual(by_key["base"]["label"], "1 can")
        self.assertEqual(by_key["fl_oz"]["label"], "fl oz")
        self.assertEqual(by_key["fl_oz"]["unit_label"], "fl oz")
        self.assertEqual(Decimal(by_key["g"]["serving_multiplier"]), Decimal("1") / 355)
        self.assertEqual(
            Decimal(by_key["ml"]["serving_multiplier"]),
            Decimal("1") / Decimal("354.8823547500"),
        )
        self.assertEqual(
            Decimal(by_key["fl_oz"]["serving_multiplier"]), Decimal("1") / 12
        )

    def test_estimated_liquid_components_use_clean_fluid_ounce_amounts(self):
        expected_amounts = (("330", Decimal("11")), ("143", Decimal("5")))

        for volume_milliliters, expected_fluid_ounces in expected_amounts:
            with self.subTest(volume_milliliters=volume_milliliters):
                options = portion_options_for_serving(
                    quantity="1",
                    unit=FoodItemVersion.ServingUnit.SERVING,
                    label="1 portion",
                    weight_grams=volume_milliliters,
                    volume_milliliters=volume_milliliters,
                )
                by_key = {option["key"]: option for option in options}
                displayed_amount = Decimal("1") / Decimal(
                    by_key["fl_oz"]["serving_multiplier"]
                )

                self.assertEqual(displayed_amount, expected_fluid_ounces)

    def test_tiny_estimated_weights_keep_positive_portion_conversions(self):
        for weight_grams in ("0.001", "0.01", "0.049", "0.05", "0.1"):
            with self.subTest(weight_grams=weight_grams):
                options = portion_options_for_serving(
                    quantity=1, unit="item", weight_grams=weight_grams
                )
                by_key = {option["key"]: option for option in options}

                self.assertEqual(Decimal(by_key["g"]["serving_multiplier"]), 10)
                self.assertEqual(
                    Decimal(by_key["oz"]["serving_multiplier"]),
                    Decimal("28.349523125") / Decimal("0.1"),
                )

    def test_portion_options_handles_zero_or_negative_inputs_without_exception(self):
        cases = [
            {"quantity": 0, "unit": "g"},
            {"quantity": "0.00", "unit": "ml"},
            {"quantity": -5, "unit": "g"},
            {"quantity": 1, "unit": "item", "weight_grams": 0},
            {"quantity": 1, "unit": "item", "weight_grams": "0.01"},
            {"quantity": 1, "unit": "item", "weight_grams": -10},
            {"quantity": 1, "unit": "serving", "volume_milliliters": 0},
            {"quantity": 1, "unit": "serving", "volume_milliliters": -50},
        ]

        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                options = portion_options_for_serving(**kwargs)
                self.assertTrue(isinstance(options, list))
                self.assertGreater(len(options), 0)
                self.assertEqual(options[0]["key"], "base")
