import { apiFetch } from './requestClient';

const authHeader = (token) => ({ Authorization: `Bearer ${token}` });
const jsonHeaders = (token) => ({
  ...authHeader(token),
  'Content-Type': 'application/json',
});

export const fetchDailyDiary = (date, token) =>
  apiFetch(`/api/meals/daily/?date=${encodeURIComponent(date)}`, {
    headers: authHeader(token),
  });

export const createMeal = (payload, token) =>
  apiFetch('/api/meals/', {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(payload),
  });

export const updateMeal = (mealId, payload, token) =>
  apiFetch(`/api/meals/${mealId}/`, {
    method: 'PATCH',
    headers: jsonHeaders(token),
    body: JSON.stringify(payload),
  });

export const deleteMeal = (mealId, token) =>
  apiFetch(`/api/meals/${mealId}/`, {
    method: 'DELETE',
    headers: authHeader(token),
  });

export const searchFoods = (query, token, options = {}) => {
  const params = new URLSearchParams({ search: query });
  if (options.ordering) params.set('ordering', options.ordering);
  if (options.limit) params.set('limit', String(options.limit));
  return apiFetch(`/api/foods/?${params.toString()}`, {
    headers: authHeader(token),
  });
};

export const createMealProposal = (payload, token) =>
  apiFetch('/api/meal-proposals/', {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(payload),
  });

export const updateMealProposal = (proposalId, payload, token) =>
  apiFetch(`/api/meal-proposals/${proposalId}/`, {
    method: 'PATCH',
    headers: jsonHeaders(token),
    body: JSON.stringify(payload),
  });

export const adjustMealProposal = (proposalId, payload, token) => {
  const endpoint = proposalId
    ? `/api/meal-proposals/${proposalId}/follow-up/`
    : '/api/meal-proposals/adjustments/';
  const body = proposalId
    ? {
        follow_up: payload.adjustment,
        name: payload.name,
        notes: payload.notes,
        entry_date: payload.entry_date,
        items: payload.items,
      }
    : payload;
  return apiFetch(endpoint, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(body),
  });
};

export const acceptMealProposal = (proposalId, token) =>
  apiFetch(`/api/meal-proposals/${proposalId}/accept/`, {
    method: 'POST',
    headers: authHeader(token),
  });
