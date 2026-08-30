import { mealEstimateExamples, randomMealEstimateExample } from './mealEstimateExamples';

describe('meal estimate examples', () => {
  test('offers 100 distinct examples across the AI estimate experience', () => {
    expect(mealEstimateExamples).toHaveLength(100);
    expect(new Set(mealEstimateExamples).size).toBe(100);
  });

  test('selects examples across the full collection', () => {
    expect(randomMealEstimateExample(() => 0)).toBe(mealEstimateExamples[0]);
    expect(randomMealEstimateExample(() => 0.999999)).toBe(mealEstimateExamples[99]);
  });
});
