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

export const searchFoods = (query, token) =>
  apiFetch(`/api/foods/?search=${encodeURIComponent(query)}`, {
    headers: authHeader(token),
  });

export const createPersonalFood = (payload, token) =>
  apiFetch('/api/foods/', {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(payload),
  });

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

export const followUpMealProposal = (proposalId, payload, token) =>
  apiFetch(`/api/meal-proposals/${proposalId}/follow-up/`, {
    method: 'POST',
    headers: jsonHeaders(token),
    body: JSON.stringify(payload),
  });

export const acceptMealProposal = (proposalId, token) =>
  apiFetch(`/api/meal-proposals/${proposalId}/accept/`, {
    method: 'POST',
    headers: authHeader(token),
  });
