import { apiFetch } from './requestClient';
import { adjustMealProposal } from './mealApiClient';

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
});
