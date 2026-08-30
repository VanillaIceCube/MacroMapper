import { itemNutrientTotal, servingsValue } from './nutrition/nutritionMath';
import { roundedNumberString, selectedPortion } from './mealItemPortions';

export function updateMealItemTree(items, key, update) {
  return items.map((item) =>
    item.key === key
      ? update(item)
      : { ...item, components: updateMealItemTree(item.components || [], key, update) },
  );
}

export function removeMealItemFromTree(items, key) {
  return items
    .filter((item) => item.key !== key)
    .map((item) => ({
      ...item,
      components: removeMealItemFromTree(item.components || [], key),
    }));
}

export function changeMealItemServings(items, key, amount, item) {
  const activePortion = selectedPortion(item);
  const multiplier = Number(activePortion.serving_multiplier);
  const numericAmount = Number(amount);
  const servings =
    amount === '' || !Number.isFinite(numericAmount) || !Number.isFinite(multiplier)
      ? amount
      : roundedNumberString(numericAmount * (multiplier > 0 ? multiplier : 1));
  return updateMealItemTree(items, key, (currentItem) => ({
    ...currentItem,
    servings,
    selected_portion_key: activePortion.key,
  }));
}

export const changeMealItemPortion = (items, key, selectedPortionKey) =>
  updateMealItemTree(items, key, (item) => ({
    ...item,
    selected_portion_key: selectedPortionKey,
  }));

export const changeMealItemNutrient = (items, key, nutrient, totalValue) =>
  updateMealItemTree(items, key, (item) => {
    const numeric = Number(totalValue);
    if (item.components?.length) {
      const currentCalories = itemNutrientTotal(item, 'calories');
      if (
        nutrient !== 'calories' ||
        totalValue === '' ||
        !Number.isFinite(numeric) ||
        numeric < 0 ||
        !currentCalories
      ) {
        return item;
      }
      const scale = numeric / currentCalories;
      return {
        ...item,
        components: item.components.map((component) => ({
          ...component,
          servings:
            scale === 0
              ? component.servings
              : roundedNumberString(servingsValue(component) * scale),
          nutrients:
            scale === 0
              ? Object.fromEntries(
                  Object.entries(component.nutrients || {}).map(([key, value]) => [
                    key,
                    value === null || value === undefined || value === '' ? value : '0',
                  ]),
                )
              : component.nutrients,
        })),
      };
    }
    const servings = servingsValue(item);
    const perServingValue =
      totalValue === '' || !Number.isFinite(numeric) || !servings
        ? totalValue
        : String(numeric / servings);
    return {
      ...item,
      nutrients: { ...item.nutrients, [nutrient]: perServingValue },
    };
  });
