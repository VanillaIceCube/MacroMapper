import { apiFetch } from '../http/requestClient';
import { getResponseErrorMessage, safeReadJson } from '../http/apiResponse';

function jsonRequest(method, payload) {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  };
}

async function requestMeal(path, options, failureMessage, networkMessage = failureMessage) {
  let response;
  try {
    response = await apiFetch(path, options);
  } catch (error) {
    throw new Error(networkMessage, { cause: error });
  }
  if (!response.ok) {
    throw new Error(await getResponseErrorMessage(response, failureMessage));
  }
  return response;
}

export async function fetchDailyDiary(date) {
  const response = await requestMeal(
    `/api/meals/daily/?date=${encodeURIComponent(date)}`,
    undefined,
    'Could not load this day.',
    'Could not load this day. Please try again.',
  );
  const result = await safeReadJson(response);
  if (!Array.isArray(result?.meals) || !Array.isArray(result?.totals)) {
    throw new Error('Could not read this day. Please try again.');
  }
  return result;
}

const saveNetworkMessage = 'Could not save this meal. Your draft is still here. Please try again.';

export async function createMealFromDraft(payload) {
  await requestMeal(
    '/api/meals/drafts/',
    jsonRequest('POST', payload),
    'Could not save this meal.',
    saveNetworkMessage,
  );
}

export async function updateMealFromDraft(mealId, payload) {
  await requestMeal(
    `/api/meals/${mealId}/draft/`,
    jsonRequest('PUT', payload),
    'Could not save this meal.',
    saveNetworkMessage,
  );
}

export async function deleteMeal(mealId) {
  await requestMeal(`/api/meals/${mealId}/`, { method: 'DELETE' }, 'Could not delete this meal.');
}

export async function createMealProposal(payload) {
  const response = await requestMeal(
    '/api/meal-proposals/',
    jsonRequest('POST', payload),
    'Could not estimate this meal.',
    'Could not reach the server. Your meal description is still here. Please try again.',
  );
  const proposal = await safeReadJson(response);
  if (!proposal) throw new Error('Could not parse estimation response.');
  return proposal;
}

export async function updateMealProposal(proposalId, payload) {
  await requestMeal(
    `/api/meal-proposals/${proposalId}/`,
    jsonRequest('PATCH', payload),
    'Could not save your meal draft.',
    saveNetworkMessage,
  );
}

export async function acceptMealProposal(proposalId) {
  await requestMeal(
    `/api/meal-proposals/${proposalId}/accept/`,
    { method: 'POST' },
    'Could not add this meal to your diary.',
    saveNetworkMessage,
  );
}

async function requestAdjustment(path, payload) {
  const response = await requestMeal(
    path,
    jsonRequest('POST', payload),
    'Could not apply that adjustment. Your current meal is still here.',
    'Could not reach AI. Your current meal and adjustment are still here.',
  );
  const result = await safeReadJson(response);
  if (!result) throw new Error('Could not parse adjustment response.');
  return result;
}

export const adjustMeal = (mealId, payload) =>
  requestAdjustment(`/api/meals/${mealId}/adjustments/`, payload);

export const adjustMealProposal = (proposalId, payload) => {
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
  return requestAdjustment(endpoint, body);
};

export const searchFoods = async (query, options = {}) => {
  const params = new URLSearchParams({ search: query });
  if (options.ordering) params.set('ordering', options.ordering);
  if (options.limit) params.set('limit', String(options.limit));
  if (options.offset) params.set('offset', String(options.offset));
  if (options.scope && options.scope !== 'all') params.set('scope', options.scope);
  if (options.provider) params.set('provider', options.provider);
  if (options.provenance && options.provenance !== 'all') {
    params.set('provenance', options.provenance);
  }
  if (options.originType && options.originType !== 'all') {
    params.set('origin_type', options.originType);
  }
  const response = await requestMeal(`/api/foods/?${params.toString()}`, undefined, '');
  const results = (await safeReadJson(response)) || [];
  if (!Array.isArray(results)) throw new Error();
  return results;
};
