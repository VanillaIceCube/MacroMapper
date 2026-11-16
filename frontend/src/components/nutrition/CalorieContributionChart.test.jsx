import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../test-helpers/utils';
import CalorieContributionChart from './CalorieContributionChart';

describe('CalorieContributionChart', () => {
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

  test('renders empty state safely when contributions are empty or zero', () => {
    renderWithProviders(
      <CalorieContributionChart
        contributions={[]}
        title="Calories by Meal Item"
        emptyText="No calorie contribution data."
      />,
    );

    const figure = screen.getByRole('figure', { name: 'Calories by Meal Item' });
    expect(within(figure).getByText('No calorie contribution data.')).toBeInTheDocument();
  });
});
