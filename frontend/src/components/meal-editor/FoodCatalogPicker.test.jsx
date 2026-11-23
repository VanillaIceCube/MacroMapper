import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { searchFoods } from '../../services/mealApiClient';
import { renderWithProviders } from '../../test-helpers/utils';
import FoodCatalogPicker from './FoodCatalogPicker';

vi.mock('../../services/mealApiClient');

test('hides foods already in the draft and sends the chosen food to the editor', async () => {
  const user = userEvent.setup();
  const apple = { id: 7, name: 'Apple', current_version: { serving_label: 'one apple' } };
  const pear = { id: 8, name: 'Pear', current_version: { serving_label: 'one pear' } };
  const onAddFood = vi.fn();
  searchFoods.mockResolvedValue(Response.json([apple, pear]));

  renderWithProviders(
    <FoodCatalogPicker
      open
      token="access-token"
      mealItems={[{ food_item: '7' }]}
      onAddFood={onAddFood}
    />,
  );

  const catalog = within(screen.getByRole('region', { name: 'Add from the Catalog' }));
  expect(await catalog.findByText('Pear')).toBeVisible();
  expect(catalog.queryByText('Apple')).not.toBeInTheDocument();

  await user.click(catalog.getByRole('button', { name: 'Add', exact: true }));

  expect(onAddFood).toHaveBeenCalledExactlyOnceWith(pear);
  expect(catalog.getByText('Pear added to Meal Items.')).toBeVisible();
});
