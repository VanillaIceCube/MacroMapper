import {
  clearSession,
  getSessionVersion,
  rotateSessionTokens,
  startSession,
} from '../../services/authentication/sessionState';
import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMealFromDraft, searchFoods } from '../../services/meals/mealApiClient';
import { renderWithProviders } from '../../test-helpers/utils';
import MealEditorDialog from './MealEditorDialog';

vi.mock('../../services/meals/mealApiClient');

beforeEach(() => startSession({ access: 'access-token', refresh: 'refresh-token' }));
afterAll(() => clearSession());

test('keeps a manual draft after a failed save and reports success when retried', async () => {
  const user = userEvent.setup();
  const onSaved = vi.fn();
  searchFoods.mockResolvedValue([
    { id: 7, name: 'Apple', current_version: { id: 9, serving_label: 'one apple' } },
  ]);
  createMealFromDraft
    .mockRejectedValueOnce(new Error('Could not save right now.'))
    .mockResolvedValueOnce({ id: 21 });

  renderWithProviders(
    <MealEditorDialog
      open
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

  expect(createMealFromDraft).toHaveBeenLastCalledWith(
    expect.objectContaining({
      name: 'Afternoon snack',
      entry_date: '2026-11-23',
      items: [expect.objectContaining({ food_item_id: 7, food_version_id: 9 })],
    }),
  );
  expect(onSaved).toHaveBeenCalledExactlyOnceWith('Meal added.');
});

test('preserves the open meal draft when the access token rotates', async () => {
  const user = userEvent.setup();
  searchFoods.mockResolvedValue([
    { id: 7, name: 'Apple', current_version: { id: 9, serving_label: 'one apple' } },
  ]);
  renderWithProviders(
    <MealEditorDialog
      open
      date="2026-11-23"
      launchMode="add"
      onClose={vi.fn()}
      onSaved={vi.fn()}
    />,
  );

  const dialog = within(await screen.findByRole('dialog', { name: /Map Your Meal/ }));
  await user.click(await dialog.findByRole('button', { name: 'Add', exact: true }));
  const mealName = dialog.getByRole('textbox', { name: 'Meal name' });
  await user.type(mealName, 'Afternoon snack');

  await act(async () => {
    rotateSessionTokens({ access: 'rotated-token' }, getSessionVersion(), 'refresh-token');
  });

  expect(mealName).toHaveValue('Afternoon snack');
  expect(dialog.getByLabelText('Apple macro values')).toBeVisible();
});
