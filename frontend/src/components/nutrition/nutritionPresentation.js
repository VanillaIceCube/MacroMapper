import { NUTRIENT_FIELDS as nutrientDefinitions } from '../../domain/nutrition/definitions';
import { macroCalorieSegments as calculateMacroCalorieSegments } from '../../domain/nutrition/calculations';

const nutrientPresentation = {
  calories: {
    label: 'Calories',
    note: 'Total energy',
    color: 'var(--calorie-color)',
    background: 'var(--atlas-paper)',
  },
  protein: {
    label: 'Protein',
    note: '4 kcal per gram',
    color: 'var(--protein-color)',
    background: 'var(--atlas-forest-soft)',
  },
  carbohydrates: {
    label: 'Carbs',
    note: '4 kcal per gram',
    color: 'var(--carbohydrate-color)',
    background: 'var(--atlas-mineral-soft)',
  },
  fat: {
    label: 'Fat',
    note: '9 kcal per gram',
    color: 'var(--fat-color)',
    background: 'var(--atlas-persimmon-soft)',
  },
  fiber: {
    label: 'Fiber',
    color: 'var(--fiber-color)',
    background: 'var(--atlas-paper)',
  },
  sugar: {
    label: 'Sugar',
    color: 'var(--sugar-color)',
    background: 'var(--atlas-paper)',
  },
  sodium: {
    label: 'Sodium',
    color: 'var(--sodium-color)',
    background: 'var(--atlas-paper)',
  },
  cholesterol: {
    label: 'Cholesterol',
    color: 'var(--cholesterol-color)',
    background: 'var(--atlas-paper)',
  },
};

export const NUTRIENT_FIELDS = nutrientDefinitions.map((field) => ({
  ...field,
  ...nutrientPresentation[field.key],
}));

export const PRIMARY_NUTRIENT_FIELDS = NUTRIENT_FIELDS.filter((field) => field.primary);

export const MACRO_CALORIE_FIELDS = PRIMARY_NUTRIENT_FIELDS.filter(
  (field) => field.caloriesPerGram,
).map((field) => ({
  key: field.key,
  label: field.key === 'carbohydrates' ? 'carbs' : field.key,
  displayLabel: field.label,
  caloriesPerGram: field.caloriesPerGram,
  color: field.color,
}));

export const macroCalorieSegments = (values) =>
  calculateMacroCalorieSegments(values).map((segment) => ({
    ...MACRO_CALORIE_FIELDS.find((field) => field.key === segment.key),
    ...segment,
  }));

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
