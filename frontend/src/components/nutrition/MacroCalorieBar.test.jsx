import { screen } from '@testing-library/react';
import MacroCalorieBar from './MacroCalorieBar';
import { renderWithProviders } from '../../test-helpers/utils';

describe('MacroCalorieBar', () => {
  test('describes fractional macro energy in its accessible image name', () => {
    renderWithProviders(
      <MacroCalorieBar
        name="Lunch"
        values={{ calories: 33.25, protein: 2.375, carbohydrates: 3.125, fat: 1.25 }}
      />,
    );

    expect(
      screen.getByRole('img', {
        name: 'Lunch macro calorie stack: protein 9.5 kcal, carbs 12.5 kcal, fat 11.25 kcal',
      }),
    ).toBeVisible();
  });

  test('uses rounded energy and spoken units for whole-number charts', () => {
    renderWithProviders(
      <MacroCalorieBar
        name="Lunch"
        values={{ calories: 33.25, protein: 2.375, carbohydrates: 3.125, fat: 1.25 }}
        wholeNumbers
      />,
    );

    expect(
      screen.getByRole('img', {
        name: 'Lunch macro calorie stack: protein 10 kilocalories, carbs 13 kilocalories, fat 11 kilocalories',
      }),
    ).toBeVisible();
  });

  test('retains a known zero while omitting an unavailable macro from the breakdown', () => {
    renderWithProviders(
      <MacroCalorieBar
        name="Fruit"
        values={{ calories: 8, protein: 0, carbohydrates: 2, fat: null }}
      />,
    );

    expect(
      screen.getByRole('img', { name: 'Fruit macro calorie stack: protein 0 kcal, carbs 8 kcal' }),
    ).toBeVisible();
  });

  test('announces unavailable macro data even when total calories are known', () => {
    renderWithProviders(
      <MacroCalorieBar
        name="Unknown recipe"
        values={{ calories: 100, protein: null, carbohydrates: undefined, fat: 'invalid' }}
      />,
    );

    expect(
      screen.getByRole('img', { name: 'Unknown recipe macro calorie stack unavailable' }),
    ).toBeVisible();
  });
});
