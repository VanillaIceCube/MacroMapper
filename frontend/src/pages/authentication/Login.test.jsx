import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { login } from '../../services/authApiClient';
import { renderWithProviders } from '../../test-support/utils';
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
      ok: true,
      json: async () => ({
        access: 'access-token',
        refresh: 'refresh-token',
        username: 'mapper',
        email: 'mapper@example.com',
      }),
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
    let resolveRequest;
    login.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveRequest = resolve;
      }),
    );
    renderWithProviders(<Login showSnackbar={showSnackbar} />, { routeEntries: ['/login'] });
    await userEvent.type(screen.getByLabelText('Email'), 'mapper@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'secret');
    await userEvent.click(screen.getByRole('button', { name: 'Login' }));
    const pendingButton = screen.getByRole('button', { name: 'Logging in...' });
    expect(pendingButton).toBeDisabled();
    fireEvent.click(pendingButton);
    expect(login).toHaveBeenCalledTimes(1);
    resolveRequest({
      ok: false,
      status: 400,
      json: async () => ({ password: ['Validation failed.'] }),
    });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Login' })).toBeEnabled());
    expect(showSnackbar).toHaveBeenCalledWith('error', 'Validation failed.');
    consoleError.mockRestore();
  });
});
