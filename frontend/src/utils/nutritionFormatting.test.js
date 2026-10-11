import { formatNutritionAmount, formatWholeNutritionAmount } from './nutritionFormatting';

describe('nutrition formatting', () => {
  test('keeps invalid values unavailable and preserves fractional quantity labels', () => {
    expect(formatNutritionAmount(undefined)).toBe('—');
    expect(formatNutritionAmount('invalid')).toBe('—');
    expect(formatWholeNutritionAmount(Infinity)).toBe('—');
    expect(formatNutritionAmount('1.25')).toBe(
      (1.25).toLocaleString(undefined, { maximumFractionDigits: 2 }),
    );
    expect(formatWholeNutritionAmount('1.5')).toBe((2).toLocaleString());
  });
  test('preserves missing whole nutrition amounts as unavailable', () => {
    expect(formatWholeNutritionAmount(null)).toBe('—');
    expect(formatWholeNutritionAmount('')).toBe('—');
  });
});
