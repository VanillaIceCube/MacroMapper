vi.mock('@mui/material', async () => await vi.importActual('@mui/material'));
import { Route, Routes } from 'react-router';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import NotificationsMenu from './NotificationsMenu';
import { renderWithProviders } from '../test-helpers/utils';
import {
  clearAllNotifications,
  clearNotification,
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../services/notificationApiClient';

vi.mock('../services/notificationApiClient', () => ({
  clearAllNotifications: vi.fn(),
  clearNotification: vi.fn(),
  fetchNotifications: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  markNotificationRead: vi.fn(),
}));

const response = (body, ok = true) => ({
  ok,
  json: vi.fn().mockResolvedValue(body),
});

describe('NotificationsMenu', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.unstubAllEnvs();
    sessionStorage.clear();
    fetchNotifications.mockResolvedValue(response([]));
    clearAllNotifications.mockResolvedValue(response({ deleted: 1 }));
    clearNotification.mockResolvedValue(response(null));
    markAllNotificationsRead.mockResolvedValue(response({ updated: 1 }));
    markNotificationRead.mockResolvedValue(
      response({
        id: 1,
        title: 'Welcome to MacroMapper',
        message: 'Your private workspace is ready.',
        is_read: true,
        target_path: '/',
      }),
    );
  });

  test('renders MacroMapper notifications', async () => {
    const user = userEvent.setup();
    sessionStorage.setItem('accessToken', 'access');
    fetchNotifications.mockResolvedValue(
      response([
        {
          id: 1,
          title: 'Welcome to MacroMapper',
          message: 'Your private workspace is ready.',
          is_read: false,
          target_path: '/',
        },
      ]),
    );
    renderWithProviders(<NotificationsMenu />);

    await waitFor(() => expect(fetchNotifications).toHaveBeenCalled());
    await user.click(screen.getByLabelText('notifications'));

    expect(screen.getByText('Welcome to MacroMapper')).toBeInTheDocument();
    expect(screen.getByText('Your private workspace is ready.')).toBeInTheDocument();
    await user.click(screen.getByText('Mark all read'));
    expect(markAllNotificationsRead).toHaveBeenCalledWith();
  });
  test.each(['network', 'malformed'])(
    'retries a failed load without reporting an empty inbox (%s)',
    async (failure) => {
      sessionStorage.setItem('accessToken', 'access');
      if (failure === 'network') fetchNotifications.mockRejectedValueOnce(new Error('offline'));
      else fetchNotifications.mockResolvedValueOnce(response({ invalid: true }));
      fetchNotifications.mockResolvedValueOnce(response([]));
      renderWithProviders(<NotificationsMenu />);
      await userEvent.click(screen.getByLabelText('notifications'));
      expect(
        await screen.findByText('Notifications are unavailable right now.'),
      ).toBeInTheDocument();
      expect(screen.queryByText('No notifications yet.')).not.toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
      expect(await screen.findByText('No notifications yet.')).toBeInTheDocument();
      expect(fetchNotifications).toHaveBeenCalledTimes(2);
    },
  );
  test('keeps failed clear actions visible and allows retry', async () => {
    sessionStorage.setItem('accessToken', 'access');
    fetchNotifications.mockResolvedValue(
      response([{ id: 1, title: 'Parity notice', message: 'Parity message', is_read: false }]),
    );
    clearNotification.mockResolvedValueOnce({ ok: false }).mockResolvedValueOnce({ ok: true });
    renderWithProviders(<NotificationsMenu />);
    await userEvent.click(screen.getByLabelText('notifications'));
    await screen.findByText('Parity notice');
    await userEvent.click(screen.getByLabelText('Clear notification'));
    expect(await screen.findByText('Could not clear that notification.')).toBeInTheDocument();
    expect(screen.getByText('Parity notice')).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText('Clear notification'));
    await waitFor(() => expect(screen.queryByText('Parity notice')).not.toBeInTheDocument());
  });
  test.each(['http', 'json', 'wrong-id'])(
    'keeps unread records and the popover after failed mark-read (%s)',
    async (failure) => {
      sessionStorage.setItem('accessToken', 'access');
      fetchNotifications.mockResolvedValue(
        response([
          {
            id: 1,
            title: 'Parity notice',
            message: 'Parity message',
            is_read: false,
            target_path: '/must-not-navigate',
          },
        ]),
      );
      markNotificationRead.mockResolvedValue(
        failure === 'http'
          ? { ok: false }
          : {
              ok: true,
              json: async () => {
                if (failure === 'json') throw new Error('Invalid JSON');
                return { id: 99, is_read: true };
              },
            },
      );
      renderWithProviders(<NotificationsMenu />);
      await userEvent.click(screen.getByLabelText('notifications'));
      await userEvent.click(await screen.findByText('Parity notice'));
      expect(await screen.findByText('Could not update that notification.')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Mark all read' })).toBeEnabled();
      expect(screen.getByText('Parity notice')).toBeInTheDocument();
    },
  );
  test('blocks item and bulk actions through mark-read response parsing', async () => {
    sessionStorage.setItem('accessToken', 'access');
    const notification = {
      id: 1,
      title: 'Parity notice',
      message: 'Parity message',
      is_read: false,
    };
    fetchNotifications.mockResolvedValue(response([notification]));
    let resolveJson;
    markNotificationRead.mockResolvedValue({
      ok: true,
      json: () =>
        new Promise((resolve) => {
          resolveJson = resolve;
        }),
    });
    renderWithProviders(<NotificationsMenu />);
    await userEvent.click(screen.getByLabelText('notifications'));
    await userEvent.click(await screen.findByText('Parity notice'));
    expect(screen.getByLabelText('Clear notification')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Mark all read' })).toBeDisabled();
    fireEvent.click(screen.getByLabelText('Clear notification'));
    expect(clearNotification).not.toHaveBeenCalled();
    resolveJson({ ...notification, is_read: true });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Clear all' })).toBeEnabled());
  });
  test('blocks item actions while a bulk clear is pending and preserves records on failure', async () => {
    sessionStorage.setItem('accessToken', 'access');
    fetchNotifications.mockResolvedValue(
      response([{ id: 1, title: 'Parity notice', message: 'Parity message', is_read: true }]),
    );
    let resolveClear;
    clearAllNotifications.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveClear = resolve;
      }),
    );
    renderWithProviders(<NotificationsMenu />);
    await userEvent.click(screen.getByLabelText('notifications'));
    await userEvent.click(await screen.findByRole('button', { name: 'Clear all' }));
    expect(screen.getByLabelText('Clear notification')).toBeDisabled();
    resolveClear({ ok: false });
    expect(await screen.findByText('Could not clear notifications.')).toBeInTheDocument();
    expect(screen.getByText('Parity notice')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Clear all' })).toBeEnabled();
  });
});

describe('NotificationsMenu response and navigation', () => {
  const notification = {
    id: 1,
    title: 'Notification title',
    message: 'Notification message',
    is_read: false,
    target_path: '/notification-target',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    sessionStorage.setItem('accessToken', 'access');
  });
  test.each([
    null,
    {},
    'unexpected',
    1,
    ...['title', 'message'].flatMap((field) =>
      [{ text: 'bad' }, ['bad'], 42, true].map((value) => [{ ...notification, [field]: value }]),
    ),
  ])('keeps the menu usable for malformed notification JSON: %j', async (body) => {
    fetchNotifications
      .mockResolvedValueOnce({ ok: true, json: async () => body })
      .mockResolvedValue({ ok: true, json: async () => [notification] });
    const user = userEvent.setup();
    renderWithProviders(<NotificationsMenu />);
    await user.click(screen.getByLabelText('notifications'));
    expect(await screen.findByText('Notifications are unavailable right now.')).toBeVisible();
    expect(screen.getByRole('button', { name: /Retry/i })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: /Retry/i }));
    expect(await screen.findByText(notification.message)).toBeVisible();
    expect(screen.queryByText('Notifications are unavailable right now.')).not.toBeInTheDocument();
  });

  test.each([
    ['title', {}],
    ['message', []],
    ['target_path', {}],
    ['is_read', 'true'],
    ['board_name', {}],
    ['list_name', {}],
  ])(
    'keeps the cached row and prevents navigation after malformed %s in mark-read',
    async (field, value) => {
      fetchNotifications.mockResolvedValue({ ok: true, json: async () => [notification] });
      markNotificationRead
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ ...notification, is_read: true, [field]: value }),
        })
        .mockResolvedValue({ ok: true, json: async () => ({ ...notification, is_read: true }) });
      const user = userEvent.setup();
      renderWithProviders(
        <Routes>
          <Route path="/" element={<NotificationsMenu />} />
          <Route path="/notification-target" element={<h1>Notification destination</h1>} />
        </Routes>,
      );
      await user.click(screen.getByLabelText('notifications'));
      await user.click(await screen.findByText(notification.message));
      expect(await screen.findByText('Could not update that notification.')).toBeVisible();
      expect(screen.getByText(notification.message)).toBeVisible();
      expect(
        screen.queryByRole('heading', { name: 'Notification destination' }),
      ).not.toBeInTheDocument();
      expect(screen.getByLabelText('Clear notification')).toBeEnabled();
      await user.click(screen.getByText(notification.message));
      expect(
        await screen.findByRole('heading', { name: 'Notification destination' }),
      ).toBeVisible();
      expect(markNotificationRead).toHaveBeenCalledTimes(2);
    },
  );
});
