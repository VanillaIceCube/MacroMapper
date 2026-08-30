import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../test-support/utils';
import CalorieContributionChart from './CalorieContributionChart';
import MacroCalorieSplit from './MacroCalorieSplit';
import MealNutritionSummary from './MealNutritionSummary';

describe('shared nutrition charts', () => {
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

  test('renders, summarizes, and explains a reusable calories-by-x chart on hover', async () => {
    const user = userEvent.setup();
    const contributions = [600, 500, 400, 300, 200, 100].map((calories, index) => ({
      key: `meal-${index}`,
      name: `Meal ${index}`,
      calories,
      protein: calories / 4,
      carbohydrates: null,
      fat: null,
    }));
    renderWithProviders(
      <CalorieContributionChart
        contributions={contributions}
        title="Calories by meal"
        chartAriaLabel="Meal calorie chart"
        emptyText="No meals."
        variant="dashboard"
        otherKey="other-meals"
        otherLabel={(count) => `Other meals (${count})`}
      />,
    );

    const figure = screen.getByRole('figure', { name: 'Calories by meal' });
    expect(within(figure).getByText('Other meals (2)')).toBeInTheDocument();
    expect(within(figure).getAllByLabelText(/\(\d+ percent\)$/)).toHaveLength(5);
    expect(
      within(figure).getByRole('img', {
        name: 'Meal 0 macro calorie stack: protein 600 kilocalories',
      }),
    ).toBeVisible();
    await user.hover(
      within(figure).getByLabelText('Other meals (2) 300 kilocalories (14 percent)'),
    );
    expect(await screen.findByText('Components: Meal 4, Meal 5 · 300 kcal (14%)')).toBeVisible();
  });

  test('combines shared cards and charts in a collapsible meal summary', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <MealNutritionSummary
        items={[
          {
            key: 'apple',
            name: 'Apple',
            servings: '1',
            nutrients: { calories: '95', protein: '0.5', carbohydrates: '25', fat: '0.3' },
            components: [],
          },
        ]}
      />,
    );

    const summary = screen.getByRole('region', { name: 'Meal macro breakdown' });
    expect(within(summary).getByLabelText('Full meal nutrition values')).toBeVisible();
    expect(within(summary).getByRole('figure', { name: 'Calories by Component' })).toBeVisible();

    await user.click(
      within(summary).getByRole('button', { name: 'Collapse meal nutrition summary' }),
    );
    await waitFor(() => {
      expect(
        within(summary).queryByLabelText('Full meal nutrition values'),
      ).not.toBeInTheDocument();
    });
    expect(within(summary).getByText('95 kcal')).toBeVisible();
  });
});
