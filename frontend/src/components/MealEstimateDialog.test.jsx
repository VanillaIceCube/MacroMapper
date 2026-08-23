import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test-support/utils';
import {
  acceptMealProposal,
  createMealProposal,
  searchFoods,
  updateMealProposal,
} from '../services/mealApiClient';
import MealEstimateDialog from './MealEstimateDialog';

vi.mock('../services/mealApiClient', () => ({
  acceptMealProposal: vi.fn(),
  createMealProposal: vi.fn(),
  searchFoods: vi.fn(),
  updateMealProposal: vi.fn(),
}));

const response = (body = {}, ok = true) => ({
  ok,
  json: vi.fn().mockResolvedValue(body),
});

const source = {
  title: 'Official restaurant nutrition',
  provider: 'Example Restaurant',
  url: 'https://example.com/nutrition',
  accessed_on: null,
  is_official: true,
};

const component = {
  key: 'ai-0.0',
  food_item_id: null,
  food_version_id: null,
  name: 'Burger patty',
  provider_name: 'Example Restaurant',
  origin_type: 'restaurant',
  servings: '2',
  serving_quantity: '1',
  serving_unit: 'item',
  serving_label: 'one patty',
  provenance: 'ai_estimate',
  source_kind: 'ai_estimate',
  confidence_score: '0.8',
  nutrients: { calories: '200', protein: '12' },
  sources: [source],
  components: [],
};

const proposal = {
  id: 25,
  description: 'Double burger',
  entry_date: '2026-08-16',
  name: 'Estimated double burger',
  generator: 'openai',
  provider_name: 'OpenAI',
  provider_model: 'gpt-test',
  confidence_score: '0.8',
  items: [
    {
      ...component,
      key: 'ai-0',
      name: 'Double burger',
      servings: '1',
      nutrients: { calories: '400', protein: '24' },
      components: [component],
    },
  ],
};

const kefir = {
  ...component,
  key: 'ai-1',
  name: 'Plain kefir yogurt',
  servings: '1',
  serving_label: 'one cup',
  nutrients: { calories: '104', protein: '9.2', carbohydrates: '11.6', fat: '2.5' },
  components: [],
};

const apple = {
  id: 7,
  name: 'Apple',
  provider_name: '',
  origin_type: 'generic',
  scope: 'shared',
  current_version: {
    id: 9,
    serving_quantity: '1',
    serving_unit: 'item',
    serving_label: 'one apple',
    provenance: 'official',
    confidence_score: '0.99',
    nutrients: [{ key: 'calories', amount: '95' }],
    sources: [source],
  },
};

describe('MealEstimateDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    createMealProposal.mockResolvedValue(response(proposal));
    updateMealProposal.mockResolvedValue(response(proposal));
    acceptMealProposal.mockResolvedValue(response({ id: 11 }));
    searchFoods.mockResolvedValue(response([apple]));
  });

  test('creates, labels, edits, expands, and accepts a sourced proposal', async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    renderWithProviders(
      <MealEstimateDialog
        date="2026-08-16"
        open
        token="access-token"
        onClose={() => {}}
        onSaved={onSaved}
      />,
    );

    const promptDialog = screen.getByRole('dialog', { name: 'Estimate a meal' });
    await user.type(
      within(promptDialog).getByRole('textbox', { name: 'Describe what you ate' }),
      'Double burger',
    );
    await user.click(within(promptDialog).getByRole('button', { name: 'Create estimate' }));

    const reviewDialog = await screen.findByRole('dialog', { name: 'Review meal estimate' });
    expect(within(reviewDialog).getByText('Model gpt-test')).toBeInTheDocument();
    const macroBreakdown = within(reviewDialog).getByRole('region', {
      name: 'Meal macro breakdown',
    });
    expect(macroBreakdown).toHaveTextContent(/400\s*kcal/);
    expect(within(reviewDialog).getByLabelText('Full meal nutrition values')).toBeVisible();
    expect(
      within(reviewDialog).getByRole('img', {
        name: 'Macro calorie split: protein 100%, carbs 0%, fat 0%',
      }),
    ).toBeVisible();
    expect(within(reviewDialog).getByText('24 g (100%)')).toBeVisible();
    expect(within(reviewDialog).getAllByText('0 g (0%)')).toHaveLength(2);
    expect(within(reviewDialog).getByLabelText('Burger patty 400 kcal (100%)')).toBeVisible();
    expect(macroBreakdown).toHaveTextContent(/24\s*g/);

    await user.click(
      within(reviewDialog).getByRole('button', { name: 'Collapse meal nutrition summary' }),
    );
    await waitFor(() => {
      expect(
        within(reviewDialog).queryByLabelText('Full meal nutrition values'),
      ).not.toBeInTheDocument();
    });
    await user.click(
      within(reviewDialog).getByRole('button', { name: 'Expand meal nutrition summary' }),
    );
    expect(await within(reviewDialog).findByLabelText('Full meal nutrition values')).toBeVisible();

    expect(within(reviewDialog).getByLabelText('Double burger macro values')).toHaveTextContent(
      /Protein\s*24\s*g/,
    );
    expect(
      within(reviewDialog).queryByLabelText('Burger patty macro values'),
    ).not.toBeInTheDocument();
    await user.click(
      within(reviewDialog).getByRole('button', { name: 'Expand components for Double burger' }),
    );
    expect(
      await within(reviewDialog).findByLabelText('Burger patty macro values'),
    ).toHaveTextContent(/Protein\s*24\s*g/);

    expect(within(reviewDialog).queryByText('AI estimate')).not.toBeInTheDocument();
    await user.click(
      within(reviewDialog).getByRole('button', {
        name: 'Show estimate details for Double burger',
      }),
    );
    expect(within(reviewDialog).getByText('AI estimate')).toBeVisible();
    expect(
      within(reviewDialog).getByRole('link', { name: 'Official restaurant nutrition' }),
    ).toHaveAttribute('href', 'https://example.com/nutrition');

    const quantity = within(reviewDialog).getByRole('spinbutton', { name: 'Amount' });
    await user.clear(quantity);
    await user.type(quantity, '1');
    expect(
      within(reviewDialog).getByRole('region', { name: 'Meal macro breakdown' }),
    ).toHaveTextContent(/200\s*kcal/);
    expect(within(reviewDialog).getByLabelText('Burger patty 200 kcal (100%)')).toBeVisible();
    await user.click(within(reviewDialog).getByRole('button', { name: 'remove Burger patty' }));
    expect(within(reviewDialog).queryByText('Burger patty')).not.toBeInTheDocument();

    expect(
      within(reviewDialog).queryByRole('textbox', { name: 'Search catalog' }),
    ).not.toBeInTheDocument();
    await user.click(within(reviewDialog).getByRole('button', { name: 'Expand add another food' }));
    await user.type(within(reviewDialog).getByRole('textbox', { name: 'Search catalog' }), 'Apple');
    await user.click(within(reviewDialog).getByRole('button', { name: 'search proposal foods' }));
    await user.click(await within(reviewDialog).findByRole('button', { name: 'Add' }));
    expect(within(reviewDialog).getByRole('heading', { name: 'Apple' })).toBeInTheDocument();

    await user.click(within(reviewDialog).getByRole('button', { name: 'Save to diary' }));

    await waitFor(() => {
      expect(updateMealProposal).toHaveBeenCalledWith(
        25,
        expect.objectContaining({
          items: expect.arrayContaining([expect.objectContaining({ name: 'Apple' })]),
        }),
        'access-token',
      );
    });
    expect(acceptMealProposal).toHaveBeenCalledWith(25, 'access-token');
    expect(onSaved).toHaveBeenCalledWith('Estimated meal added to your diary.');
  });

  test('shows a provider error without closing the dialog', async () => {
    const user = userEvent.setup();
    createMealProposal.mockResolvedValue(
      response({ detail: 'Meal estimation is not configured.' }, false),
    );
    renderWithProviders(
      <MealEstimateDialog
        date="2026-08-16"
        open
        token="access-token"
        onClose={() => {}}
        onSaved={() => {}}
      />,
    );
    await user.type(screen.getByRole('textbox', { name: 'Describe what you ate' }), 'Unknown meal');
    await user.click(screen.getByRole('button', { name: 'Create estimate' }));
    expect(await screen.findByText('Meal estimation is not configured.')).toBeInTheDocument();
    expect(screen.getByRole('dialog', { name: 'Estimate a meal' })).toBeInTheDocument();
  });

  test('charts the largest meal-level components instead of nested ingredients', async () => {
    const user = userEvent.setup();
    createMealProposal.mockResolvedValue(
      response({
        ...proposal,
        name: 'Burger and kefir',
        items: [...proposal.items, kefir],
      }),
    );
    renderWithProviders(
      <MealEstimateDialog
        date="2026-08-16"
        open
        token="access-token"
        onClose={() => {}}
        onSaved={() => {}}
      />,
    );

    await user.type(
      screen.getByRole('textbox', { name: 'Describe what you ate' }),
      'Burger and kefir',
    );
    await user.click(screen.getByRole('button', { name: 'Create estimate' }));

    const reviewDialog = await screen.findByRole('dialog', { name: 'Review meal estimate' });
    const componentChart = within(reviewDialog).getByLabelText('Component calorie chart');
    expect(within(componentChart).getByLabelText('Double burger 400 kcal (79%)')).toBeVisible();
    expect(
      within(componentChart).getByLabelText('Plain kefir yogurt 104 kcal (21%)'),
    ).toBeVisible();
    expect(
      within(componentChart).queryByLabelText('Burger patty 400 kcal (79%)'),
    ).not.toBeInTheDocument();
  });
});
