vi.mock('@mui/material', async () => await vi.importActual('@mui/material'));
import { Route, Routes } from 'react-router';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AppHeader from './AppHeader';
import { renderWithProviders } from '../test-helpers/utils';
import { fetchNotifications } from '../services/notificationApiClient';
import { logout } from '../services/requestClient';

vi.mock('../services/notificationApiClient', () => ({ fetchNotifications: vi.fn() }));

vi.mock('../services/requestClient', () => ({
  logout: vi.fn(),
}));

describe('AppHeader', () => {
  test.each(['/', '/cleanup04-check/'])('loads its logo within Vite base %s', (base) => {
    vi.stubEnv('BASE_URL', base);
    renderWithProviders(<AppHeader title="MacroMapper" setDrawerOpen={vi.fn()} />);

    expect(screen.getByAltText('')).toHaveAttribute('src', `${base}macromapper-mark.png`);
  });

  test('supports profile menu keyboard navigation, dismissal, and logout', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AppHeader title="MacroMapper" setDrawerOpen={setDrawerOpen} />);

    await user.click(screen.getByLabelText('user profile'));
    expect(screen.getByRole('menu')).toBeInTheDocument();
    await user.keyboard('{End}');
    expect(screen.getByRole('menuitem', { name: 'Logout' })).toHaveFocus();
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('menu')).not.toBeInTheDocument());
    expect(logout).not.toHaveBeenCalled();

    await user.click(screen.getByLabelText('user profile'));
    await user.keyboard('{End}{Enter}');
    expect(logout).toHaveBeenCalledTimes(1);
  });

  const setDrawerOpen = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.unstubAllEnvs();
    sessionStorage.clear();
    fetchNotifications.mockResolvedValue(Response.json([]));
  });

  test.each(['0', '1'])('shows connected apps only for enabled MCP (%s)', async (enabled) => {
    vi.stubEnv('VITE_MCP_ENABLED', enabled);
    const user = userEvent.setup();
    renderWithProviders(<AppHeader title="MacroMapper" setDrawerOpen={setDrawerOpen} />);
    await user.click(screen.getByLabelText('user profile'));
    if (enabled === '1') {
      await user.click(screen.getByText('Connected Apps'));
      expect(screen.queryByText('Logout')).not.toBeInTheDocument();
    } else {
      expect(screen.queryByText('Connected Apps')).not.toBeInTheDocument();
    }
    vi.unstubAllEnvs();
  });

  test.each(['/login', '/register', '/forgot-password', '/reset-password'])(
    'does not render the header or fetch notifications on %s',
    (route) => {
      sessionStorage.setItem('accessToken', 'access');
      renderWithProviders(<AppHeader title="MacroMapper" setDrawerOpen={setDrawerOpen} />, {
        routeEntries: [route],
      });

      expect(screen.queryByText('MacroMapper')).not.toBeInTheDocument();
      expect(fetchNotifications).not.toHaveBeenCalled();
    },
  );

  test('renders the title and global controls for authenticated pages', async () => {
    sessionStorage.setItem('accessToken', 'access');
    renderWithProviders(<AppHeader title="MacroMapper" setDrawerOpen={setDrawerOpen} />);

    expect(screen.getByText('MacroMapper')).toBeInTheDocument();
    expect(screen.getByLabelText('notifications')).toBeInTheDocument();
    expect(screen.getByLabelText('user profile')).toBeInTheDocument();
    expect(screen.getByLabelText('menu')).toBeInTheDocument();
    await waitFor(() => expect(fetchNotifications).toHaveBeenCalledWith());
  });

  test('opens the navigation drawer', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AppHeader title="MacroMapper" setDrawerOpen={setDrawerOpen} />);

    await user.click(screen.getByLabelText('menu'));

    expect(setDrawerOpen).toHaveBeenCalled();
  });

  test('shows profile details and logs out', async () => {
    const user = userEvent.setup();
    sessionStorage.setItem('username', 'macro-mapper-user');
    sessionStorage.setItem('email', 'macro-mapper-user@example.com');
    renderWithProviders(<AppHeader title="MacroMapper" setDrawerOpen={setDrawerOpen} />);

    await user.click(screen.getByLabelText('user profile'));
    expect(screen.getByText('macro-mapper-user')).toBeInTheDocument();
    expect(screen.getByText('macro-mapper-user@example.com')).toBeInTheDocument();
    await user.click(screen.getByText('Logout'));

    expect(logout).toHaveBeenCalled();
  });
});

describe('AppHeader navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    sessionStorage.setItem('accessToken', 'access');
    fetchNotifications.mockResolvedValue(Response.json([]));
  });
  test.each(['click', 'keyboard'])(
    'Connected Apps supports %s navigation through its real link',
    async (activation) => {
      vi.stubEnv('VITE_MCP_ENABLED', '1');
      const user = userEvent.setup();
      renderWithProviders(
        <Routes>
          <Route path="/" element={<AppHeader title="Application" setDrawerOpen={vi.fn()} />} />
          <Route path="/connections" element={<h1>Connected Apps destination</h1>} />
        </Routes>,
      );
      await user.click(screen.getByLabelText('user profile'));
      const link = screen.getByRole('menuitem', { name: 'Connected Apps' });
      expect(link).toHaveAttribute('href', '/connections');
      if (activation === 'keyboard') {
        await screen.findByRole('menu');
        await user.keyboard('{ArrowDown}');
        expect(link).toHaveFocus();
        await user.keyboard('{Enter}');
      } else await user.click(link);
      expect(
        await screen.findByRole('heading', { name: 'Connected Apps destination' }),
      ).toBeVisible();
    },
  );
  afterEach(() => vi.unstubAllEnvs());
});
