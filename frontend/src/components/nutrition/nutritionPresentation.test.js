import {
  decorateCalorieContributions,
  macroCalorieSegments,
  macroDonutBackground,
  NUTRIENT_FIELDS,
} from './nutritionPresentation';
import { summarizeCalorieContributions } from '../../domain/nutrition/calculations';

describe('nutrition presentation', () => {
  test('retains nutrient labels and semantic colors on calculated macro segments', () => {
    expect(NUTRIENT_FIELDS.find(({ key }) => key === 'carbohydrates')).toMatchObject({
      label: 'Carbs',
      unit: 'g',
      note: '4 kcal per gram',
      color: 'var(--carbohydrate-color)',
      background: 'var(--atlas-mineral-soft)',
      caloriesPerGram: 4,
    });
    const segments = macroCalorieSegments({ protein: 10, carbohydrates: 20, fat: 5 });
    expect(segments[1]).toMatchObject({
      key: 'carbohydrates',
      label: 'carbs',
      displayLabel: 'Carbs',
      color: 'var(--carbohydrate-color)',
      grams: 20,
      calories: 80,
    });
    expect(macroDonutBackground(segments)).toContain('var(--carbohydrate-color)');
    expect(macroDonutBackground([])).toBe('var(--atlas-border)');
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

  test('safely summarizes and decorates contributions with non-finite or missing calories', () => {
    const contributions = [
      { name: 'Item B', calories: '100' },
      { name: 'Item A', calories: '100' },
      { name: 'Broken', calories: 'NaN' },
      { name: 'Zero', calories: 0 },
      null,
    ];

    const summarized = summarizeCalorieContributions(contributions, { maxItems: 10 });
    expect(summarized).toHaveLength(4);
    expect(summarized[0].name).toBe('Item A');
    expect(summarized[1].name).toBe('Item B');

    const decorated = decorateCalorieContributions(summarized);
    expect(decorated[0].percentage).toBe(50);
    expect(decorated[0].relativeBarWidth).toBe(100);

    const emptyDecorated = decorateCalorieContributions([null, { calories: 0 }]);
    expect(emptyDecorated[0]).toMatchObject({ percentage: 0, relativeBarWidth: 0 });
  });
});
