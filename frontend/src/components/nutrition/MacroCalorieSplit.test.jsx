import { screen, within } from '@testing-library/react';
import { renderWithProviders } from '../../test-helpers/utils';
import MacroCalorieSplit from './MacroCalorieSplit';

describe('MacroCalorieSplit', () => {
  test('renders the dashboard macro split from shared nutrient values', () => {
    renderWithProviders(
      <MacroCalorieSplit
        values={{ calories: 400, protein: 25, carbohydrates: 50, fat: 11.111 }}
        variant="dashboard"
      />,
    );

    const figure = screen.getByRole('figure', { name: 'Macro Balance' });
    expect(within(figure).getByText('400')).toBeInTheDocument();
    expect(
      within(figure).getByRole('img', {
        name: 'Macro Balance: protein 25 percent, carbs 50 percent, fat 25 percent',
      }),
    ).toBeVisible();
  });

  test('renders the diary meal-card macro balance variant', () => {
    renderWithProviders(
      <MacroCalorieSplit
        values={{ calories: 640, protein: 40, carbohydrates: 80, fat: 17.778 }}
        variant="meal-card"
        chartAriaLabel="Dinner Macro Balance"
      />,
    );

    const figure = screen.getByRole('figure', { name: 'Dinner Macro Balance' });
    expect(within(figure).getByText('Macro Balance')).toBeVisible();
    expect(within(figure).getByText('18 g (25%)')).toBeVisible();
    expect(
      within(figure).getByRole('img', {
        name: 'Dinner Macro Balance: protein 25 percent, carbs 50 percent, fat 25 percent',
      }),
    ).toBeVisible();
  });
});
