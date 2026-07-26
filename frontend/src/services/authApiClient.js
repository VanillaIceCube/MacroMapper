import { apiFetch } from './requestClient';

const jsonHeaders = { 'Content-Type': 'application/json' };

export const login = ({ email, password }) =>
  apiFetch('/auth/login/', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ email: email?.trim(), password }),
  });

export const register = ({ email, username, password }) => {
  const payload = { email: email?.trim(), password };
  const trimmedUsername = username?.trim();
  if (trimmedUsername) {
    payload.username = trimmedUsername;
  }

  return apiFetch('/auth/register/', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
};

export const forgotPassword = ({ email }) =>
  apiFetch('/auth/forgot-password/', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ email: email?.trim() }),
  });

export const resetPassword = ({ uid, token, password }) =>
  apiFetch('/auth/reset-password/', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ uid, token, password }),
  });
