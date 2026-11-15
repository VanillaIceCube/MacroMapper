import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../test-helpers/utils';
import MealNutritionSummary from './MealNutritionSummary';

describe('MealNutritionSummary', () => {
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
