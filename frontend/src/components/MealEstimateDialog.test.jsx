import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test-support/utils';
import { createMealProposal } from '../services/mealApiClient';
import MealEstimateDialog from './MealEstimateDialog';

vi.mock('../services/mealApiClient', () => ({
  createMealProposal: vi.fn(),
}));

const response = (body = {}, ok = true) => ({
  ok,
  json: vi.fn().mockResolvedValue(body),
});

const proposal = {
  id: 25,
  entry_date: '2026-08-16',
  name: 'Estimated double burger',
  provider_name: 'OpenAI',
  provider_model: 'gpt-test',
  confidence_score: '0.8',
  items: [],
};

describe('MealEstimateDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    createMealProposal.mockResolvedValue(response(proposal));
  });

  test('creates a proposal and hands it to the unified meal editor', async () => {
    const user = userEvent.setup();
    const onEstimated = vi.fn();
    renderWithProviders(
      <MealEstimateDialog
        date="2026-08-16"
        open
        token="access-token"
        onClose={() => {}}
        onEstimated={onEstimated}
      />,
    );

    const dialog = screen.getByRole('dialog', { name: 'Estimate a meal' });
    await user.type(
      within(dialog).getByRole('textbox', { name: 'Describe what you ate' }),
      'Double burger',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Create estimate' }));

    await waitFor(() => expect(onEstimated).toHaveBeenCalledWith(proposal));
    expect(createMealProposal).toHaveBeenCalledWith(
      { description: 'Double burger', entry_date: '2026-08-16' },
      'access-token',
    );
  });

  test('requires a description before estimating', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <MealEstimateDialog
        date="2026-08-16"
        open
        token="access-token"
        onClose={() => {}}
        onEstimated={() => {}}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Create estimate' }));
    expect(screen.getByText('Describe the meal you want to estimate.')).toBeVisible();
    expect(createMealProposal).not.toHaveBeenCalled();
  });

  test('shows an estimate error without closing the prompt', async () => {
    const user = userEvent.setup();
    createMealProposal.mockResolvedValue(
      response({ detail: 'The estimate provider is unavailable.' }, false),
    );
    renderWithProviders(
      <MealEstimateDialog
        date="2026-08-16"
        open
        token="access-token"
        onClose={() => {}}
        onEstimated={() => {}}
      />,
    );

    await user.type(screen.getByRole('textbox', { name: 'Describe what you ate' }), 'Tacos');
    await user.click(screen.getByRole('button', { name: 'Create estimate' }));

    expect(await screen.findByText('The estimate provider is unavailable.')).toBeVisible();
    expect(screen.getByRole('dialog', { name: 'Estimate a meal' })).toBeVisible();
  });
});
