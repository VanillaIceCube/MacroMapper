import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { resetPassword } from '../../services/authApiClient';
import { renderWithProviders } from '../../test-support/utils';
import ResetPassword from './ResetPassword';

vi.mock('../../services/authApiClient', () => ({
  resetPassword: vi.fn(),
}));

describe('ResetPassword', () => {
  test('submits a valid reset link and matching passwords', async () => {
    const showSnackbar = vi.fn();
    resetPassword.mockResolvedValue({
      ok: true,
      json: async () => ({ message: 'Password reset successful.' }),
    });
    renderWithProviders(<ResetPassword showSnackbar={showSnackbar} />, {
      routeEntries: ['/reset-password?uid=user-id&token=reset-token'],
    });

    await userEvent.type(screen.getByLabelText('New Password'), 'new-secret');
    await userEvent.type(screen.getByLabelText('Confirm Password'), 'new-secret');
    await userEvent.click(screen.getByRole('button', { name: 'Reset Password' }));

    await waitFor(() =>
      expect(resetPassword).toHaveBeenCalledWith({
        uid: 'user-id',
        token: 'reset-token',
        password: 'new-secret',
      }),
    );
  });

  test('rejects a reset page without link credentials', async () => {
    const showSnackbar = vi.fn();
    renderWithProviders(<ResetPassword showSnackbar={showSnackbar} />, {
      routeEntries: ['/reset-password'],
    });

    fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'new-secret' } });
    fireEvent.change(screen.getByLabelText('Confirm Password'), {
      target: { value: 'new-secret' },
    });
    await userEvent.click(screen.getByRole('button', { name: 'Reset Password' }));

    expect(resetPassword).not.toHaveBeenCalled();
    expect(showSnackbar).toHaveBeenCalledWith('error', 'Invalid or expired reset link.');
  });
  test('blocks duplicate submissions and recovers after a validation failure', async () => {
    const showSnackbar = vi.fn();
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    let resolveRequest;
    resetPassword.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveRequest = resolve;
      }),
    );
    renderWithProviders(<ResetPassword showSnackbar={showSnackbar} />, {
      routeEntries: ['/reset-password?uid=test-user&token=test-token'],
    });
    fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'new-secret' } });
    fireEvent.change(screen.getByLabelText('Confirm Password'), {
      target: { value: 'new-secret' },
    });
    await userEvent.click(screen.getByRole('button', { name: 'Reset Password' }));
    const pendingButton = screen.getByRole('button', { name: 'Resetting...' });
    expect(pendingButton).toBeDisabled();
    fireEvent.click(pendingButton);
    expect(resetPassword).toHaveBeenCalledTimes(1);
    resolveRequest({
      ok: false,
      status: 400,
      json: async () => ({ password: ['Validation failed.'] }),
    });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Reset Password' })).toBeEnabled(),
    );
    expect(showSnackbar).toHaveBeenCalledWith('error', 'Validation failed.');
    consoleError.mockRestore();
  });
});
