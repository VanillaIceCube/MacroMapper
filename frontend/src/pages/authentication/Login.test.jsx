import { Route, Routes } from 'react-router';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { login } from '../../services/authApiClient';
import { renderWithProviders } from '../../test-helpers/utils';
import Login from './Login';

vi.mock('../../services/authApiClient', () => ({
  login: vi.fn(),
}));

describe('Login', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  test('logs in and stores the returned session', async () => {
    const showSnackbar = vi.fn();
    login.mockResolvedValue({
      access: 'access-token',
      refresh: 'refresh-token',
      username: 'mapper',
      email: 'mapper@example.com',
    });
    renderWithProviders(<Login showSnackbar={showSnackbar} />, { routeEntries: ['/login'] });

    await userEvent.type(screen.getByLabelText('Email'), 'mapper@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'secret');
    await userEvent.click(screen.getByRole('button', { name: 'Login' }));

    await waitFor(() => expect(sessionStorage.getItem('accessToken')).toBe('access-token'));
    expect(login).toHaveBeenCalledWith({ email: 'mapper@example.com', password: 'secret' });
    expect(showSnackbar).toHaveBeenCalledWith('success', 'Welcome mapper!');
  });

  test('shows a pending session-expired message', () => {
    const showSnackbar = vi.fn();
    sessionStorage.setItem(
      'pendingSnackbar',
      JSON.stringify({ severity: 'error', message: 'Please sign in again.' }),
    );

    renderWithProviders(<Login showSnackbar={showSnackbar} />, { routeEntries: ['/login'] });

    expect(showSnackbar).toHaveBeenCalledWith('error', 'Please sign in again.');
    expect(sessionStorage.getItem('pendingSnackbar')).toBeNull();
  });

  test('centers the authentication brand and login card', () => {
    renderWithProviders(<Login showSnackbar={vi.fn()} />, { routeEntries: ['/login'] });

    const brand = screen.getByRole('heading', { name: 'MacroMapper' }).parentElement;
    const shell = brand.parentElement;

    expect(brand).toHaveStyle({ alignItems: 'center' });
    expect(shell).toHaveStyle({ alignItems: 'center' });
  });
  test('blocks duplicate submissions and recovers after a validation failure', async () => {
    const showSnackbar = vi.fn();
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    let rejectRequest;
    login.mockReturnValueOnce(
      new Promise((_resolve, reject) => {
        rejectRequest = reject;
      }),
    );
    renderWithProviders(<Login showSnackbar={showSnackbar} />, { routeEntries: ['/login'] });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'mapper@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret' } });
    await userEvent.click(screen.getByRole('button', { name: 'Login' }));
    const pendingButton = screen.getByRole('button', { name: 'Logging in...' });
    expect(pendingButton).toBeDisabled();
    fireEvent.click(pendingButton);
    expect(login).toHaveBeenCalledTimes(1);
    rejectRequest(new Error('Validation failed.'));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Login' })).toBeEnabled());
    expect(showSnackbar).toHaveBeenCalledWith('error', 'Validation failed.');
    consoleError.mockRestore();
  });
  describe.each([
    { name: 'Forgot Password?', to: '/forgot-password', tabs: 4 },
    { name: 'Create Account', to: '/register', tabs: 5 },
  ])('navigation to $to ($name)', ({ name, to, tabs }) => {
    test.each(['click', 'keyboard'])(
      '%s follows a real link without submitting',
      async (activation) => {
        vi.clearAllMocks();
        sessionStorage.clear();
        const user = userEvent.setup();
        const showSnackbar = vi.fn();
        renderWithProviders(
          <Routes>
            <Route path="/login" element={<Login showSnackbar={showSnackbar} />} />
            <Route path={to} element={<h1>Navigation destination</h1>} />
          </Routes>,
          { routeEntries: ['/login'] },
        );
        const link = screen.getByRole('link', { name, exact: true });
        expect(link).toHaveAttribute('href', to);
        if (activation === 'keyboard') {
          for (let i = 0; i < tabs; i += 1) await user.tab();
          expect(link).toHaveFocus();
          await user.keyboard('{Enter}');
        } else {
          await user.click(link);
        }
        expect(
          await screen.findByRole('heading', { name: 'Navigation destination' }),
        ).toBeVisible();
        expect(login).not.toHaveBeenCalled();
        expect(showSnackbar).not.toHaveBeenCalled();
      },
    );
  });
});
