import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';

describe('App', () => {
  beforeEach(() => {
    sessionStorage.clear();
    window.history.replaceState({}, '', '/');
    vi.spyOn(global, 'fetch').mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify({ meals: [], totals: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('redirects signed-out users to login', async () => {
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Login' })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/login');
  });

  test('shows the protected application shell and meal diary to signed-in users at /', async () => {
    sessionStorage.setItem('accessToken', 'token');
    render(<App />);

    expect(await screen.findByText('MacroMapper')).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'Meal Log', level: 1 })).toBeInTheDocument();
    expect(screen.getByLabelText('notifications')).toBeInTheDocument();
    expect(screen.getByLabelText('user profile')).toBeInTheDocument();
    expect(screen.getByLabelText('menu')).toBeInTheDocument();

    const dateNav = screen.getByRole('navigation', { name: 'diary date navigation' });
    expect(dateNav).toBeInTheDocument();
  });

  test('navigates between authentication routes through the browser router', async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, '', '/login');
    render(<App />);

    await user.click(await screen.findByRole('link', { name: 'Create Account' }));

    expect(await screen.findByRole('heading', { name: 'Create account' })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/register');
  });

  test('redirects an unknown route to the protected meal diary page', async () => {
    sessionStorage.setItem('accessToken', 'token');
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key) =>
      key === 'accessToken' ? 'token' : null,
    );
    window.history.replaceState({}, '', '/not-a-macromapper-route');
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Meal Log', level: 1 })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/');
  });
});

describe('real session route lifecycle', () => {
  const SessionApp = App;

  const reply = (body, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  const credentials = {
    access: 'access',
    refresh: 'refresh',
    username: 'Reader',
    email: 'reader@example.com',
  };
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    vi.stubEnv('VITE_MCP_ENABLED', '1');
    window.history.replaceState({}, '', '/login');
    vi.stubGlobal(
      'fetch',
      vi.fn((url) => {
        if (url.includes('/auth/login/') || url.includes('/auth/register/'))
          return Promise.resolve(reply(credentials));
        if (url.includes('/auth/mcp/authorize/'))
          return Promise.resolve(
            reply({
              ticket: 'ticket',
              application: { name: 'Reader app', client_id: 'client' },
              user: { username: 'Reader' },
              permissions: [],
            }),
          );
        if (url.includes('/api/expired/')) return Promise.resolve(reply({}, 401));
        if (url.includes('/diary/')) return Promise.resolve(reply({ meals: [], totals: [] }));
        return Promise.resolve(reply([]));
      }),
    );
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  test.each(['login', 'register'])(
    'keeps the real %s success message across the session transition',
    async (page) => {
      window.history.replaceState({}, '', `/${page}`);
      render(<SessionApp />);
      const user = userEvent.setup();
      await user.type(await screen.findByRole('textbox', { name: 'Email' }), 'reader@example.com');
      await user.type(screen.getByLabelText('Password', { exact: true }), 'password123');
      if (page === 'register') {
        await user.type(screen.getByRole('textbox', { name: /Username/ }), 'Reader');
        await user.type(screen.getByLabelText('Confirm Password'), 'password123');
      }
      await user.click(
        screen.getByRole('button', {
          name: page === 'login' ? /^Login$/i : /^(Register|Create account)$/i,
        }),
      );
      expect(
        await screen.findByText(
          page === 'login' ? 'Welcome Reader!' : /Account created! Welcome to/,
        ),
      ).toBeVisible();
      expect(await screen.findByLabelText('user profile')).toBeVisible();
      expect(sessionStorage.getItem('accessToken')).toBe('access');
    },
  );

  test('shows the queued logout message after the session shell and lazy Login change', async () => {
    const { startSession } = await import('./services/sessionState');
    startSession(credentials);
    window.history.replaceState({}, '', '/');
    render(<SessionApp />);
    const user = userEvent.setup();
    await user.click(await screen.findByLabelText('user profile'));
    await user.click(screen.getByText('Logout'));
    expect(await screen.findByRole('heading', { name: 'Login' })).toBeVisible();
    expect(await screen.findByText('Logout Successful :)')).toBeVisible();
    expect(sessionStorage.getItem('pendingSnackbar')).toBeNull();
  });

  test('shows expiry feedback after a reactive guard redirects to lazy Login', async () => {
    sessionStorage.setItem('accessToken', 'expired');
    window.history.replaceState({}, '', '/');
    render(<SessionApp />);
    expect(await screen.findByLabelText('user profile')).toBeVisible();
    const { apiFetch } = await import('./services/requestClient');
    await act(() => apiFetch('/api/expired/'));
    expect(await screen.findByRole('heading', { name: 'Login' })).toBeVisible();
    expect(await screen.findByText('Your session expired. Please log in again.')).toBeVisible();
  });

  test('retains the complete consent query through lazy login and account publication', async () => {
    const pending = '/connections/authorize?state=keep%26this&client_id=reader';
    window.history.replaceState({}, '', pending);
    render(<SessionApp />);
    const user = userEvent.setup();
    await user.type(await screen.findByRole('textbox', { name: 'Email' }), 'reader@example.com');
    expect(new URLSearchParams(window.location.search).get('next')).toBe(pending);
    await user.type(screen.getByLabelText('Password', { exact: true }), 'password123');
    await user.click(screen.getByRole('button', { name: 'Login' }));
    expect(await screen.findByText('Connect this application')).toBeVisible();
    expect(`${window.location.pathname}${window.location.search}`).toBe(pending);
    expect(await screen.findByText('Signed in as Reader')).toBeVisible();
  });

  test('account replacement closes account menus and presents only the current profile', async () => {
    const { startSession } = await import('./services/sessionState');
    startSession(credentials);
    window.history.replaceState({}, '', '/');
    render(<SessionApp />);
    const user = userEvent.setup();
    await user.click(await screen.findByLabelText('user profile'));
    expect(screen.getByText('reader@example.com')).toBeVisible();
    act(() =>
      startSession({
        access: 'next',
        refresh: 'next-r',
        username: 'Next',
        email: 'next@example.com',
      }),
    );
    expect(screen.queryByText('reader@example.com')).not.toBeInTheDocument();
    await user.click(screen.getByLabelText('user profile'));
    expect(screen.getByText('next@example.com')).toBeVisible();
  });
});
