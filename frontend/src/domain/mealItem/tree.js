import { itemNutrientTotal, servingsValue } from '../nutrition/calculations';
import { roundedNumberString, selectedPortion } from './portions';

const adjusted = (item) => ({
  ...item,
  provenance: 'user_modified_estimate',
  source_kind: 'user_modified_estimate',
  confidence_score: null,
  evidence: { ...item.evidence, status: 'user_modified_estimate', nutrients: {} },
});

export function updateMealItemTree(items, key, update, affectsNutrition = true) {
  return items.map((item) => {
    if (item.key === key) return update(item);
    const components = updateMealItemTree(item.components || [], key, update, affectsNutrition);
    const changed = components.some((child, index) => child !== item.components[index]);
    return changed
      ? affectsNutrition
        ? adjusted({ ...item, components })
        : { ...item, components }
      : item;
  });
}

export function removeMealItemFromTree(items, key) {
  return items
    .filter((item) => item.key !== key)
    .map((item) => {
      const components = removeMealItemFromTree(item.components || [], key);
      const changed =
        components.length !== (item.components || []).length ||
        components.some((child, index) => child !== item.components[index]);
      return changed ? adjusted({ ...item, components }) : item;
    });
}

export function changeMealItemServings(items, key, amount, item) {
  const activePortion = selectedPortion(item);
  const multiplier = Number(activePortion?.serving_multiplier);
  const rawNumeric = Number(amount);
  const numericAmount = Number.isFinite(rawNumeric) && rawNumeric < 0 ? 0 : rawNumeric;
  const clampedAmount = Number.isFinite(rawNumeric) && rawNumeric < 0 ? '0' : amount;

  const servings =
    clampedAmount === '' || !Number.isFinite(numericAmount) || !Number.isFinite(multiplier)
      ? clampedAmount
      : typeof amount === 'string' && (multiplier === 1 || Math.abs(multiplier - 1) < 1e-9)
        ? clampedAmount
        : roundedNumberString(numericAmount * (multiplier > 0 ? multiplier : 1));

  return updateMealItemTree(items, key, (currentItem) => ({
    ...currentItem,
    servings,
    selected_portion_key: activePortion?.key || 'base',
  }));
}

export const changeMealItemPortion = (items, key, selectedPortionKey) =>
  updateMealItemTree(
    items,
    key,
    (item) => ({
      ...item,
      selected_portion_key: selectedPortionKey,
    }),
    false,
  );

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
    const rawNumeric = Number(totalValue);
    const numeric = Number.isFinite(rawNumeric) && rawNumeric < 0 ? 0 : rawNumeric;
    const clampedTotalValue = Number.isFinite(rawNumeric) && rawNumeric < 0 ? '0' : totalValue;

    if (item.components?.length) {
      // Once edited, a composite uses its component totals. An official parent
      // can differ from inferred components, so scale against those components.
      const currentCalories =
        item.components.reduce(
          (total, component) => total + (itemNutrientTotal(component, 'calories') || 0),
          0,
        ) * servingsValue(item);
      if (
        nutrient !== 'calories' ||
        clampedTotalValue === '' ||
        !Number.isFinite(numeric) ||
        numeric < 0 ||
        !currentCalories
      ) {
        return item;
      }
      const scale = numeric / currentCalories;
      return adjusted({
        ...item,
        components: item.components.map((component) => ({
          ...(scale === 0 ? zeroNutrients(component) : component),
          servings:
            scale === 0
              ? component.servings
              : roundedNumberString(servingsValue(component) * scale),
        })),
      });
    }
    const servings = servingsValue(item);
    const perServingValue =
      clampedTotalValue === '' || !Number.isFinite(numeric) || !servings
        ? clampedTotalValue
        : String(numeric / servings);
    return adjusted({
      ...item,
      nutrients: { ...item.nutrients, [nutrient]: perServingValue },
    });
  });
