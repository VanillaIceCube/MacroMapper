from __future__ import annotations

from decimal import Decimal
from typing import Literal

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, field_validator

from foods.models import FoodItemVersion
from foods.portions import portion_options_for_serving


class EstimationProviderError(Exception):
    """A safe, user-facing failure from the configured estimation provider."""


class EstimatedSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    provider: str = Field(default="", max_length=160)
    url: str = Field(min_length=1, max_length=2048)
    is_official: bool = False

    @field_validator("url")
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        value = value.strip()
        try:
            URLValidator(schemes=["http", "https"])(value)
        except DjangoValidationError as error:
            raise ValueError("Source URLs must use HTTP or HTTPS.") from error
        return value


class EstimatedNutrients(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calories: float | None = Field(default=None, ge=0)
    protein: float | None = Field(default=None, ge=0)
    carbohydrates: float | None = Field(default=None, ge=0)
    fat: float | None = Field(default=None, ge=0)
    fiber: float | None = Field(default=None, ge=0)
    sugar: float | None = Field(default=None, ge=0)
    sodium: float | None = Field(default=None, ge=0)
    cholesterol: float | None = Field(default=None, ge=0)


class EstimatedFood(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    provider_name: str = Field(default="", max_length=160)
    origin_type: Literal["generic", "branded", "restaurant"] = "generic"
    servings: float = Field(default=1, gt=0)
    serving_quantity: float = Field(default=1, gt=0)
    serving_unit: Literal[
        "g",
        "ml",
        "oz",
        "fl_oz",
        "cup",
        "tbsp",
        "tsp",
        "item",
        "serving",
    ] = "serving"
    serving_label: str = Field(default="one serving", max_length=120)
    serving_weight_grams: float = Field(gt=0)
    serving_volume_ml: float | None = Field(default=None, gt=0)
    provenance: Literal["official", "ai_estimate"] = "ai_estimate"
    confidence_score: float = Field(ge=0, le=1)
    nutrients: EstimatedNutrients
    sources: list[EstimatedSource] = Field(default_factory=list)
    components: list["EstimatedFood"] = Field(default_factory=list)


class EstimatedMeal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    confidence_score: float = Field(ge=0, le=1)
    items: list[EstimatedFood] = Field(min_length=1, max_length=20)


EstimatedFood.model_rebuild()


SYSTEM_PROMPT = """You create factual, editable nutrition estimates from meal descriptions.
Return only the requested structured meal data. Set the meal-level name to a concise,
user-facing title that summarizes the foods, such as "Pub Burger, Poutine & Milkshake",
rather than copying the full input description. Search for official brand or restaurant
nutrition pages first. Mark an item official only when its nutrient values are directly
supported by an official published source; otherwise mark it ai_estimate. Preserve source
URLs and identify which sources are official. Break composite restaurant and prepared meals
into atomic ingredient-level components. Each component must represent exactly one distinct
ingredient or one conventional cohesive prepared food. Put each identifiable ingredient
directly under the composite food as its own sibling component; do not combine ingredients
with commas, "and", slashes, or vague group names such as "toppings". For example, return
sour cream, tomato, and salsa as three components, and return cabbage, tomato, onion, and
cilantro as four components. Guacamole, salsa, tortillas, fries, breads, and cohesive sauces
may remain single components unless the user explicitly asks for their recipes. Nutrients
apply to the declared serving and use kcal for calories, grams for
protein/carbohydrates/fat/fiber/sugar, and milligrams for
sodium/cholesterol. Anchor nutrients to exactly one stable serving_quantity, serving_unit,
and serving_label. Choose a concise natural base serving for every item and component.
For countable foods, prefer serving_quantity 1, serving_unit item, and labels such as
"1 burger", "1 medium carrot", or "1 bun". For plated or bowled foods, prefer
serving_quantity 1, serving_unit serving, and labels such as "1 plate" or "1 bowl".
For beverages, always use a natural container as the base serving instead of a volume.
Use serving_quantity 1 and serving_unit serving. Use "1 can" for canned beer or soda,
"1 bottle" for bottled drinks, "1 glass" for an otherwise unspecified drink, and
"1 shake" for a milkshake. Put the number of containers consumed in servings: six
12 fl oz cans of Modelo must be servings 6 with serving_label "1 can", never Quantity
72 with Unit "fl oz". Set serving_volume_ml to the volume of exactly one container so
the application can offer ml, fl oz, and cup conversions. Set serving_volume_ml to null
for non-liquid foods. Prefer standard whole or half-fluid-ounce container sizes instead
of unnecessarily precise liquid volumes.
Use servings to represent how many base servings the user ate. Do not put ingredient lists,
alternate sizes, explanations, parenthetical gram estimates, or the food name in
serving_label. The food name is already displayed as the item title. Always provide
serving_weight_grams as the estimated edible gram weight of exactly one declared base
serving. The application uses it to add a deterministic grams option for every item.
Use null for unavailable nutrients, never zero. Do not provide dietary, medical, clinical,
or treatment advice."""


def _json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


def _serialize_food(food: EstimatedFood, *, key: str, depth: int = 0) -> dict:
    data = food.model_dump(mode="python")
    serving_weight_grams = data.pop("serving_weight_grams")
    serving_volume_ml = data.pop("serving_volume_ml")
    data["portion_options"] = portion_options_for_serving(
        quantity=data["serving_quantity"],
        unit=data["serving_unit"],
        label=data["serving_label"],
        weight_grams=serving_weight_grams,
        volume_milliliters=serving_volume_ml,
    )
    option_keys = {option["key"] for option in data["portion_options"]}
    if depth and "fl_oz" in option_keys:
        data["selected_portion_key"] = "fl_oz"
    elif depth and "g" in option_keys:
        data["selected_portion_key"] = "g"
    else:
        data["selected_portion_key"] = (
            data["serving_unit"] if data["serving_unit"] in option_keys else "base"
        )
    data["key"] = key
    data["food_item_id"] = None
    data["food_version_id"] = None
    data["source_kind"] = (
        "official_verified"
        if food.provenance == FoodItemVersion.Provenance.OFFICIAL
        else "ai_estimate"
    )
    data["components"] = [
        _serialize_food(component, key=f"{key}.{index}", depth=depth + 1)
        for index, component in enumerate(food.components)
    ]
    return _json_value(data)


class OpenAIMealEstimationProvider:
    name = "OpenAI"

    def __init__(self, *, client=None):
        if not settings.OPENAI_API_KEY and client is None:
            raise EstimationProviderError(
                "Meal estimation is not configured. Add an OpenAI API key or use a catalog food."
            )
        self.model = settings.OPENAI_MEAL_ESTIMATION_MODEL
        self.client = client or OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_MEAL_ESTIMATION_TIMEOUT,
        )

    def estimate(self, description: str) -> dict:
        try:
            response = self.client.responses.parse(
                model=self.model,
                tools=[{"type": "web_search"}],
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": description},
                ],
                text_format=EstimatedMeal,
                store=False,
            )
            parsed = response.output_parsed
            if parsed is None:
                raise EstimationProviderError(
                    "The estimation provider did not return a usable meal proposal."
                )
            return {
                "name": parsed.name,
                "confidence_score": parsed.confidence_score,
                "items": [
                    _serialize_food(item, key=f"ai-{index}")
                    for index, item in enumerate(parsed.items)
                ],
                "provider_name": self.name,
                "provider_model": self.model,
                "provider_response_id": response.id,
            }
        except EstimationProviderError:
            raise
        except Exception as error:
            raise EstimationProviderError(
                "The meal estimation service is temporarily unavailable. Try again or log the meal manually."
            ) from error


def get_estimation_provider():
    return OpenAIMealEstimationProvider()
