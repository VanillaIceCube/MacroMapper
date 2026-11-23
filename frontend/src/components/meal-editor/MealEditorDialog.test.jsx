import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMeal, searchFoods } from '../../services/mealApiClient';
import { renderWithProviders } from '../../test-helpers/utils';
import MealEditorDialog from './MealEditorDialog';

vi.mock('../../services/mealApiClient');

test('keeps a manual draft after a failed save and reports success when retried', async () => {
  const user = userEvent.setup();
  const onSaved = vi.fn();
  searchFoods.mockResolvedValue(
    Response.json([
      { id: 7, name: 'Apple', current_version: { id: 9, serving_label: 'one apple' } },
    ]),
  );
  createMeal
    .mockResolvedValueOnce(Response.json({ detail: 'Could not save right now.' }, { status: 503 }))
    .mockResolvedValueOnce(Response.json({ id: 21 }, { status: 201 }));

  renderWithProviders(
    <MealEditorDialog
      open
      token="access-token"
      date="2026-11-23"
      meal={null}
      launchMode="add"
      onClose={vi.fn()}
      onSaved={onSaved}
    />,
  );

  const dialog = within(await screen.findByRole('dialog', { name: /Map Your Meal/ }));
  await user.click(await dialog.findByRole('button', { name: 'Add', exact: true }));
  const mealName = dialog.getByRole('textbox', { name: 'Meal name' });
  await user.type(mealName, 'Afternoon snack');
  const saveMeal = dialog.getByRole('button', { name: 'Save meal' });
  await user.click(saveMeal);

  expect(await dialog.findByText('Could not save right now.')).toBeVisible();
  expect(mealName).toHaveValue('Afternoon snack');
  expect(dialog.getByLabelText('Apple macro values')).toBeVisible();
  expect(onSaved).not.toHaveBeenCalled();

  await user.click(saveMeal);

  expect(createMeal).toHaveBeenLastCalledWith(
    expect.objectContaining({
      name: 'Afternoon snack',
      entry_date: '2026-11-23',
      items: [expect.objectContaining({ food_item_id: 7, food_version_id: 9 })],
    }),
    'access-token',
  );
  expect(onSaved).toHaveBeenCalledExactlyOnceWith('Meal added.');
});
