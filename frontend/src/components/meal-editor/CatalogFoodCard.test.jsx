import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../test-helpers/utils';
import CatalogFoodCard from './CatalogFoodCard';

const food = {
  id: 15,
  name: 'Orchard pear',
  scope: 'shared',
  current_version: {
    serving_label: 'one pear',
    provenance: 'ai_estimate',
    confidence_score: '0.85',
    sources: [{ title: 'Nutrition reference', url: 'https://example.com/nutrition' }],
  },
};

test('sends the chosen food and menu anchor to the picker', async () => {
  const user = userEvent.setup();
  const onAddFood = vi.fn();
  const onOpenActions = vi.fn();
  renderWithProviders(
    <ul>
      <CatalogFoodCard
        food={food}
        disabled={false}
        actionsOpen={false}
        detailsOpen={false}
        onAddFood={onAddFood}
        onOpenActions={onOpenActions}
      />
    </ul>,
  );

  expect(screen.getByText('one pear')).toBeVisible();
  expect(screen.getByText('Shared')).toBeVisible();
  expect(
    screen.queryByRole('region', { name: 'Orchard pear estimate details' }),
  ).not.toBeInTheDocument();
  const more = screen.getByRole('button', { name: 'More actions for Orchard pear' });
  expect(more).toHaveAttribute('aria-expanded', 'false');
  await user.click(screen.getByRole('button', { name: 'Add' }));
  await user.click(more);
  expect(onAddFood).toHaveBeenCalledExactlyOnceWith(food);
  expect(onOpenActions).toHaveBeenCalledExactlyOnceWith(food.id, more);
});

test('reflects the picker’s disabled actions, open menu and evidence details', () => {
  renderWithProviders(
    <ul>
      <CatalogFoodCard
        food={food}
        disabled
        actionsOpen
        detailsOpen
        onAddFood={vi.fn()}
        onOpenActions={vi.fn()}
      />
    </ul>,
  );

  expect(screen.getByRole('button', { name: 'Add' })).toBeDisabled();
  const more = screen.getByRole('button', { name: 'More actions for Orchard pear' });
  expect(more).toBeDisabled();
  expect(more).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByRole('region', { name: 'Orchard pear estimate details' })).toBeVisible();
  expect(screen.getByText('85% Confidence')).toBeVisible();
  expect(screen.getByRole('link', { name: 'Nutrition reference' })).toHaveAttribute(
    'href',
    food.current_version.sources[0].url,
  );
});
