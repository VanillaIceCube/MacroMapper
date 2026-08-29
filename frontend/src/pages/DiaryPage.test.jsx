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
    id: 9,
    serving_quantity: '1.000',
    serving_unit: 'item',
    serving_label: 'one apple',
    provenance: 'user_entered',
    confidence_score: null,
    portion_options: [
      {
        key: 'base',
        label: 'one apple',
        unit_label: 'serving',
        serving_multiplier: '1',
      },
      {
        key: 'half',
        label: 'half apple',
        unit_label: 'half apple',
        serving_multiplier: '0.5',
      },
    ],
    nutrients: [
      { key: 'calories', name: 'Calories', unit: 'kcal', amount: '95.0000' },
      { key: 'protein', name: 'Protein', unit: 'g', amount: '0.5000' },
      { key: 'carbohydrates', name: 'Carbohydrates', unit: 'g', amount: '25.0000' },
      { key: 'fat', name: 'Fat', unit: 'g', amount: '0.3000' },
    ],
    sources: [],
    components: [],
  },
};

const estimatedTaco = {
  ...apple,
  id: 8,
  name: 'Carne Asada Taco',
  provider_name: 'San Diego Taco Co.',
  scope: 'catalog',
  current_version: {
    ...apple.current_version,
    id: 10,
    serving_label: 'one taco',
    provenance: 'ai_estimate',
    confidence_score: '0.910',
    sources: [
      {
        title: 'Restaurant nutrition reference',
        url: 'https://example.com/taco-nutrition',
      },
    ],
    components: [
      {
        food_version_id: 12,
        food_item_name: 'Corn tortilla',
        servings: '1.000',
        components: [],
      },
    ],
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
    const sugarTotal = within(dailySummary).getByRole('group', { name: 'Sugar daily total' });
    expect(within(sugarTotal).getByText('—')).toBeInTheDocument();
    expect(screen.getByText('80% confidence')).toBeInTheDocument();
    expect(screen.getByText('1 × Apple')).toBeInTheDocument();
    expect(screen.getByText('95 kcal')).toBeInTheDocument();
    expect(screen.getByText('Not scored')).toBeInTheDocument();
    expect(screen.getByText('User entered')).toBeInTheDocument();
  });

  test('rounds macro charts and shows the original AI follow-up wording', async () => {
    const estimatedMeal = {
      ...meal,
      notes: 'Estimated from: A single apple\n\nAI follow-ups:\n- I only ate half the apple',
      items: [
        {
          ...meal.items[0],
          nutrients: [
            { key: 'calories', name: 'Calories', unit: 'kcal', amount: '95.4000' },
            { key: 'protein', name: 'Protein', unit: 'g', amount: '0.5000' },
            {
              key: 'carbohydrates',
              name: 'Carbohydrates',
              unit: 'g',
              amount: '1.5000',
            },
            { key: 'fat', name: 'Fat', unit: 'g', amount: '0.4000' },
          ],
        },
      ],
    };
    fetchDailyDiary.mockResolvedValue(
      response({
        date: '2026-08-16',
        meals: [estimatedMeal],
        totals: [
          { key: 'calories', name: 'Calories', unit: 'kcal', amount: '95.4000' },
          { key: 'protein', name: 'Protein', unit: 'g', amount: '0.5000' },
          {
            key: 'carbohydrates',
            name: 'Carbohydrates',
            unit: 'g',
            amount: '1.5000',
          },
          { key: 'fat', name: 'Fat', unit: 'g', amount: '0.4000' },
        ],
      }),
    );

    renderWithProviders(<DiaryPage />);

    const macroSplit = await screen.findByRole('figure', { name: 'Macro calorie split' });
    expect(within(macroSplit).getByText('95')).toBeInTheDocument();
    expect(within(macroSplit).getByText('1 g (17%)')).toBeInTheDocument();
    expect(within(macroSplit).getByText('2 g (52%)')).toBeInTheDocument();
    expect(within(macroSplit).getByText('0 g (31%)')).toBeInTheDocument();

    const caloriesByMeal = screen.getByRole('figure', { name: 'Calories by meal' });
    expect(within(caloriesByMeal).getByText('95 kcal (100%)')).toBeInTheDocument();

    expect(
      screen.getByText('A single apple AI follow-ups: - I only ate half the apple'),
    ).toBeVisible();
    expect(screen.queryByText(/Estimated from:/i)).not.toBeInTheDocument();
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
    expect(within(addDialog).getByRole('region', { name: 'Meal macro breakdown' })).toBeVisible();
    expect(within(addDialog).getByLabelText('Apple macro values')).toBeVisible();
    expect(
      within(addDialog).getByText('All matching foods are already in this meal.'),
    ).toBeVisible();
    expect(
      within(addDialog).queryByRole('button', { name: 'remove Apple' }),
    ).not.toBeInTheDocument();
    await user.click(within(addDialog).getByRole('button', { name: 'More actions for Apple' }));
    expect(screen.getByRole('menuitem', { name: 'Edit nutrition for Apple' })).toBeVisible();
    expect(
      screen.queryByRole('menuitem', { name: 'Show estimate details for Apple' }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole('menuitem', { name: 'Edit nutrition for Apple' }));
    await user.click(within(addDialog).getByRole('combobox', { name: 'Unit' }));
    await user.click(await screen.findByRole('option', { name: 'half apple' }));
    const quantity = within(addDialog).getByRole('spinbutton', { name: 'Count' });
    expect(quantity).toHaveValue(2);
    await user.clear(quantity);
    await user.type(quantity, '1');
    await user.click(screen.getByRole('button', { name: 'Save meal' }));

    await waitFor(() => {
      expect(createMeal).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Lunch',
          item_inputs: [{ food_item: 7, servings: '0.5', order: 0 }],
        }),
        'access-token',
      );
    });
    expect(showSnackbar).toHaveBeenCalledWith('success', 'Meal added.');
  });

  test('shows catalog estimate tags and details and restores a removed food', async () => {
    const user = userEvent.setup();
    searchFoods.mockResolvedValue(response([estimatedTaco]));
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [], totals: [] }));
    renderWithProviders(<DiaryPage />);

    await screen.findByText('Nothing logged yet');
    await user.click(screen.getByRole('button', { name: 'Add manually' }));
    const dialog = await screen.findByRole('dialog', { name: /Add meal manually/ });

    expect(within(dialog).getByText('AI estimate')).toBeVisible();
    expect(within(dialog).getByText('91% confidence')).toBeVisible();
    expect(within(dialog).getByText('San Diego Taco Co.')).toBeVisible();
    expect(
      within(dialog).queryByRole('link', { name: 'Restaurant nutrition reference' }),
    ).not.toBeInTheDocument();

    await user.click(
      within(dialog).getByRole('button', { name: 'More actions for Carne Asada Taco' }),
    );
    await user.click(
      screen.getByRole('menuitem', {
        name: 'Show estimate details for Carne Asada Taco',
      }),
    );
    expect(
      within(dialog).getByRole('link', { name: 'Restaurant nutrition reference' }),
    ).toHaveAttribute('href', 'https://example.com/taco-nutrition');

    await user.click(within(dialog).getByRole('button', { name: 'Add' }));
    expect(within(dialog).getByText('All matching foods are already in this meal.')).toBeVisible();
    expect(
      within(dialog).queryByRole('button', { name: 'remove Carne Asada Taco' }),
    ).not.toBeInTheDocument();
    expect(within(dialog).queryByText('Corn tortilla')).not.toBeInTheDocument();
    await user.click(
      within(dialog).getByRole('button', {
        name: 'Expand components for Carne Asada Taco',
      }),
    );
    expect(within(dialog).getByText('Corn tortilla')).toBeVisible();
    expect(
      within(dialog).getByRole('button', {
        name: 'Collapse components for Carne Asada Taco',
      }),
    ).toHaveAttribute('aria-expanded', 'true');

    await user.click(
      within(dialog).getByRole('button', { name: 'More actions for Carne Asada Taco' }),
    );
    expect(
      screen.getByRole('menuitem', { name: 'Show estimate details for Carne Asada Taco' }),
    ).toBeVisible();
    await user.click(screen.getByRole('menuitem', { name: 'remove Carne Asada Taco' }));

    expect(await within(dialog).findByRole('button', { name: 'Add' })).toBeVisible();
    expect(within(dialog).getByText('No foods added yet')).toBeVisible();
  });

  test('protects an unsaved manual meal draft before closing', async () => {
    const user = userEvent.setup();
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [], totals: [] }));
    renderWithProviders(<DiaryPage />);

    await screen.findByText('Nothing logged yet');
    await user.click(screen.getByRole('button', { name: 'Add manually' }));
    const editor = await screen.findByRole('dialog', { name: /Add meal manually/ });
    await user.type(within(editor).getByRole('textbox', { name: /Meal name/ }), 'Draft lunch');
    await user.click(within(editor).getByRole('button', { name: 'Cancel' }));

    const discardDialog = screen.getByRole('dialog', {
      name: 'Discard manual meal changes?',
    });
    await user.click(within(discardDialog).getByRole('button', { name: 'Keep editing' }));
    await waitFor(() =>
      expect(
        screen.queryByRole('dialog', { name: 'Discard manual meal changes?' }),
      ).not.toBeInTheDocument(),
    );
    const resumedEditor = screen.getByRole('dialog', { name: /Add meal manually/ });
    expect(resumedEditor).toBeVisible();

    await user.click(within(resumedEditor).getByRole('button', { name: 'Cancel' }));
    await user.click(
      within(screen.getByRole('dialog', { name: 'Discard manual meal changes?' })).getByRole(
        'button',
        { name: 'Discard changes' },
      ),
    );
    await waitFor(() => expect(resumedEditor).not.toBeInTheDocument());
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
    const servings = within(dialog).getByLabelText('Count');
    await user.clear(servings);
    await user.type(servings, '2');
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }));

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
