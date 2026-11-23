import { apiFetch } from './requestClient';
import {
  clearAllNotifications,
  clearNotification,
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from './notificationApiClient';

vi.mock('./requestClient', () => ({
  apiFetch: vi.fn(),
}));

describe('notificationApiClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('lists notifications through the request client', () => {
    fetchNotifications();

    expect(apiFetch).toHaveBeenCalledWith('/api/notifications/');
  });

  test('marks one notification read', () => {
    markNotificationRead(42);

    expect(apiFetch).toHaveBeenCalledWith('/api/notifications/42/', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ is_read: true }),
    });
  });

  test('clears one or all notifications', () => {
    clearNotification(42);
    clearAllNotifications();

    expect(apiFetch).toHaveBeenNthCalledWith(1, '/api/notifications/42/', {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    expect(apiFetch).toHaveBeenNthCalledWith(2, '/api/notifications/clear-all/', {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
    });
  });

  test('marks all notifications read', () => {
    markAllNotificationsRead();

    expect(apiFetch).toHaveBeenCalledWith('/api/notifications/mark-all-read/', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
    });
  });
});
