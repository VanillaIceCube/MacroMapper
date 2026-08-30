import { apiFetch } from './requestClient';
import { adjustMealProposal, createMeal, updateMeal } from './mealApiClient';

vi.mock('./requestClient', () => ({
  apiFetch: vi.fn(),
}));

describe('mealApiClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('sends all reviewed fields when adjusting an existing proposal', () => {
    const items = [{ key: 'apple', servings: '1' }];

    adjustMealProposal(
      90,
      {
        adjustment: 'Add cinnamon',
        name: 'Apple snack',
        notes: 'Use the homemade version.',
        entry_date: '2026-08-17',
        items,
      },
      'TOKEN',
    );

    expect(apiFetch).toHaveBeenCalledWith('/api/meal-proposals/90/follow-up/', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer TOKEN',
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

  test('creates a meal from the complete reviewed draft', () => {
    const draft = {
      entry_date: '2026-08-30',
      name: 'Trail lunch',
      notes: '',
      items: [{ key: 'apple', servings: '1' }],
    };

    createMeal(draft, 'TOKEN');

    expect(apiFetch).toHaveBeenCalledWith('/api/meals/drafts/', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer TOKEN',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(draft),
    });
  });

  test('updates an existing meal from the complete reviewed draft', () => {
    const draft = {
      entry_date: '2026-08-30',
      name: 'Trail lunch',
      notes: 'Adjusted after review.',
      items: [{ key: 'apple', servings: '2' }],
    };

    updateMeal(42, draft, 'TOKEN');

    expect(apiFetch).toHaveBeenCalledWith('/api/meals/42/draft/', {
      method: 'PUT',
      headers: {
        Authorization: 'Bearer TOKEN',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(draft),
    });
  });
});
