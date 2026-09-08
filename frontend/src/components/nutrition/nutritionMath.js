import { MACRO_CALORIE_FIELDS, PRIMARY_NUTRIENT_FIELDS } from './nutritionDefinitions';

export const formatNutritionAmount = (amount) => {
  if (amount === null || amount === undefined || amount === '') return '—';
  const numeric = Number(amount);
  return Number.isFinite(numeric)
    ? numeric.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : '—';
};

export const formatWholeNutritionAmount = (amount) => {
  if (amount === null || amount === undefined || amount === '') return '—';
  const numeric = Number(amount);
  return Number.isFinite(numeric) ? Math.round(numeric).toLocaleString() : '—';
};

export const nutrientArrayToValues = (nutrients = [], divisor = 1) => {
  const safeNutrients = Array.isArray(nutrients) ? nutrients : [];
  const safeDivisor = Number(divisor);
  const validDivisor = Number.isFinite(safeDivisor) && safeDivisor > 0 ? safeDivisor : 1;

  return Object.fromEntries(
    safeNutrients.map((nutrient) => {
      if (!nutrient || typeof nutrient !== 'object') return ['', ''];
      const amount = Number(nutrient.amount);
      return [
        nutrient.key,
        Number.isFinite(amount) ? String(amount / validDivisor) : nutrient.amount,
      ];
    }),
  );
};

export const servingsValue = (item) => {
  if (!item || typeof item !== 'object') return 0;
  const servings = Number(item.servings);
  return Number.isFinite(servings) && servings > 0 ? servings : 0;
};

export function perServingNutrient(item, key) {
  if (!item || typeof item !== 'object') return null;
  const components = Array.isArray(item.components) ? item.components : [];
  if (components.length) {
    const knownValues = components
      .map((component) => ({
        value: perServingNutrient(component, key),
        servings: servingsValue(component),
      }))
      .filter(({ value }) => value != null && Number.isFinite(value));
    if (!knownValues.length) return null;
    return knownValues.reduce((total, entry) => total + entry.value * entry.servings, 0);
  }
  const value = item.nutrients?.[key];
  if (value == null || value === '') return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

export function itemNutrientTotal(item, key) {
  const value = perServingNutrient(item, key);
  return value == null || !Number.isFinite(value) ? null : value * servingsValue(item);
}

export function mealNutrientTotal(items = [], key) {
  const safeItems = Array.isArray(items) ? items : [];
  const knownValues = safeItems
    .map((item) => itemNutrientTotal(item, key))
    .filter((value) => value != null && Number.isFinite(value));
  return knownValues.length ? knownValues.reduce((total, value) => total + value, 0) : null;
}

export const mealNutrientValues = (items = []) =>
  Object.fromEntries(
    PRIMARY_NUTRIENT_FIELDS.map(({ key }) => [key, mealNutrientTotal(items, key)]),
  );

export function macroCalorieSegments(values = {}) {
  if (!values || typeof values !== 'object') return [];
  const segments = MACRO_CALORIE_FIELDS.filter(
    (field) => values[field.key] != null && Number.isFinite(Number(values[field.key])),
  ).map((field) => {
    const grams = Math.max(Number(values[field.key]) || 0, 0);
    return {
      ...field,
      grams,
      calories: grams * field.caloriesPerGram,
    };
  });
  const totalCalories = segments.reduce((total, segment) => total + segment.calories, 0);
  return totalCalories > 0
    ? segments.map((segment) => ({
        ...segment,
        percentage: (segment.calories / totalCalories) * 100,
      }))
    : [];
}

export function macroDonutBackground(segments = []) {
  if (!Array.isArray(segments) || !segments.length) return 'var(--atlas-border)';
  let cursor = 0;
  const stops = segments.map((segment) => {
    const start = cursor;
    cursor += segment.percentage || 0;
    return `${segment.color} ${start}% ${cursor}%`;
  });
  return `conic-gradient(${stops.join(', ')})`;
}

export function summarizeCalorieContributions(
  contributions = [],
  { maxItems = 5, otherKey = 'other-items', otherLabel = (count) => `Other (${count})` } = {},
) {
  const safeContributions = (Array.isArray(contributions) ? contributions : []).filter(
    (item) => item && typeof item === 'object',
  );
  const sorted = [...safeContributions].sort((first, second) => {
    const firstCalories = Number.isFinite(Number(first.calories)) ? Number(first.calories) : 0;
    const secondCalories = Number.isFinite(Number(second.calories)) ? Number(second.calories) : 0;
    if (secondCalories !== firstCalories) {
      return secondCalories - firstCalories;
    }
    const firstName = String(first.name || '');
    const secondName = String(second.name || '');
    return firstName.localeCompare(secondName);
  });

  if (sorted.length <= maxItems) return sorted;
  const visibleCount = maxItems - 1;
  const remaining = sorted.slice(visibleCount);
  return [
    ...sorted.slice(0, visibleCount),
    {
      key: otherKey,
      name: otherLabel(remaining.length),
      isOther: true,
      groupedItems: remaining,
      componentNames: remaining.map((item) => item.name || 'Item'),
      calories: remaining.reduce(
        (total, item) =>
          total + (Number.isFinite(Number(item.calories)) ? Number(item.calories) : 0),
        0,
      ),
      ...Object.fromEntries(
        MACRO_CALORIE_FIELDS.map(({ key }) => [
          key,
          remaining.some((item) => item[key] != null && Number.isFinite(Number(item[key])))
            ? remaining.reduce(
                (total, item) =>
                  total +
                  (item[key] != null && Number.isFinite(Number(item[key])) ? Number(item[key]) : 0),
                0,
              )
            : null,
        ]),
      ),
    },
  ];
}

export function decorateCalorieContributions(contributions = []) {
  const safeContributions = (Array.isArray(contributions) ? contributions : []).filter(
    (item) => item && typeof item === 'object',
  );
  const totalCalories = safeContributions.reduce(
    (total, item) => total + (Number.isFinite(Number(item.calories)) ? Number(item.calories) : 0),
    0,
  );
  const highestCalories = Math.max(
    ...safeContributions.map((item) =>
      Number.isFinite(Number(item.calories)) ? Number(item.calories) : 0,
    ),
    0,
  );

  return safeContributions.map((item) => {
    const itemCalories = Number.isFinite(Number(item.calories)) ? Number(item.calories) : 0;
    return {
      ...item,
      percentage: totalCalories > 0 ? (itemCalories / totalCalories) * 100 : 0,
      relativeBarWidth: highestCalories > 0 ? (itemCalories / highestCalories) * 100 : 0,
      macroSegments: macroCalorieSegments(item),
    };
  });
}

export function itemCalorieContributions(items = []) {
  const safeItems = Array.isArray(items) ? items : [];
  if (!safeItems.length) return [];
  const singleComposite = safeItems.length === 1 && Boolean(safeItems[0]?.components?.length);
  const chartItems = singleComposite ? safeItems[0].components : safeItems;
  const parentServings = singleComposite ? servingsValue(safeItems[0]) : 1;

  return (Array.isArray(chartItems) ? chartItems : []).flatMap((item, index) => {
    if (!item || typeof item !== 'object') return [];
    const calories = itemNutrientTotal(item, 'calories');
    if (calories == null || !Number.isFinite(calories)) return [];
    const itemKey = item.key || item.food_item_id || item.food_version_id || `item-${index}`;
    const itemName = item.name || item.food_name || item.food_item_name || 'Item';

    return [
      {
        key: String(itemKey),
        name: String(itemName),
        calories: calories * parentServings,
        ...Object.fromEntries(
          MACRO_CALORIE_FIELDS.map(({ key }) => {
            const value = itemNutrientTotal(item, key);
            return [key, value == null || !Number.isFinite(value) ? null : value * parentServings];
          }),
        ),
      },
    ];
  });
}
