import { apiFetch } from '../http/requestClient';
import { readOkJson } from '../http/apiResponse';

async function postAuthForm(path, payload, invalidResponseMessage) {
  const response = await apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return readOkJson(response, invalidResponseMessage);
}

export const login = ({ email, password }) =>
  postAuthForm('/auth/login/', { email: email?.trim(), password }, 'Login failed.');

export const register = ({ email, username, password }) => {
  const payload = { email: email?.trim(), password };
  const trimmedUsername = username?.trim();
  if (trimmedUsername) payload.username = trimmedUsername;

  return postAuthForm('/auth/register/', payload, 'Registration failed.');
};

export const forgotPassword = ({ email }) =>
  postAuthForm(
    '/auth/forgot-password/',
    { email: email?.trim() },
    'Password reset request failed.',
  );

export const resetPassword = ({ uid, token, password }) =>
  postAuthForm('/auth/reset-password/', { uid, token, password }, 'Password reset failed.');
