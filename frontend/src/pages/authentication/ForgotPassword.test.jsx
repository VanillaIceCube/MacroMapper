import { Route, Routes } from 'react-router';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { forgotPassword } from '../../services/authApiClient';
import { renderWithProviders } from '../../test-helpers/utils';
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
  describe.each([{ name: 'Back to Login', to: '/login', tabs: 3 }])(
    'navigation to $to ($name)',
    ({ name, to, tabs }) => {
      test.each(['click', 'keyboard'])(
        '%s follows a real link without submitting',
        async (activation) => {
          vi.clearAllMocks();
          sessionStorage.clear();
          const user = userEvent.setup();
          const showSnackbar = vi.fn();
          renderWithProviders(
            <Routes>
              <Route
                path="/forgot-password"
                element={<ForgotPassword showSnackbar={showSnackbar} />}
              />
              <Route path={to} element={<h1>Navigation destination</h1>} />
            </Routes>,
            { routeEntries: ['/forgot-password'] },
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
          expect(forgotPassword).not.toHaveBeenCalled();
          expect(showSnackbar).not.toHaveBeenCalled();
        },
      );
    },
  );
});
