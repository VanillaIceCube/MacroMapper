import {
  decorateCalorieContributions,
  itemCalorieContributions,
  itemNutrientTotal,
  macroCalorieSegments,
  mealNutrientValues,
  summarizeCalorieContributions,
} from './nutritionMath';

const leaf = (key, nutrients, servings = '1') => ({
  key,
  name: key,
  servings,
  nutrients,
  components: [],
});

describe('nutritionMath', () => {
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

  test('groups overflow contribution rows and decorates them for a shared chart', () => {
    const contributions = [10, 60, 20, 50, 30, 40].map((calories, index) => ({
      key: `item-${index}`,
      name: `Item ${index}`,
      calories,
      protein: calories / 4,
      carbohydrates: null,
      fat: null,
    }));

    const summarized = summarizeCalorieContributions(contributions, {
      otherKey: 'other-foods',
      otherLabel: (count) => `Other foods (${count})`,
    });
    const rows = decorateCalorieContributions(summarized);

    expect(summarized).toHaveLength(5);
    expect(summarized.at(-1)).toMatchObject({
      key: 'other-foods',
      name: 'Other foods (2)',
      calories: 30,
      protein: 7.5,
    });
    expect(rows[0]).toMatchObject({ name: 'Item 1', relativeBarWidth: 100 });
    expect(rows.reduce((total, row) => total + row.percentage, 0)).toBeCloseTo(100);
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
});
