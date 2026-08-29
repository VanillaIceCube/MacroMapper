import { MACRO_CALORIE_FIELDS, PRIMARY_NUTRIENT_FIELDS } from './nutritionDefinitions';

export const formatNutritionAmount = (amount) => {
  if (amount === null || amount === undefined || amount === '') return '—';
  const numeric = Number(amount);
  return Number.isFinite(numeric)
    ? numeric.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : '—';
};

export const formatWholeNutritionAmount = (amount) => {
  const numeric = Number(amount);
  return Number.isFinite(numeric) ? Math.round(numeric).toLocaleString() : '—';
};

export const nutrientArrayToValues = (nutrients = [], divisor = 1) =>
  Object.fromEntries(
    nutrients.map((nutrient) => {
      const amount = Number(nutrient.amount);
      return [
        nutrient.key,
        Number.isFinite(amount) && divisor > 0 ? String(amount / divisor) : nutrient.amount,
      ];
    }),
  );

export const servingsValue = (item) => {
  const servings = Number(item.servings);
  return Number.isFinite(servings) && servings > 0 ? servings : 0;
};

export function perServingNutrient(item, key) {
  const components = item.components || [];
  if (components.length) {
    const knownValues = components
      .map((component) => ({
        value: perServingNutrient(component, key),
        servings: servingsValue(component),
      }))
      .filter(({ value }) => value != null);
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
  return value == null ? null : value * servingsValue(item);
}

export function mealNutrientTotal(items, key) {
  const knownValues = items
    .map((item) => itemNutrientTotal(item, key))
    .filter((value) => value != null);
  return knownValues.length ? knownValues.reduce((total, value) => total + value, 0) : null;
}

export const mealNutrientValues = (items) =>
  Object.fromEntries(
    PRIMARY_NUTRIENT_FIELDS.map(({ key }) => [key, mealNutrientTotal(items, key)]),
  );

export function macroCalorieSegments(values) {
  const segments = MACRO_CALORIE_FIELDS.filter((field) => values[field.key] != null).map(
    (field) => ({
      ...field,
      grams: Math.max(Number(values[field.key]) || 0, 0),
      calories: Math.max(Number(values[field.key]) || 0, 0) * field.caloriesPerGram,
    }),
  );
  const totalCalories = segments.reduce((total, segment) => total + segment.calories, 0);
  return totalCalories
    ? segments.map((segment) => ({
        ...segment,
        percentage: (segment.calories / totalCalories) * 100,
      }))
    : [];
}

export function macroDonutBackground(segments) {
  if (!segments.length) return 'var(--atlas-border)';
  let cursor = 0;
  const stops = segments.map((segment) => {
    const start = cursor;
    cursor += segment.percentage;
    return `${segment.color} ${start}% ${cursor}%`;
  });
  return `conic-gradient(${stops.join(', ')})`;
}

export function summarizeCalorieContributions(
  contributions,
  { maxItems = 5, otherKey = 'other-items', otherLabel = (count) => `Other (${count})` } = {},
) {
  const sorted = [...contributions].sort((first, second) => second.calories - first.calories);
  if (sorted.length <= maxItems) return sorted;
  const visibleCount = maxItems - 1;
  const remaining = sorted.slice(visibleCount);
  return [
    ...sorted.slice(0, visibleCount),
    {
      key: otherKey,
      name: otherLabel(remaining.length),
      calories: remaining.reduce((total, item) => total + item.calories, 0),
      ...Object.fromEntries(
        MACRO_CALORIE_FIELDS.map(({ key }) => [
          key,
          remaining.some((item) => item[key] != null)
            ? remaining.reduce((total, item) => total + (item[key] || 0), 0)
            : null,
        ]),
      ),
    },
  ];
}

export function decorateCalorieContributions(contributions) {
  const totalCalories = contributions.reduce((total, item) => total + item.calories, 0);
  const highestCalories = Math.max(...contributions.map((item) => item.calories), 0);
  return contributions.map((item) => ({
    ...item,
    percentage: totalCalories ? (item.calories / totalCalories) * 100 : 0,
    relativeBarWidth: highestCalories ? (item.calories / highestCalories) * 100 : 0,
    macroSegments: macroCalorieSegments(item),
  }));
}

export function itemCalorieContributions(items) {
  const singleComposite = items.length === 1 && items[0].components?.length;
  const chartItems = singleComposite ? items[0].components : items;
  const parentServings = singleComposite ? servingsValue(items[0]) : 1;

  return chartItems.flatMap((item) => {
    const calories = itemNutrientTotal(item, 'calories');
    if (calories == null) return [];
    return [
      {
        key: item.key,
        name: item.name,
        calories: calories * parentServings,
        ...Object.fromEntries(
          MACRO_CALORIE_FIELDS.map(({ key }) => {
            const value = itemNutrientTotal(item, key);
            return [key, value == null ? null : value * parentServings];
          }),
        ),
      },
    ];
  });
}
