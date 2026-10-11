export const NUTRIENT_FIELDS = [
  {
    key: 'calories',
    unit: 'kcal',
    primary: true,
  },
  {
    key: 'protein',
    unit: 'g',
    caloriesPerGram: 4,
    primary: true,
  },
  {
    key: 'carbohydrates',
    unit: 'g',
    caloriesPerGram: 4,
    primary: true,
  },
  {
    key: 'fat',
    unit: 'g',
    caloriesPerGram: 9,
    primary: true,
  },
  {
    key: 'fiber',
    unit: 'g',
  },
  {
    key: 'sugar',
    unit: 'g',
  },
  {
    key: 'sodium',
    unit: 'mg',
  },
  {
    key: 'cholesterol',
    unit: 'mg',
  },
];

export const PRIMARY_NUTRIENT_FIELDS = NUTRIENT_FIELDS.filter((field) => field.primary);

export const MACRO_CALORIE_FIELDS = PRIMARY_NUTRIENT_FIELDS.filter(
  (field) => field.caloriesPerGram,
).map(({ key, caloriesPerGram }) => ({ key, caloriesPerGram }));
