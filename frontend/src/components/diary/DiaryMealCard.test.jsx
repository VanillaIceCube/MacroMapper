import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../test-helpers/utils';
import DiaryMealCard from './DiaryMealCard';

const meal = {
  id: 9,
  name: 'Morning oats',
  notes: 'Estimated from: breakfast at home',
  confidence_score: null,
  items: [
    {
      id: 4,
      food_name: 'Rolled oats',
      servings: '1',
      serving_label: 'one bowl',
      nutrients: [{ key: 'calories', amount: '200' }],
    },
  ],
};

test('shows a saved meal’s context and invokes edit and delete for that meal', async () => {
  const user = userEvent.setup();
  const onEdit = vi.fn();
  const onDelete = vi.fn();
  renderWithProviders(
    <DiaryMealCard
      meal={meal}
      mealNumber={2}
      nutrients={{ calories: 200 }}
      dailyCalories={800}
      onEdit={onEdit}
      onDelete={onDelete}
    />,
  );

  const card = within(screen.getByRole('article'));
  expect(card.getByRole('heading', { name: 'Morning oats' })).toBeVisible();
  expect(card.getByText('Meal 02')).toBeVisible();
  expect(card.getByText('25% of daily calories')).toBeVisible();
  expect(card.getByText('breakfast at home')).toBeVisible();
  const foods = within(card.getByRole('table', { name: 'Morning oats food breakdown' }));
  expect(foods.getByText('1 × Rolled oats')).toBeVisible();
  expect(foods.getByText('200 kcal')).toBeVisible();

  await user.click(card.getByRole('button', { name: 'edit Morning oats' }));
  await user.click(card.getByRole('button', { name: 'delete Morning oats' }));
  expect(onEdit).toHaveBeenCalledExactlyOnceWith(meal);
  expect(onDelete).toHaveBeenCalledExactlyOnceWith(meal);
});

test('omits the daily share when the saved meal has no calorie total', () => {
  renderWithProviders(
    <DiaryMealCard
      meal={{ ...meal, items: [] }}
      mealNumber={1}
      nutrients={{ calories: null }}
      dailyCalories={800}
      onEdit={vi.fn()}
      onDelete={vi.fn()}
    />,
  );

  expect(screen.getByText('0 foods')).toBeVisible();
  expect(screen.queryByText(/of daily calories/)).not.toBeInTheDocument();
});
