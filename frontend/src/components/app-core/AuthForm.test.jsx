import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AuthForm, { AuthLink } from './AuthForm';
import { renderWithProviders } from '../../test-helpers/utils';

describe('AuthForm', () => {
  test.each(['/', '/cleanup04-check/'])('loads its logo within Vite base %s', (base) => {
    vi.stubEnv('BASE_URL', base);
    renderWithProviders(<AuthForm title="Sign in" submitLabel="Sign in" />);

    expect(screen.getByAltText('')).toHaveAttribute('src', `${base}macromapper-mark.png`);
  });

  test('presents the page title as the main heading and renders its content', () => {
    renderWithProviders(
      <AuthForm title="Recover access" submitLabel="Send reset link">
        <p>Enter your email to receive a reset link.</p>
      </AuthForm>,
    );

    expect(screen.getByRole('heading', { level: 1, name: 'Recover access' })).toBeVisible();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.getByRole('heading', { name: 'MacroMapper' })).toBeVisible();
    expect(screen.getByText('Enter your email to receive a reset link.')).toBeVisible();
  });

  test('supports native keyboard submit and links to other auth pages', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithProviders(
      <AuthForm
        title="Recover access"
        onSubmit={onSubmit}
        submitLabel="Send reset link"
        footer={<AuthLink to="/login">Back to Login</AuthLink>}
      >
        <label htmlFor="recovery-email">Email</label>
        <input id="recovery-email" name="email" type="email" required />
      </AuthForm>,
    );

    expect(screen.getByRole('form', { name: 'Recover access' })).toBeVisible();
    expect(screen.getByRole('link', { name: 'Back to Login' })).toHaveAttribute('href', '/login');
    await user.tab();
    expect(screen.getByRole('textbox', { name: 'Email' })).toHaveFocus();
    await user.keyboard('reader@example.com{Enter}');

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('textbox', { name: 'Email' })).toHaveValue('reader@example.com');
    expect(screen.getByRole('button', { name: 'Send reset link' })).toBeEnabled();
  });
});
