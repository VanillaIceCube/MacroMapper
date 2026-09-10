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
  let servings;
  if (amount === '' || amount == null) {
    servings = '';
  } else if (!Number.isFinite(numericAmount) || !Number.isFinite(multiplier) || multiplier <= 0) {
    servings = amount;
  } else {
    const validAmount = Math.max(0, numericAmount);
    if (typeof amount === 'string' && (amount.endsWith('.') || amount.endsWith('.0'))) {
      servings = amount;
    } else {
      servings = roundedNumberString(validAmount * (multiplier > 0 ? multiplier : 1));
    }
  }
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

const zeroNutrients = (item) => ({
  ...item,
  nutrients: Object.fromEntries(
    Object.entries(item.nutrients || {}).map(([key, value]) => [
      key,
      value === null || value === undefined || value === '' ? value : '0',
    ]),
  ),
  components: (item.components || []).map(zeroNutrients),
});

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
          ...(scale === 0 ? zeroNutrients(component) : component),
          servings:
            scale === 0
              ? component.servings
              : roundedNumberString(servingsValue(component) * scale),
        })),
      };
    }
    const servings = servingsValue(item);
    const validNumeric = Number.isFinite(numeric) ? Math.max(0, numeric) : numeric;
    const perServingValue =
      totalValue === '' || !Number.isFinite(numeric) || !servings
        ? totalValue !== '' && Number.isFinite(numeric) && numeric < 0
          ? '0'
          : totalValue
        : String(validNumeric / servings);
    return {
      ...item,
      nutrients: { ...item.nutrients, [nutrient]: perServingValue },
    };
  });
