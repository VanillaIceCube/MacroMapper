import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DiaryPage from './DiaryPage';
import { renderWithProviders } from '../test-support/utils';
import {
  acceptMealProposal,
  adjustMealProposal,
  createMeal,
  createMealProposal,
  deleteMeal,
  fetchDailyDiary,
  searchFoods,
  updateMealProposal,
  updateMeal,
} from '../services/mealApiClient';

vi.mock('../services/mealApiClient', () => ({
  acceptMealProposal: vi.fn(),
  adjustMealProposal: vi.fn(),
  createMealProposal: vi.fn(),
  createMeal: vi.fn(),
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

const breakfastBurrito = {
  ...estimatedTaco,
  id: 71,
  name: 'Breakfast Burrito',
  provider_name: 'San Diego Breakfast Co.',
  current_version: {
    ...estimatedTaco.current_version,
    id: 72,
    serving_label: 'one burrito',
    nutrients: [
      { key: 'calories', name: 'Calories', unit: 'kcal', amount: '650.0000' },
      { key: 'protein', name: 'Protein', unit: 'g', amount: '30.0000' },
    ],
    components: [
      {
        food_item_id: 73,
        food_version_id: 74,
        food_item_name: 'Flour tortilla',
        servings: '1.0000',
        serving_quantity: '1.000',
        serving_unit: 'item',
        serving_label: 'one tortilla',
        provenance: 'ai_estimate',
        confidence_score: '0.900',
        nutrients: [{ key: 'calories', name: 'Calories', unit: 'kcal', amount: '200.0000' }],
        components: [],
      },
      {
        food_item_id: 75,
        food_version_id: 76,
        food_item_name: 'Egg and potato filling',
        servings: '1.0000',
        serving_quantity: '1.000',
        serving_unit: 'serving',
        serving_label: 'one serving',
        provenance: 'ai_estimate',
        confidence_score: '0.850',
        nutrients: [{ key: 'calories', name: 'Calories', unit: 'kcal', amount: '450.0000' }],
        components: [],
      },
    ],
  },
};

const estimatedProposal = {
  id: 90,
  name: 'Estimated lunch',
  provider_name: 'OpenAI',
  provider_model: 'gpt-test',
  confidence_score: '0.840',
  items: [
    {
      key: 'estimated-taco',
      food_item_id: 8,
      food_version_id: 10,
      name: 'Carne Asada Taco',
      provider_name: 'San Diego Taco Co.',
      origin_type: 'restaurant',
      servings: '1',
      serving_quantity: '1',
      serving_unit: 'item',
      serving_label: 'one taco',
      portion_options: [
        { key: 'base', label: 'one taco', unit_label: 'serving', serving_multiplier: '1' },
      ],
      selected_portion_key: 'base',
      provenance: 'ai_estimate',
      source_kind: 'ai_estimate',
      confidence_score: '0.910',
      is_user_modified: false,
      nutrients: {
        calories: '240',
        protein: '18',
        carbohydrates: '22',
        fat: '9',
      },
      sources: [],
      components: [],
    },
  ],
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

    const nutritionColumns = screen.getByTestId('meal-11-nutrition-columns');
    const foodTable = within(nutritionColumns).getByRole('table', {
      name: 'Breakfast food breakdown',
    });
    const macroBalance = within(nutritionColumns).getByRole('figure', {
      name: 'Breakfast Macro Balance',
    });
    expect(nutritionColumns).toHaveStyle({ alignItems: 'start' });
    expect(foodTable).toBeVisible();
    expect(macroBalance).toBeVisible();
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

    const macroSplit = await screen.findByRole('figure', { name: 'Macro Balance' });
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
    await user.click(screen.getByRole('button', { name: 'Chart your Course Manually' }));
    const addDialog = await screen.findByRole('dialog', { name: /Map Your Meal/ });
    await user.type(within(addDialog).getByRole('textbox', { name: /Meal name/ }), 'Lunch');
    await user.type(within(addDialog).getByRole('textbox', { name: 'Search catalog' }), 'Apple');
    await user.click(within(addDialog).getByRole('button', { name: 'search foods' }));
    await user.click(await within(addDialog).findByRole('button', { name: 'Add' }));
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

  test('loads 20 recent foods by default and limits broad search results', async () => {
    const user = userEvent.setup();
    const recentResults = Array.from({ length: 20 }, (_, index) => ({
      ...apple,
      id: 50 + index,
      name: `Recent food ${String(index + 1).padStart(2, '0')}`,
      current_version: { ...apple.current_version, id: 70 + index },
    }));
    const broadResults = Array.from({ length: 30 }, (_, index) => ({
      ...apple,
      id: 100 + index,
      name: `Catalog food ${String(index + 1).padStart(2, '0')}`,
      current_version: { ...apple.current_version, id: 200 + index },
    }));
    searchFoods
      .mockResolvedValueOnce(response(recentResults))
      .mockResolvedValueOnce(response(broadResults));
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [], totals: [] }));
    renderWithProviders(<DiaryPage />);

    await screen.findByText('Nothing logged yet');
    await user.click(screen.getByRole('button', { name: 'Chart your Course Manually' }));
    const dialog = await screen.findByRole('dialog', { name: 'Map Your Meal' });

    expect(await within(dialog).findByText('Recent food 01')).toBeVisible();
    expect(within(dialog).getAllByRole('button', { name: 'Add' })).toHaveLength(20);
    expect(within(dialog).getByText('20 recent')).toBeVisible();
    expect(searchFoods).toHaveBeenCalledWith('', 'access-token', {
      ordering: '-created_at',
      limit: 20,
    });

    await user.type(within(dialog).getByRole('textbox', { name: 'Search catalog' }), 'catalog');
    await user.click(within(dialog).getByRole('button', { name: 'search foods' }));

    expect(await within(dialog).findByText('Catalog food 01')).toBeVisible();
    expect(within(dialog).getAllByRole('button', { name: 'Add' })).toHaveLength(25);
    expect(within(dialog).queryByText('Catalog food 26')).not.toBeInTheDocument();
    expect(
      within(dialog).getByText(
        'Showing the first 25 results. Refine your search to find a specific food.',
      ),
    ).toBeVisible();
    expect(searchFoods).toHaveBeenLastCalledWith('catalog', 'access-token');
  });

  test('leaves a new meal name blank for generation when saving', async () => {
    const user = userEvent.setup();
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [], totals: [] }));
    createMeal.mockResolvedValue(response({ ...meal, name: 'Apple' }));
    renderWithProviders(<DiaryPage />);

    await screen.findByText('Nothing logged yet');
    await user.click(screen.getByRole('button', { name: 'Chart your Course Manually' }));
    const addDialog = await screen.findByRole('dialog', { name: /Map Your Meal/ });
    expect(
      within(addDialog).getByText('Optional. Leave blank to generate a name when you save.'),
    ).toBeVisible();
    await user.type(within(addDialog).getByRole('textbox', { name: 'Search catalog' }), 'Apple');
    await user.click(within(addDialog).getByRole('button', { name: 'search foods' }));
    await user.click(await within(addDialog).findByRole('button', { name: 'Add' }));
    await user.click(within(addDialog).getByRole('button', { name: 'Save meal' }));

    await waitFor(() =>
      expect(createMeal).toHaveBeenCalledWith(
        expect.objectContaining({
          name: '',
          item_inputs: [{ food_item: 7, servings: '1', order: 0 }],
        }),
        'access-token',
      ),
    );
  });

  test('opens Map It With AI first and Map Your Meal directly from the matching action', async () => {
    const user = userEvent.setup();
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [], totals: [] }));
    renderWithProviders(<DiaryPage />);

    await screen.findByText('Nothing logged yet');
    await user.click(screen.getByRole('button', { name: 'Map your Meal with AI' }));
    let dialog = await screen.findByRole('dialog', { name: 'Map It With AI' });
    expect(screen.getAllByRole('dialog')).toHaveLength(1);
    expect(within(dialog).getByRole('textbox', { name: 'Describe what you ate' })).toBeVisible();
    expect(screen.queryByRole('dialog', { name: /Map Your Meal/ })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(dialog).not.toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: 'Chart your Course Manually' }));
    dialog = await screen.findByRole('dialog', { name: /Map Your Meal/ });
    expect(await within(dialog).findByText('Apple')).toBeVisible();
    expect(searchFoods).toHaveBeenCalledWith('', 'access-token', {
      ordering: '-created_at',
      limit: 20,
    });
    expect(within(dialog).getByRole('region', { name: 'Meal Details' })).toBeVisible();
    expect(within(dialog).getByRole('region', { name: 'Meal macro breakdown' })).toBeVisible();
    expect(within(dialog).getByRole('region', { name: 'Meal Items' })).toBeVisible();
    expect(within(dialog).getByRole('region', { name: 'Add from the Catalog' })).toBeVisible();
    expect(within(dialog).getByText('AI Adjustments')).toBeVisible();
    await waitFor(() =>
      expect(within(dialog).getByRole('textbox', { name: 'Search catalog' })).toHaveFocus(),
    );
  });

  test('uses AI Adjustments to build and save a meal from no foods', async () => {
    const user = userEvent.setup();
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [], totals: [] }));
    adjustMealProposal.mockResolvedValue(
      response({
        applied: true,
        message: 'Added a taco.',
        proposal: estimatedProposal,
      }),
    );
    updateMealProposal.mockResolvedValue(response(estimatedProposal));
    acceptMealProposal.mockResolvedValue(response(meal));
    renderWithProviders(<DiaryPage />);

    await screen.findByText('Nothing logged yet');
    await user.click(screen.getByRole('button', { name: 'Chart your Course Manually' }));
    const dialog = await screen.findByRole('dialog', { name: 'Map Your Meal' });
    await user.type(
      within(dialog).getByRole('textbox', { name: 'Describe an AI adjustment' }),
      'Add a carne asada taco',
    );
    const entryDate = within(dialog).getByLabelText('Date').value;
    await user.click(within(dialog).getByRole('button', { name: 'Apply adjustment' }));

    await waitFor(() =>
      expect(within(dialog).getByRole('textbox', { name: 'Meal name' })).toHaveValue(
        'Estimated lunch',
      ),
    );
    expect(within(dialog).getByLabelText('Carne Asada Taco macro values')).toBeVisible();
    expect(adjustMealProposal).toHaveBeenCalledWith(
      null,
      expect.objectContaining({
        adjustment: 'Add a carne asada taco',
        entry_date: entryDate,
        name: '',
        notes: '',
        items: [],
      }),
      'access-token',
    );

    await user.click(within(dialog).getByRole('button', { name: 'Save meal' }));
    await waitFor(() =>
      expect(updateMealProposal).toHaveBeenCalledWith(
        90,
        expect.objectContaining({ name: 'Estimated lunch' }),
        'access-token',
      ),
    );
    expect(acceptMealProposal).toHaveBeenCalledWith(90, 'access-token');
    expect(createMeal).not.toHaveBeenCalled();
  });

  test('orders the Map Your Meal sections around nutrition, items, and adjustments', async () => {
    const user = userEvent.setup();
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [], totals: [] }));
    renderWithProviders(<DiaryPage />);

    await screen.findByText('Nothing logged yet');
    await user.click(screen.getByRole('button', { name: 'Chart your Course Manually' }));
    const dialog = await screen.findByRole('dialog', { name: 'Map Your Meal' });
    await user.type(within(dialog).getByRole('textbox', { name: 'Search catalog' }), 'Apple');
    await user.click(within(dialog).getByRole('button', { name: 'search foods' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Add' }));

    expect(within(dialog).getByRole('region', { name: 'Meal Details' })).toHaveStyle({
      order: '1',
    });
    expect(within(dialog).getByRole('region', { name: 'Meal macro breakdown' })).toBeVisible();
    expect(within(dialog).getByRole('region', { name: 'Meal Items' })).toHaveStyle({ order: '3' });
    expect(within(dialog).getByText('AI Adjustments')).toBeVisible();
    expect(within(dialog).getByRole('region', { name: 'Add from the Catalog' })).toHaveStyle({
      order: '5',
    });
  });

  test('validates the estimate prompt inside the unified meal dialog', async () => {
    const user = userEvent.setup();
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [], totals: [] }));
    renderWithProviders(<DiaryPage />);

    await screen.findByText('Nothing logged yet');
    await user.click(screen.getByRole('button', { name: 'Map your Meal with AI' }));
    const dialog = await screen.findByRole('dialog', { name: 'Map It With AI' });
    await user.click(within(dialog).getByRole('button', { name: 'Create estimate' }));

    expect(within(dialog).getByText('Describe the meal you want to estimate.')).toBeVisible();
    expect(createMealProposal).not.toHaveBeenCalled();
  });

  test('keeps the unified estimate prompt open when estimation fails', async () => {
    const user = userEvent.setup();
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [], totals: [] }));
    createMealProposal.mockResolvedValue(
      response({ detail: 'The estimate provider is unavailable.' }, false),
    );
    renderWithProviders(<DiaryPage />);

    await screen.findByText('Nothing logged yet');
    await user.click(screen.getByRole('button', { name: 'Map your Meal with AI' }));
    const dialog = await screen.findByRole('dialog', { name: 'Map It With AI' });
    await user.type(
      within(dialog).getByRole('textbox', { name: 'Describe what you ate' }),
      'Tacos',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Create estimate' }));

    expect(await within(dialog).findByText('The estimate provider is unavailable.')).toBeVisible();
    expect(screen.getAllByRole('dialog')).toHaveLength(1);
  });

  test('hands an AI proposal to the unified builder and combines it with catalog foods', async () => {
    const user = userEvent.setup();
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [], totals: [] }));
    createMealProposal.mockResolvedValue(response(estimatedProposal));
    updateMealProposal.mockResolvedValue(response(estimatedProposal));
    acceptMealProposal.mockResolvedValue(response(meal));
    renderWithProviders(<DiaryPage />);

    await screen.findByText('Nothing logged yet');
    await user.click(screen.getByRole('button', { name: 'Map your Meal with AI' }));
    const estimateDialog = await screen.findByRole('dialog', { name: 'Map It With AI' });
    await user.type(
      within(estimateDialog).getByRole('textbox', { name: 'Describe what you ate' }),
      'Carne asada taco',
    );
    await user.click(within(estimateDialog).getByRole('button', { name: 'Create estimate' }));

    const dialog = await screen.findByRole('dialog', { name: 'Map Your Meal' });
    expect(screen.getAllByRole('dialog')).toHaveLength(1);
    expect(await within(dialog).findByLabelText('Carne Asada Taco macro values')).toBeVisible();
    expect(within(dialog).getByText('AI Adjustments')).toBeVisible();
    await user.click(within(dialog).getByRole('button', { name: 'Expand Add from the Catalog' }));
    await user.type(within(dialog).getByRole('textbox', { name: 'Search catalog' }), 'Apple');
    await user.click(within(dialog).getByRole('button', { name: 'search foods' }));
    await user.click(await within(dialog).findByRole('button', { name: 'Add' }));
    expect(within(dialog).getByLabelText('Apple macro values')).toBeVisible();
    await user.click(within(dialog).getByRole('button', { name: 'Save meal' }));

    await waitFor(() => {
      expect(updateMealProposal).toHaveBeenCalledWith(
        90,
        expect.objectContaining({
          name: 'Estimated lunch',
          items: expect.arrayContaining([
            expect.objectContaining({ food_item_id: 7, food_version_id: 9 }),
            expect.objectContaining({ food_item_id: 8, food_version_id: 10 }),
          ]),
        }),
        'access-token',
      );
    });
    expect(acceptMealProposal).toHaveBeenCalledWith(90, 'access-token');
    expect(createMeal).not.toHaveBeenCalled();
  });

  test('keeps AI Adjustments in Map Your Meal after estimation', async () => {
    const user = userEvent.setup();
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [], totals: [] }));
    createMealProposal.mockResolvedValue(response(estimatedProposal));
    adjustMealProposal.mockResolvedValue(
      response({
        applied: true,
        message: 'Updated the meal.',
        proposal: { ...estimatedProposal, name: 'Updated estimated lunch' },
      }),
    );
    renderWithProviders(<DiaryPage />);

    await screen.findByText('Nothing logged yet');
    await user.click(screen.getByRole('button', { name: 'Map your Meal with AI' }));
    const estimateDialog = await screen.findByRole('dialog', { name: 'Map It With AI' });
    await user.type(
      within(estimateDialog).getByRole('textbox', { name: 'Describe what you ate' }),
      'Carne asada taco',
    );
    await user.click(within(estimateDialog).getByRole('button', { name: 'Create estimate' }));

    const addMealDialog = await screen.findByRole('dialog', { name: 'Map Your Meal' });
    await user.type(
      within(addMealDialog).getByRole('textbox', { name: 'Describe an AI adjustment' }),
      'Add salsa',
    );
    await user.click(within(addMealDialog).getByRole('button', { name: 'Apply adjustment' }));

    await waitFor(() =>
      expect(within(addMealDialog).getByRole('textbox', { name: 'Meal name' })).toHaveValue(
        'Updated estimated lunch',
      ),
    );
    expect(adjustMealProposal).toHaveBeenCalledWith(
      90,
      expect.objectContaining({ adjustment: 'Add salsa', name: 'Estimated lunch' }),
      'access-token',
    );
  });

  test('shows catalog estimate tags and details and restores a removed food', async () => {
    const user = userEvent.setup();
    searchFoods.mockResolvedValue(response([estimatedTaco]));
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [], totals: [] }));
    renderWithProviders(<DiaryPage />);

    await screen.findByText('Nothing logged yet');
    await user.click(screen.getByRole('button', { name: 'Chart your Course Manually' }));
    const dialog = await screen.findByRole('dialog', { name: /Map Your Meal/ });
    await user.type(
      within(dialog).getByRole('textbox', { name: 'Search catalog' }),
      'Carne Asada Taco',
    );
    await user.click(within(dialog).getByRole('button', { name: 'search foods' }));

    expect(await within(dialog).findByText('AI estimate')).toBeVisible();
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
    expect(within(dialog).getByText('No meal items yet')).toBeVisible();
  });

  test('protects an unsaved Map Your Meal draft before closing', async () => {
    const user = userEvent.setup();
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [], totals: [] }));
    renderWithProviders(<DiaryPage />);

    await screen.findByText('Nothing logged yet');
    await user.click(screen.getByRole('button', { name: 'Chart your Course Manually' }));
    const mealBuilder = await screen.findByRole('dialog', { name: /Map Your Meal/ });
    await user.type(within(mealBuilder).getByRole('textbox', { name: /Meal name/ }), 'Draft lunch');
    await user.click(within(mealBuilder).getByRole('button', { name: 'Cancel' }));

    const discardDialog = screen.getByRole('dialog', {
      name: 'Discard meal changes?',
    });
    await user.click(within(discardDialog).getByRole('button', { name: 'Keep editing' }));
    await waitFor(() =>
      expect(
        screen.queryByRole('dialog', { name: 'Discard meal changes?' }),
      ).not.toBeInTheDocument(),
    );
    const resumedBuilder = screen.getByRole('dialog', { name: /Map Your Meal/ });
    expect(resumedBuilder).toBeVisible();

    await user.click(within(resumedBuilder).getByRole('button', { name: 'Cancel' }));
    await user.click(
      within(screen.getByRole('dialog', { name: 'Discard meal changes?' })).getByRole('button', {
        name: 'Discard changes',
      }),
    );
    await waitFor(() => expect(resumedBuilder).not.toBeInTheDocument());
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

  test('shows catalog composite nutrition in Map Your Meal and expanded components', async () => {
    const user = userEvent.setup();
    searchFoods.mockResolvedValue(response([breakfastBurrito]));
    fetchDailyDiary.mockResolvedValue(response({ date: '2026-08-16', meals: [], totals: [] }));
    renderWithProviders(<DiaryPage />);

    await screen.findByText('Nothing logged yet');
    await user.click(screen.getByRole('button', { name: 'Chart your Course Manually' }));
    const dialog = await screen.findByRole('dialog', { name: /Map Your Meal/ });
    await user.type(
      within(dialog).getByRole('textbox', { name: 'Search catalog' }),
      'Breakfast Burrito',
    );
    await user.click(within(dialog).getByRole('button', { name: 'search foods' }));
    await within(dialog).findByRole('button', { name: 'Add' });
    await user.click(within(dialog).getByRole('button', { name: 'Add' }));

    expect(
      within(within(dialog).getByLabelText('Breakfast Burrito macro values')).getByText('650'),
    ).toBeVisible();
    await user.click(
      within(dialog).getByRole('button', { name: 'Expand components for Breakfast Burrito' }),
    );
    expect(
      within(within(dialog).getByLabelText('Flour tortilla macro values')).getByText('200'),
    ).toBeVisible();
    expect(
      within(within(dialog).getByLabelText('Egg and potato filling macro values')).getByText('450'),
    ).toBeVisible();
  });

  test('shows nutrition for a saved composite item and each component', async () => {
    const user = userEvent.setup();
    const compositeMeal = {
      ...meal,
      name: 'Lunch',
      items: [
        {
          ...meal.items[0],
          id: 22,
          food_item_id: 10,
          food_version_id: 12,
          food_name: 'Avocado toast',
          serving_unit: 'serving',
          serving_label: 'one serving',
          nutrients: [{ key: 'calories', name: 'Calories', unit: 'kcal', amount: '220.0000' }],
          component_snapshot: [
            {
              food_item_id: 11,
              food_version_id: 13,
              food_name: 'Avocado',
              servings: '1.0000',
              serving_quantity: '1.000',
              serving_unit: 'item',
              serving_label: 'one avocado',
              nutrients: [{ key: 'calories', name: 'Calories', unit: 'kcal', amount: '160.0000' }],
              components: [],
            },
            {
              food_item_id: 12,
              food_version_id: 14,
              food_name: 'Toast',
              servings: '1.0000',
              serving_quantity: '1.000',
              serving_unit: 'slice',
              serving_label: 'one slice',
              nutrients: [{ key: 'calories', name: 'Calories', unit: 'kcal', amount: '60.0000' }],
              components: [],
            },
          ],
        },
      ],
    };
    fetchDailyDiary.mockResolvedValue(
      response({ date: '2026-08-16', meals: [compositeMeal], totals: [] }),
    );
    renderWithProviders(<DiaryPage />);

    await user.click(await screen.findByRole('button', { name: 'edit Lunch' }));
    const dialog = screen.getByRole('dialog', { name: /Edit meal/ });
    expect(
      within(within(dialog).getByLabelText('Avocado toast macro values')).getByText('220'),
    ).toBeVisible();

    await user.click(
      within(dialog).getByRole('button', { name: 'Expand components for Avocado toast' }),
    );
    expect(
      within(within(dialog).getByLabelText('Avocado macro values')).getByText('160'),
    ).toBeVisible();
    expect(
      within(within(dialog).getByLabelText('Toast macro values')).getByText('60'),
    ).toBeVisible();
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
