import { Route, Routes } from 'react-router';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { register } from '../../services/authApiClient';
import { renderWithProviders } from '../../test-helpers/utils';
import Register from './Register';

vi.mock('../../services/authApiClient', () => ({
  register: vi.fn(),
}));

describe('Register', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  test('creates an account and stores the session', async () => {
    const showSnackbar = vi.fn();
    register.mockResolvedValue({
      access: 'access-token',
      refresh: 'refresh-token',
      username: 'mapper',
      email: 'mapper@example.com',
    });
    renderWithProviders(<Register showSnackbar={showSnackbar} />, {
      routeEntries: ['/register'],
    });

    await userEvent.type(screen.getByLabelText('Email'), 'mapper@example.com');
    await userEvent.type(screen.getByLabelText('Username (optional)'), 'mapper');
    await userEvent.type(screen.getByLabelText('Password'), 'secret');
    await userEvent.type(screen.getByLabelText('Confirm Password'), 'secret');
    await userEvent.click(screen.getByRole('button', { name: 'Register' }));

    await waitFor(() => expect(sessionStorage.getItem('accessToken')).toBe('access-token'));
    expect(register).toHaveBeenCalledWith({
      email: 'mapper@example.com',
      username: 'mapper',
      password: 'secret',
    });
  });

  test('rejects mismatched passwords locally', async () => {
    const showSnackbar = vi.fn();
    renderWithProviders(<Register showSnackbar={showSnackbar} />, {
      routeEntries: ['/register'],
    });

    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'one' } });
    fireEvent.change(screen.getByLabelText('Confirm Password'), { target: { value: 'two' } });
    await userEvent.click(screen.getByRole('button', { name: 'Register' }));

    expect(register).not.toHaveBeenCalled();
    expect(showSnackbar).toHaveBeenCalledWith('error', 'Passwords do not match.');
  });
  test('blocks duplicate submissions and recovers after a validation failure', async () => {
    const showSnackbar = vi.fn();
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    let rejectRequest;
    register.mockReturnValueOnce(
      new Promise((_resolve, reject) => {
        rejectRequest = reject;
      }),
    );
    renderWithProviders(<Register showSnackbar={showSnackbar} />, { routeEntries: ['/register'] });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'mapper@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret' } });
    fireEvent.change(screen.getByLabelText('Confirm Password'), { target: { value: 'secret' } });
    await userEvent.click(screen.getByRole('button', { name: 'Register' }));
    const pendingButton = screen.getByRole('button', { name: 'Registering...' });
    expect(pendingButton).toBeDisabled();
    fireEvent.click(pendingButton);
    expect(register).toHaveBeenCalledTimes(1);
    rejectRequest(new Error('Validation failed.'));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Register' })).toBeEnabled());
    expect(showSnackbar).toHaveBeenCalledWith('error', 'Validation failed.');
    consoleError.mockRestore();
  });
  describe.each([{ name: 'Sign in', to: '/login', tabs: 6 }])(
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
              <Route path="/register" element={<Register showSnackbar={showSnackbar} />} />
              <Route path={to} element={<h1>Navigation destination</h1>} />
            </Routes>,
            { routeEntries: ['/register'] },
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
          expect(register).not.toHaveBeenCalled();
          expect(showSnackbar).not.toHaveBeenCalled();
        },
      );
    },
  );
});
