export const NUTRIENT_FIELDS = [
  {
    key: 'calories',
    label: 'Calories',
    unit: 'kcal',
    note: 'Total energy',
    color: 'var(--calorie-color)',
    background: 'var(--atlas-paper)',
    primary: true,
  },
  {
    key: 'protein',
    label: 'Protein',
    unit: 'g',
    note: '4 kcal per gram',
    color: 'var(--protein-color)',
    background: 'var(--atlas-forest-soft)',
    caloriesPerGram: 4,
    primary: true,
  },
  {
    key: 'carbohydrates',
    label: 'Carbs',
    unit: 'g',
    note: '4 kcal per gram',
    color: 'var(--carbohydrate-color)',
    background: 'var(--atlas-mineral-soft)',
    caloriesPerGram: 4,
    primary: true,
  },
  {
    key: 'fat',
    label: 'Fat',
    unit: 'g',
    note: '9 kcal per gram',
    color: 'var(--fat-color)',
    background: 'var(--atlas-persimmon-soft)',
    caloriesPerGram: 9,
    primary: true,
  },
  {
    key: 'fiber',
    label: 'Fiber',
    unit: 'g',
    color: 'var(--fiber-color)',
    background: 'var(--atlas-paper)',
  },
  {
    key: 'sugar',
    label: 'Sugar',
    unit: 'g',
    color: 'var(--sugar-color)',
    background: 'var(--atlas-paper)',
  },
  {
    key: 'sodium',
    label: 'Sodium',
    unit: 'mg',
    color: 'var(--sodium-color)',
    background: 'var(--atlas-paper)',
  },
  {
    key: 'cholesterol',
    label: 'Cholesterol',
    unit: 'mg',
    color: 'var(--cholesterol-color)',
    background: 'var(--atlas-paper)',
  },
];

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
