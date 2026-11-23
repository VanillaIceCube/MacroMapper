import { clearSession, startSession } from '../../services/authentication/sessionState';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { searchFoods } from '../../services/meals/mealApiClient';
import { renderWithProviders } from '../../test-helpers/utils';
import FoodCatalogPicker from './FoodCatalogPicker';

vi.mock('../../services/meals/mealApiClient');

beforeEach(() => startSession({ access: 'access-token', refresh: 'refresh-token' }));
afterEach(() => clearSession());

test('hides foods already in the draft and sends the chosen food to the editor', async () => {
  const user = userEvent.setup();
  const apple = { id: 7, name: 'Apple', current_version: { serving_label: 'one apple' } };
  const pear = { id: 8, name: 'Pear', current_version: { serving_label: 'one pear' } };
  const onAddFood = vi.fn();
  searchFoods.mockResolvedValue([apple, pear]);

  renderWithProviders(
    <FoodCatalogPicker open mealItems={[{ food_item: '7' }]} onAddFood={onAddFood} />,
  );

  const catalog = within(screen.getByRole('region', { name: 'Add from the Catalog' }));
  expect(await catalog.findByText('Pear')).toBeVisible();
  expect(catalog.queryByText('Apple')).not.toBeInTheDocument();

  await user.click(catalog.getByRole('button', { name: 'Add', exact: true }));

  expect(onAddFood).toHaveBeenCalledExactlyOnceWith(pear);
  expect(catalog.getByText('Pear added to Meal Items.')).toBeVisible();
});

test('retries a failed page with the applied search and keeps the foods already loaded', async () => {
  const user = userEvent.setup();
  const foods = Array.from({ length: 21 }, (_, index) => ({
    id: index + 1,
    name: `Orchard food ${index + 1}`,
    current_version: { serving_label: 'one serving' },
  }));
  searchFoods
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce(foods)
    .mockRejectedValueOnce(new Error('Could not load more foods.'))
    .mockResolvedValueOnce([foods[19], foods[20]]);

  renderWithProviders(<FoodCatalogPicker open mealItems={[]} onAddFood={vi.fn()} />);

  const catalog = within(screen.getByRole('region', { name: 'Add from the Catalog' }));
  const search = catalog.getByRole('textbox', { name: 'Search catalog' });
  await user.type(search, 'orchard{Enter}');
  await user.click(await catalog.findByRole('button', { name: 'Show 20 more' }));

  expect(await catalog.findByText('Could not load more foods.')).toBeVisible();
  expect(catalog.getByText('Orchard food 1')).toBeVisible();
  expect(catalog.queryByText('Orchard food 21')).not.toBeInTheDocument();

  await user.type(search, ' draft');
  await user.click(catalog.getByRole('button', { name: 'Retry' }));

  expect(await catalog.findByText('Orchard food 21')).toBeVisible();
  expect(catalog.getByText('Orchard food 1')).toBeVisible();
  expect(catalog.getAllByText('Orchard food 20')).toHaveLength(1);
  expect(search).toHaveValue('orchard draft');
  expect(searchFoods).toHaveBeenLastCalledWith('orchard', {
    limit: 21,
    offset: 20,
    ordering: 'relevance,name,id',
  });
});
