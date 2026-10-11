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

  test('renders, summarizes, and explains a reusable calories-by-x chart on hover only for Other (...)', async () => {
    const user = userEvent.setup();
    const contributions = [600, 500, 400, 300, 100, 200].map((calories, index) => ({
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

    // Normal meal-item bar should NOT display a tooltip
    const normalItemBar = within(figure).getByLabelText('Meal 0 600 kilocalories (29 percent)');
    await user.hover(normalItemBar);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();

    // Hovering Other (...) bar should NOT show a tooltip
    const otherBar = within(figure).getByRole('img', {
      name: 'Other meals (2) macro calorie stack: protein 300 kilocalories',
    });
    await user.hover(otherBar);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();

    // Hovering directly over the Other (...) text label displays a tooltip listing grouped items descending by calories
    const otherLabel = within(figure).getByText('Other meals (2)');
    await user.hover(otherLabel);

    const tooltip = await screen.findByRole('tooltip');
    expect(within(tooltip).getByText('Meal 5')).toBeInTheDocument();
    expect(within(tooltip).getByText('200 kcal')).toBeInTheDocument();
    expect(within(tooltip).getByText('Meal 4')).toBeInTheDocument();
    expect(within(tooltip).getByText('100 kcal')).toBeInTheDocument();

    // Moving off Other (...) dismisses tooltip
    await user.unhover(otherLabel);
    await waitFor(() => {
      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    });
  });

  test('does not show tooltips when no items are grouped into Other', async () => {
    const user = userEvent.setup();
    const contributions = [600, 500, 400].map((calories, index) => ({
      key: `meal-${index}`,
      name: `Meal ${index}`,
      calories,
      protein: calories / 4,
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
    const normalItemBar = within(figure).getByLabelText('Meal 0 600 kilocalories (40 percent)');
    await user.hover(normalItemBar);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  test('handles componentNames fallback when groupedItems is not provided', async () => {
    const user = userEvent.setup();
    const contributions = [
      { key: 'item-1', name: 'Item 1', calories: 500 },
      {
        key: 'other-items',
        name: 'Other (2)',
        isOther: true,
        componentNames: ['Fallback Item A', 'Fallback Item B'],
        calories: 200,
      },
    ];
    renderWithProviders(
      <CalorieContributionChart
        contributions={contributions}
        title="Calories by Meal Item"
        chartAriaLabel="Meal item calorie chart"
        otherKey="other-items"
      />,
    );

    const figure = screen.getByRole('figure', { name: 'Calories by Meal Item' });
    const otherLabel = within(figure).getByText('Other (2)');
    await user.hover(otherLabel);

    const tooltip = await screen.findByRole('tooltip');
    expect(within(tooltip).getByText('Fallback Item A')).toBeInTheDocument();
    expect(within(tooltip).getByText('Fallback Item B')).toBeInTheDocument();
    expect(within(tooltip).queryByText(/kcal/)).not.toBeInTheDocument();
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
    expect(within(summary).getByRole('figure', { name: 'Calories by Meal Item' })).toBeVisible();

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
