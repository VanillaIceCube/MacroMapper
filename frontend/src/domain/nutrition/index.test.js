import {
  MACRO_CALORIE_FIELDS,
  NUTRIENT_FIELDS,
  mealNutrientValues,
  nutrientArrayToValues,
} from './index';

test('exposes nutrient units and meal totals through the public nutrition API', () => {
  const savedNutrients = [
    { key: 'calories', amount: '160' },
    { key: 'protein', amount: '8' },
    { key: 'fat', amount: '0' },
  ];
  const servings = 2;
  const nutrients = nutrientArrayToValues(savedNutrients, servings);
  const totals = mealNutrientValues([{ servings, nutrients }]);

  expect(totals).toEqual({ calories: 160, protein: 8, carbohydrates: null, fat: 0 });
  expect(NUTRIENT_FIELDS.find((field) => field.key === 'calories')?.unit).toBe('kcal');
  expect(NUTRIENT_FIELDS.find((field) => field.key === 'sodium')?.unit).toBe('mg');
  expect(MACRO_CALORIE_FIELDS.map(({ key }) => key)).toEqual(['protein', 'carbohydrates', 'fat']);
});
