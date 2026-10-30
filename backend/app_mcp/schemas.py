"""Explicit public output schemas, containing no OAuth identities or credentials."""

from pydantic import BaseModel


class FoodSummary(BaseModel):
    id: int
    name: str
    provider: str
    scope: str
    version_id: int
    serving_quantity: str
    serving_unit: str
    serving_label: str
    provenance: str


class FoodResults(BaseModel):
    foods: list[FoodSummary]
    has_more: bool
    next_offset: int | None


class MealItemSummary(BaseModel):
    food_item_id: int
    food_version_id: int
    name: str
    servings: str
    nutrients: dict[str, str | None]


class MealSummary(BaseModel):
    id: int
    date: str
    name: str
    notes: str
    notes_truncated: bool
    updated_at: str
    items: list[MealItemSummary]
    items_truncated: bool


class DiaryResults(BaseModel):
    meals: list[MealSummary]
    has_more: bool
    next_offset: int | None


class NutrientTotal(BaseModel):
    key: str
    name: str
    unit: str
    amount: str | None


class TotalsResults(BaseModel):
    start: str
    end: str
    meal_count: int
    nutrients: list[NutrientTotal]
    note: str


class SelectedFood(BaseModel):
    food_id: int
    version_id: int
    name: str
    provider: str
    servings: str
    serving_quantity: str
    serving_unit: str
    serving_label: str
    nutrients: dict[str, str | None]


class PreparedItem(BaseModel):
    food_item: int
    servings: str
    order: int


class PreparedMeal(BaseModel):
    meal_id: int | None
    entry_date: str
    name: str
    notes: str
    item_inputs: list[PreparedItem]


class PreviewResults(BaseModel):
    confirmation_id: str
    expires_at: str
    action: str
    meal: PreparedMeal
    selected_foods: list[SelectedFood]
    replaces: MealSummary | None
    instruction: str


class ConfirmationResults(BaseModel):
    saved: bool
    meal: MealSummary
