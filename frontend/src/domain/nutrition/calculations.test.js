import {
  itemCalorieContributions,
  itemNutrientTotal,
  mealNutrientTotal,
  macroCalorieSegments,
  mealNutrientValues,
} from './calculations';

const leaf = (key, nutrients, servings = '1') => ({
  key,
  name: key,
  servings,
  nutrients,
  components: [],
});

describe('nutrition calculations', () => {
  test('rolls recursive component nutrients into item and meal totals', () => {
    const composite = {
      key: 'sandwich',
      name: 'Sandwich',
      servings: '2',
      nutrients: {},
      components: [
        leaf('bread', { calories: '100', protein: '4' }, '2'),
        leaf('filling', { calories: '200', protein: '20' }, '0.5'),
      ],
    };

    expect(itemNutrientTotal(composite, 'calories')).toBe(600);
    expect(itemNutrientTotal(composite, 'protein')).toBe(36);
    expect(mealNutrientValues([composite, leaf('fruit', { calories: '50' })])).toEqual({
      calories: 650,
      protein: 36,
      carbohydrates: null,
      fat: null,
    });
  });

  test('converts macro grams into calorie-weighted chart segments', () => {
    const segments = macroCalorieSegments({ protein: 10, carbohydrates: 20, fat: 5 });

    expect(segments.map(({ key, calories }) => ({ key, calories }))).toEqual([
      { key: 'protein', calories: 40 },
      { key: 'carbohydrates', calories: 80 },
      { key: 'fat', calories: 45 },
    ]);
    expect(segments.reduce((total, segment) => total + segment.percentage, 0)).toBeCloseTo(100);
  });

  test('uses a composite food components as calorie contribution rows', () => {
    const composite = {
      key: 'plate',
      name: 'Plate',
      servings: '2',
      nutrients: {},
      components: [
        leaf('protein', { calories: '150', protein: '20' }),
        leaf('side', { calories: '100', carbohydrates: '20' }),
      ],
    };

    expect(itemCalorieContributions([composite])).toEqual([
      expect.objectContaining({ key: 'protein', calories: 300, protein: 40 }),
      expect.objectContaining({ key: 'side', calories: 200, carbohydrates: 40 }),
    ]);
  });

  test('safely handles non-finite, null, or malformed inputs in calculations', () => {
    expect(itemNutrientTotal(null, 'calories')).toBeNull();
    expect(itemNutrientTotal({ nutrients: { calories: 'NaN' } }, 'calories')).toBeNull();
    expect(
      itemNutrientTotal({ nutrients: { calories: '100' }, servings: 'invalid' }, 'calories'),
    ).toBe(0);
    expect(
      mealNutrientTotal(
        [null, { nutrients: { calories: 'Infinity' } }, leaf('apple', { calories: '95' })],
        'calories',
      ),
    ).toBe(95);
  });

  test('handles fallback key/name resolution and filters invalid calorie rows in itemCalorieContributions', () => {
    const items = [
      {
        food_item_id: 42,
        food_name: 'Fallback Item',
        servings: '1',
        nutrients: { calories: '150', protein: '10' },
      },
      { key: 'no-cals', name: 'Water', servings: '1', nutrients: { calories: null } },
      { key: 'invalid-cals', name: 'Broken', servings: '1', nutrients: { calories: 'NaN' } },
      null,
    ];

    expect(itemCalorieContributions(items)).toEqual([
      {
        key: '42',
        name: 'Fallback Item',
        calories: 150,
        protein: 10,
        carbohydrates: null,
        fat: null,
      },
    ]);
    expect(itemCalorieContributions(null)).toEqual([]);
  });
});
