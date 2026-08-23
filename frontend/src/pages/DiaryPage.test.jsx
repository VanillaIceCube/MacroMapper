import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DiaryPage from './DiaryPage';
import { renderWithProviders } from '../test-support/utils';
import {
  createMeal,
  createPersonalFood,
  deleteMeal,
  fetchDailyDiary,
  searchFoods,
  updateMeal,
} from '../services/mealApiClient';

vi.mock('../services/mealApiClient', () => ({
  acceptMealProposal: vi.fn(),
  createMealProposal: vi.fn(),
  createMeal: vi.fn(),
  createPersonalFood: vi.fn(),
  deleteMeal: vi.fn(),
  fetchDailyDiary: vi.fn(),
  searchFoods: vi.fn(),
  updateMealProposal: vi.fn(),
  updateMeal: vi.fn(),
}));

const response = (body = {}, ok = true) => ({
  ok,
  json: vi.fn().mockResolvedValue(body),
});

const apple = {
  id: 7,
  name: 'Apple',
  provider_name: '',
  scope: 'personal',
  current_version: {
    serving_quantity: '1.000',
    serving_unit: 'item',
    serving_label: 'one apple',
  },
};

const meal = {
  id: 11,
  entry_date: '2026-08-16',
  name: 'Breakfast',
  notes: 'Early meal',
  confidence_score: '0.800',
  items: [
    {
      id: 21,
      food_item_id: 7,
      food_version_id: 9,
      food_name: 'Apple',
      provider_name: '',
      servings: '1.0000',
      serving_quantity: '1.000',
      serving_unit: 'item',
      serving_label: 'one apple',
      provenance: 'user_entered',
      confidence_score: null,
      component_snapshot: [],
      nutrients: [{ key: 'calories', name: 'Calories', unit: 'kcal', amount: '95.0000' }],
    },
  ],
};

describe('DiaryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    sessionStorage.setItem('accessToken', 'access-token');
    searchFoods.mockResolvedValue(response([apple]));
  });

  test('shows saved meals and daily totals', async () => {
    fetchDailyDiary.mockResolvedValue(
      response({
        date: '2026-08-16',
        meals: [meal],
        totals: [
          { key: 'calories', name: 'Calories', unit: 'kcal', amount: '95.0000' },
          { key: 'protein', name: 'Protein', unit: 'g', amount: '0.5000' },
          { key: 'sugar', name: 'Sugar', unit: 'g', amount: null },
        ],
      }),
    );

    renderWithProviders(<DiaryPage />);

    expect(await screen.findByRole('heading', { name: 'Breakfast' })).toBeInTheDocument();
    const dailySummary = screen.getByRole('region', { name: 'Daily summary' });
    expect(within(dailySummary).getByText('95', { selector: 'h5' })).toBeInTheDocument();
    expect(within(dailySummary).getByText('0.5', { selector: 'h5' })).toBeInTheDocument();
    expect(
      within(within(dailySummary).getByText('Sugar').parentElement).getByText('—'),
    ).toBeInTheDocument();
    expect(screen.getByText('80% confidence')).toBeInTheDocument();
    expect(screen.getByText('1 × Apple')).toBeInTheDocument();
    expect(screen.getByText('95 kcal')).toBeInTheDocument();
    expect(screen.getByText('Not scored')).toBeInTheDocument();
    expect(screen.getByText('User entered')).toBeInTheDocument();
  });

  test('creates a meal from a searched catalog food', async () => {
    const user = userEvent.setup();
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [], totals: [] }));
    createMeal.mockResolvedValue(response(meal));
    const showSnackbar = vi.fn();
    renderWithProviders(<DiaryPage showSnackbar={showSnackbar} />);

    await screen.findByText('Nothing logged yet');
    await user.click(screen.getByRole('button', { name: 'Add manually' }));
    const addDialog = await screen.findByRole('dialog', { name: /Add meal manually/ });
    await user.type(within(addDialog).getByRole('textbox', { name: /Meal name/ }), 'Lunch');
    await user.click(await screen.findByRole('button', { name: 'Add' }));
    await user.click(screen.getByRole('button', { name: 'Save meal' }));

    await waitFor(() => {
      expect(createMeal).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Lunch',
          item_inputs: [{ food_item: 7, servings: '1', order: 0 }],
        }),
        'access-token',
      );
    });
    expect(showSnackbar).toHaveBeenCalledWith('success', 'Meal added.');
  });

  test('creates a personal food with explicit nutrient values', async () => {
    const user = userEvent.setup();
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [], totals: [] }));
    createPersonalFood.mockResolvedValue(response(apple));
    renderWithProviders(<DiaryPage />);

    await screen.findByText('Nothing logged yet');
    await user.click(screen.getByRole('button', { name: 'Add manually' }));
    const dialog = await screen.findByRole('dialog', { name: /Add meal manually/ });
    await user.click(within(dialog).getByText('Create a personal food'));
    await user.type(within(dialog).getByRole('textbox', { name: 'Food name' }), 'Apple');
    await user.type(within(dialog).getByRole('spinbutton', { name: 'Calories (kcal)' }), '95');
    await user.type(within(dialog).getByRole('spinbutton', { name: 'Fiber (g)' }), '4');
    await user.click(within(dialog).getByRole('button', { name: 'Create and add food' }));

    await waitFor(() => {
      expect(createPersonalFood).toHaveBeenCalledWith(
        expect.objectContaining({
          definition: expect.objectContaining({
            nutrients: { calories: '95', fiber: '4' },
          }),
        }),
        'access-token',
      );
    });
  });

  test('edits a meal and replaces its component quantity', async () => {
    const user = userEvent.setup();
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [meal], totals: [] }));
    updateMeal.mockResolvedValue(response({ ...meal, name: 'Brunch' }));
    renderWithProviders(<DiaryPage />);

    await user.click(await screen.findByRole('button', { name: 'edit Breakfast' }));
    const dialog = screen.getByRole('dialog', { name: /Edit meal/ });
    const nameInput = within(dialog).getByRole('textbox', { name: /Meal name/ });
    await user.clear(nameInput);
    await user.type(nameInput, 'Brunch');
    const servings = within(dialog).getByLabelText('Servings');
    await user.clear(servings);
    await user.type(servings, '2');
    await user.click(within(dialog).getByRole('button', { name: 'Save meal' }));

    await waitFor(() => {
      expect(updateMeal).toHaveBeenCalledWith(
        11,
        expect.objectContaining({
          name: 'Brunch',
          item_inputs: [{ food_item: 7, food_version: 9, servings: '2', order: 0 }],
        }),
        'access-token',
      );
    });
  });

  test('deletes a meal after confirmation', async () => {
    const user = userEvent.setup();
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [meal], totals: [] }));
    deleteMeal.mockResolvedValue(response(null));
    renderWithProviders(<DiaryPage />);

    await user.click(await screen.findByRole('button', { name: 'delete Breakfast' }));
    const dialog = screen.getByRole('dialog', { name: 'Delete Breakfast?' });
    await user.click(within(dialog).getByRole('button', { name: 'Delete meal' }));

    await waitFor(() => expect(deleteMeal).toHaveBeenCalledWith(11, 'access-token'));
  });
});
