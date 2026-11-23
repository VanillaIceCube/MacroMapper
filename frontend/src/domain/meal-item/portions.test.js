import {
  displayedPortionOptions,
  nativeMeasurementPortion,
  portionOptionLabel,
  portionOptions,
  roundedNumberString,
  selectedPortion,
  servingAmountValue,
} from './portions';

const measuredItem = {
  servings: '2.5',
  serving_unit: 'g',
  selected_portion_key: 'base',
  portion_options: [
    { key: 'base', label: 'one serving', serving_multiplier: '1' },
    { key: 'g', label: 'Grams', serving_multiplier: '0.01' },
  ],
};

describe('meal item portions', () => {
  test('supplies safe fallbacks for absent portion data', () => {
    expect(portionOptions(null)).toEqual([
      { key: 'base', label: '— serving', unit_label: 'serving', serving_multiplier: '1' },
    ]);
    expect(selectedPortion(undefined).key).toBe('base');
    expect(nativeMeasurementPortion(null)).toBeNull();
    expect(portionOptionLabel(null)).toBe('serving');
    expect(roundedNumberString(NaN)).toBe('0');
    expect(roundedNumberString(Infinity)).toBe('0');
  });

  test('uses native measurement portions and keeps their conversions', () => {
    expect(selectedPortion(measuredItem)).toEqual(measuredItem.portion_options[1]);
    expect(displayedPortionOptions(measuredItem)).toEqual([measuredItem.portion_options[1]]);
    expect(portionOptionLabel(measuredItem.portion_options[1])).toBe('g');
    expect(servingAmountValue(measuredItem)).toBe('250');
  });

  test.each(['', '1.', '2.50', 'invalid'])('preserves in-progress quantity %j', (servings) => {
    expect(servingAmountValue({ servings })).toBe(servings);
  });

  test('preserves absent quantities and handles invalid multipliers', () => {
    expect(servingAmountValue(null)).toBe('');
    expect(servingAmountValue({ servings: null })).toBe('');
    expect(servingAmountValue({ servings: undefined })).toBe('');
    for (const serving_multiplier of ['0', '-1', 'invalid']) {
      expect(
        servingAmountValue({
          servings: '2.50',
          portion_options: [{ key: 'base', serving_multiplier }],
        }),
      ).toBe('2.50');
    }
  });
});
