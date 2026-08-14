import { apiFetch } from './requestClient';

const authHeader = (token) => ({ Authorization: `Bearer ${token}` });
const jsonHeaders = (token) => ({
  ...authHeader(token),
  'Content-Type': 'application/json',
});

export const fetchNotifications = (token) =>
  apiFetch('/api/notifications/', {
    headers: authHeader(token),
  });

export const markNotificationRead = (notificationId, token) =>
  apiFetch(`/api/notifications/${notificationId}/`, {
    method: 'PATCH',
    headers: jsonHeaders(token),
    body: JSON.stringify({ is_read: true }),
  });

export const clearNotification = (notificationId, token) =>
  apiFetch(`/api/notifications/${notificationId}/`, {
    method: 'DELETE',
    headers: jsonHeaders(token),
  });

export const clearAllNotifications = (token) =>
  apiFetch('/api/notifications/clear-all/', {
    method: 'DELETE',
    headers: jsonHeaders(token),
  });

export const markAllNotificationsRead = (token) =>
  apiFetch('/api/notifications/mark-all-read/', {
    method: 'PATCH',
    headers: jsonHeaders(token),
  });
