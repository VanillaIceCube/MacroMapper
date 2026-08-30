import { render, screen } from '@testing-library/react';
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
    expect(screen.getByRole('heading', { name: 'Meal Log', level: 1 })).toBeInTheDocument();
    expect(screen.getByLabelText('notifications')).toBeInTheDocument();
    expect(screen.getByLabelText('user profile')).toBeInTheDocument();
    expect(screen.getByLabelText('menu')).toBeInTheDocument();
  });

  test('navigates between authentication routes through the browser router', async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, '', '/login');
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Create Account' }));

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
