import { apiFetch } from '../http/requestClient';
import {
  createDraftAdjustment,
  createMealFromDraft,
  fetchDailyDiary,
  followUpMealProposal,
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

  test('starts a draft adjustment without a proposal ID', async () => {
    const payload = {
      adjustment: 'Add an apple',
      entry_date: '2026-08-17',
      name: '',
      notes: '',
      items: [],
    };

    await expect(createDraftAdjustment(payload)).resolves.toEqual({ proposal: { id: 90 } });

    expect(apiFetch).toHaveBeenCalledWith('/api/meal-proposals/adjustments/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  });

  test('sends all reviewed fields for a follow-up to an existing proposal', async () => {
    const items = [{ key: 'apple', servings: '1' }];

    await followUpMealProposal(90, {
      follow_up: 'Add cinnamon',
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
