import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AppHeader from './AppHeader';
import { renderWithProviders } from '../test-support/utils';
import {
  clearAllNotifications,
  clearNotification,
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../services/notificationApiClient';
import { logout } from '../services/requestClient';

jest.mock('../services/notificationApiClient', () => ({
  clearAllNotifications: jest.fn(),
  clearNotification: jest.fn(),
  fetchNotifications: jest.fn(),
  markAllNotificationsRead: jest.fn(),
  markNotificationRead: jest.fn(),
}));

jest.mock('../services/requestClient', () => ({
  logout: jest.fn(),
}));

const response = (body, ok = true) => ({
  ok,
  json: jest.fn().mockResolvedValue(body),
});

describe('AppHeader', () => {
  const setDrawerOpen = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    sessionStorage.clear();
    fetchNotifications.mockResolvedValue(response([]));
    clearAllNotifications.mockResolvedValue(response({ deleted: 1 }));
    clearNotification.mockResolvedValue(response(null));
    markAllNotificationsRead.mockResolvedValue(response({ updated: 1 }));
    markNotificationRead.mockResolvedValue(
      response({
        id: 1,
        title: 'Template ready',
        message: 'Your shell is ready.',
        is_read: true,
        target_path: '/',
      }),
    );
  });

  test.each(['/login', '/register', '/forgot-password', '/reset-password'])(
    'does not render on the public route %s',
    (route) => {
      renderWithProviders(<AppHeader title="Full Stack Template" setDrawerOpen={setDrawerOpen} />, {
        routeEntries: [route],
      });

      expect(screen.queryByText('Full Stack Template')).not.toBeInTheDocument();
    },
  );

  test('renders the title and global controls for authenticated pages', async () => {
    sessionStorage.setItem('accessToken', 'access');
    renderWithProviders(<AppHeader title="Full Stack Template" setDrawerOpen={setDrawerOpen} />);

    expect(screen.getByText('Full Stack Template')).toBeInTheDocument();
    expect(screen.getByLabelText('notifications')).toBeInTheDocument();
    expect(screen.getByLabelText('user profile')).toBeInTheDocument();
    expect(screen.getByLabelText('menu')).toBeInTheDocument();
    await waitFor(() => expect(fetchNotifications).toHaveBeenCalledWith('access'));
  });

  test('opens the navigation drawer', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AppHeader title="Full Stack Template" setDrawerOpen={setDrawerOpen} />);

    await user.click(screen.getByLabelText('menu'));

    expect(setDrawerOpen).toHaveBeenCalled();
  });

  test('shows profile details and logs out', async () => {
    const user = userEvent.setup();
    sessionStorage.setItem('username', 'template-user');
    sessionStorage.setItem('email', 'template@example.com');
    renderWithProviders(<AppHeader title="Full Stack Template" setDrawerOpen={setDrawerOpen} />);

    await user.click(screen.getByLabelText('user profile'));
    expect(screen.getByText('template-user')).toBeInTheDocument();
    expect(screen.getByText('template@example.com')).toBeInTheDocument();
    await user.click(screen.getByText('Logout'));

    expect(logout).toHaveBeenCalled();
  });

  test('renders generic notifications without workspace context', async () => {
    const user = userEvent.setup();
    sessionStorage.setItem('accessToken', 'access');
    fetchNotifications.mockResolvedValue(
      response([
        {
          id: 1,
          title: 'Template ready',
          message: 'Your shell is ready.',
          is_read: false,
          target_path: '/',
        },
      ]),
    );
    renderWithProviders(<AppHeader title="Full Stack Template" setDrawerOpen={setDrawerOpen} />);

    await waitFor(() => expect(fetchNotifications).toHaveBeenCalled());
    await user.click(screen.getByLabelText('notifications'));

    expect(screen.getByText('Template ready')).toBeInTheDocument();
    expect(screen.getByText('Your shell is ready.')).toBeInTheDocument();
    await user.click(screen.getByText('Mark all read'));
    expect(markAllNotificationsRead).toHaveBeenCalledWith('access');
  });
});
