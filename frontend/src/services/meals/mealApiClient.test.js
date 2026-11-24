import { apiFetch } from '../http/requestClient';
import {
  adjustMealProposal,
  createMealFromDraft,
  fetchDailyDiary,
  searchFoods,
  updateMealFromDraft,
} from './mealApiClient';

vi.mock('../http/requestClient', () => ({
  apiFetch: vi.fn(),
}));

describe('mealApiClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiFetch.mockResolvedValue(Response.json({ proposal: { id: 90 } }));
  });

  test('sends all reviewed fields when adjusting an existing proposal', async () => {
    const items = [{ key: 'apple', servings: '1' }];

    await adjustMealProposal(90, {
      adjustment: 'Add cinnamon',
      name: 'Apple snack',
      notes: 'Use the homemade version.',
      entry_date: '2026-08-17',
      items,
    });

    expect(apiFetch).toHaveBeenCalledWith('/api/meal-proposals/90/follow-up/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        follow_up: 'Add cinnamon',
        name: 'Apple snack',
        notes: 'Use the homemade version.',
        entry_date: '2026-08-17',
        items,
      }),
    });
  });

  test('creates a meal from the complete reviewed draft', async () => {
    const draft = {
      entry_date: '2026-08-30',
      name: 'Trail lunch',
      notes: '',
      items: [{ key: 'apple', servings: '1' }],
    };

    await createMealFromDraft(draft);

    expect(apiFetch).toHaveBeenCalledWith('/api/meals/drafts/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(draft),
    });
  });

  test('updates an existing meal from the complete reviewed draft', async () => {
    const draft = {
      entry_date: '2026-08-30',
      name: 'Trail lunch',
      notes: 'Adjusted after review.',
      items: [{ key: 'apple', servings: '2' }],
    };

    await updateMealFromDraft(42, draft);

    expect(apiFetch).toHaveBeenCalledWith('/api/meals/42/draft/', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(draft),
    });
  });

  test('returns a retry message when the diary request fails to reach the server', async () => {
    apiFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

    await expect(fetchDailyDiary('2026-11-23')).rejects.toThrow(
      'Could not load this day. Please try again.',
    );
  });

  test('rejects a diary response missing its totals', async () => {
    apiFetch.mockResolvedValueOnce(Response.json({ meals: [] }));

    await expect(fetchDailyDiary('2026-11-23')).rejects.toThrow(
      'Could not read this day. Please try again.',
    );
  });

  test('combines catalog query and filter parameters', async () => {
    apiFetch.mockResolvedValueOnce(Response.json([{ id: 1, name: 'Apple' }]));

    const results = await searchFoods('apple', {
      limit: 26,
      offset: 20,
      scope: 'personal',
      provider: 'Example Orchard',
      provenance: 'official',
      originType: 'branded',
    });

    expect(results).toEqual([{ id: 1, name: 'Apple' }]);
    expect(apiFetch).toHaveBeenCalledWith(
      '/api/foods/?search=apple&limit=26&offset=20&scope=personal&provider=Example+Orchard&provenance=official&origin_type=branded',
      undefined,
    );
  });
});
