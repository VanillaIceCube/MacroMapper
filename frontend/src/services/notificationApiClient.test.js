import { apiFetch } from './requestClient';
import {
  clearAllNotifications,
  clearNotification,
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from './notificationApiClient';

jest.mock('./requestClient', () => ({
  apiFetch: jest.fn(),
}));

describe('notificationApiClient', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('lists notifications with authentication', () => {
    fetchNotifications('TOKEN');

    expect(apiFetch).toHaveBeenCalledWith('/api/notifications/', {
      headers: { Authorization: 'Bearer TOKEN' },
    });
  });

  test('marks one notification read', () => {
    markNotificationRead(42, 'TOKEN');

    expect(apiFetch).toHaveBeenCalledWith('/api/notifications/42/', {
      method: 'PATCH',
      headers: {
        Authorization: 'Bearer TOKEN',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ is_read: true }),
    });
  });

  test('clears one or all notifications', () => {
    clearNotification(42, 'TOKEN');
    clearAllNotifications('TOKEN');

    expect(apiFetch).toHaveBeenNthCalledWith(1, '/api/notifications/42/', {
      method: 'DELETE',
      headers: {
        Authorization: 'Bearer TOKEN',
        'Content-Type': 'application/json',
      },
    });
    expect(apiFetch).toHaveBeenNthCalledWith(2, '/api/notifications/clear-all/', {
      method: 'DELETE',
      headers: {
        Authorization: 'Bearer TOKEN',
        'Content-Type': 'application/json',
      },
    });
  });

  test('marks all notifications read', () => {
    markAllNotificationsRead('TOKEN');

    expect(apiFetch).toHaveBeenCalledWith('/api/notifications/mark-all-read/', {
      method: 'PATCH',
      headers: {
        Authorization: 'Bearer TOKEN',
        'Content-Type': 'application/json',
      },
    });
  });
});
