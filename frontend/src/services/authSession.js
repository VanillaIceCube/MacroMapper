import { startSession } from './sessionState';

export async function safeReadJson(response) {
  try {
    return await response.json();
  } catch (_err) {
    return null;
  }
}

function extractErrorMessage(data) {
  if (!data) return null;

  if (typeof data === 'string') return data;

  if (Array.isArray(data) && data.length > 0) {
    return extractErrorMessage(data[0]);
  }

  if (typeof data === 'object') {
    if (data.error) {
      const msg = extractErrorMessage(data.error);
      if (msg) return msg;
    }
    if (data.detail) {
      const msg = extractErrorMessage(data.detail);
      if (msg) return msg;
    }
    const firstValue = Object.values(data)[0];
    if (firstValue !== undefined) {
      const msg = extractErrorMessage(firstValue);
      if (msg) return msg;
    }
  }

  return null;
}

export async function getResponseErrorMessage(response, fallbackMessage) {
  const data = await safeReadJson(response);
  const message = extractErrorMessage(data);
  return message || fallbackMessage;
}

export async function readOkJson(response, fallbackMessage) {
  if (!response?.ok) {
    const message = await getResponseErrorMessage(response, `HTTP ${response?.status ?? 'error'}`);
    throw new Error(message);
  }

  const data = await safeReadJson(response);
  if (!data) {
    throw new Error(fallbackMessage);
  }
  return data;
}

export function formatAuthErrorMessage(error, fallbackMessage = 'An unexpected error occurred.') {
  const isNetworkError =
    error instanceof TypeError || error?.message?.toLowerCase().includes('network');
  if (isNetworkError) {
    return 'Network error.';
  }
  return error?.message || fallbackMessage;
}

export function persistAuthSession(data) {
  startSession(data);
}
