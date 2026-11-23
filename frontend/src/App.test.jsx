import { act, fireEvent, render, screen } from '@testing-library/react';
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

  async function submitPendingAuthRequest(page) {
    const pending = Promise.withResolvers();
    const defaultFetch = fetch.getMockImplementation();
    fetch.mockImplementation((url, options) =>
      url.endsWith('/auth/' + page + '/') ? pending.promise : defaultFetch(url, options),
    );
    const query = page === 'reset-password' ? '?uid=user&token=reset' : '';
    window.history.replaceState({}, '', '/' + page + query);
    render(<SessionApp />);
    const form = await screen.findByRole('form');
    for (const label of ['Email', 'Password', 'Confirm Password', 'New Password']) {
      const input = screen.queryByLabelText(label, { exact: true });
      if (input)
        fireEvent.change(input, {
          target: { value: label === 'Email' ? credentials.email : 'password123' },
        });
    }
    fireEvent.submit(form);
    expect(fetch.mock.calls.some(([url]) => url.endsWith('/auth/' + page + '/'))).toBe(true);
    return pending;
  }

  describe.each(['login', 'register', 'forgot-password', 'reset-password'])(
    '%s request lifecycle',
    (page) => {
      test.each(['success', 'failure'])(
        'ignores a late %s after leaving the form',
        async (outcome) => {
          const pending = await submitPendingAuthRequest(page);
          const destination = page === 'login' ? '/register' : '/login';
          await userEvent.click(
            screen.getByRole('link', {
              name: page === 'login' ? /create account/i : /sign in|login|log in/i,
            }),
          );
          expect(window.location.pathname).toBe(destination);
          await act(async () => {
            if (outcome === 'success') pending.resolve(reply(credentials));
            else pending.reject(new Error('Abandoned request'));
          });
          expect(window.location.pathname).toBe(destination);
          expect(sessionStorage.getItem('accessToken')).toBeNull();
          expect(screen.queryByRole('alert')).not.toBeInTheDocument();
        },
      );
    },
  );

  test('a late login response cannot replace the new account', async () => {
    const pending = await submitPendingAuthRequest('login');
    const { startSession } = await import('./services/sessionState');
    act(() => startSession({ access: 'new-access', refresh: 'new-refresh' }));
    await act(async () => pending.resolve(reply(credentials)));
    expect(sessionStorage.getItem('accessToken')).toBe('new-access');
    expect(window.location.pathname).toBe('/login');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  test.each(['login', 'register'])(
    '%s reports a current request’s storage failure',
    async (page) => {
      const pending = await submitPendingAuthRequest(page);
      vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new Error('Storage unavailable');
      });
      await act(async () => pending.resolve(reply(credentials)));
      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Unable to access browser session storage.',
      );
      expect(sessionStorage.getItem('accessToken')).toBeNull();
      expect(window.location.pathname).toBe('/' + page);
    },
  );

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

  test('disabled MCP redirects old connection links without fetching consent', async () => {
    vi.stubEnv('VITE_MCP_ENABLED', '0');
    window.history.replaceState({}, '', '/connections/authorize?client_id=reader');
    render(<SessionApp />);
    expect(await screen.findByRole('heading', { name: 'Login' })).toBeVisible();
    expect(screen.queryByText('Connect this application')).not.toBeInTheDocument();
    expect(fetch.mock.calls.some(([url]) => url.includes('/auth/mcp/'))).toBe(false);
    expect(window.location.pathname).toBe('/login');
    expect(new URLSearchParams(window.location.search).get('next') || '').not.toContain(
      '/connections',
    );
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
