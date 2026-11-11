import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { forgotPassword } from '../../services/authApiClient';
import { renderWithProviders } from '../../test-support/utils';
import ForgotPassword from './ForgotPassword';

vi.mock('../../services/authApiClient', () => ({
  forgotPassword: vi.fn(),
}));

describe('ForgotPassword', () => {
  test('requests a password reset', async () => {
    const showSnackbar = vi.fn();
    forgotPassword.mockResolvedValue({
      ok: true,
      json: async () => ({ message: 'Password reset link has been sent!' }),
    });
    renderWithProviders(<ForgotPassword showSnackbar={showSnackbar} />, {
      routeEntries: ['/forgot-password'],
    });

    await userEvent.type(screen.getByLabelText('Email'), 'mapper@example.com');
    await userEvent.click(screen.getByRole('button', { name: 'Send Reset Link' }));

    await waitFor(() =>
      expect(showSnackbar).toHaveBeenCalledWith('success', 'Password reset link has been sent!'),
    );
    expect(forgotPassword).toHaveBeenCalledWith({ email: 'mapper@example.com' });
  });
  test('blocks duplicate submissions and recovers after a validation failure', async () => {
    const showSnackbar = vi.fn();
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    let resolveRequest;
    forgotPassword.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveRequest = resolve;
      }),
    );
    renderWithProviders(<ForgotPassword showSnackbar={showSnackbar} />, {
      routeEntries: ['/forgot-password'],
    });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'mapper@example.com' } });
    await userEvent.click(screen.getByRole('button', { name: 'Send Reset Link' }));
    const pendingButton = screen.getByRole('button', { name: 'Sending...' });
    expect(pendingButton).toBeDisabled();
    fireEvent.click(pendingButton);
    expect(forgotPassword).toHaveBeenCalledTimes(1);
    resolveRequest({
      ok: false,
      status: 400,
      json: async () => ({ password: ['Validation failed.'] }),
    });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Send Reset Link' })).toBeEnabled(),
    );
    expect(showSnackbar).toHaveBeenCalledWith('error', 'Validation failed.');
    consoleError.mockRestore();
  });
});
