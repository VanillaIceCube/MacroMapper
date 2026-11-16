import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AuthPageShell from './AuthPageShell';
import { renderWithProviders } from '../test-helpers/utils';

describe('AuthPageShell', () => {
  test.each(['/', '/cleanup04-check/'])('loads its logo within Vite base %s', (base) => {
    vi.stubEnv('BASE_URL', base);
    renderWithProviders(
      <AuthPageShell title="Sign in">
        <p>Account access</p>
      </AuthPageShell>,
    );

    expect(screen.getByAltText('')).toHaveAttribute('src', `${base}macromapper-mark.png`);
  });

  test('presents the page title as the main heading and renders its content', () => {
    renderWithProviders(
      <AuthPageShell title="Recover access">
        <p>Enter your email to receive a reset link.</p>
      </AuthPageShell>,
    );

    expect(screen.getByRole('heading', { level: 1, name: 'Recover access' })).toBeVisible();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.getByRole('heading', { name: 'MacroMapper' })).toBeVisible();
    expect(screen.getByText('Enter your email to receive a reset link.')).toBeVisible();
  });

  test('keeps its child form usable with Tab and native Enter submission', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn((event) => event.preventDefault());
    renderWithProviders(
      <AuthPageShell title="Recover access">
        <form onSubmit={onSubmit}>
          <label htmlFor="recovery-email">Email</label>
          <input id="recovery-email" name="email" type="email" required />
          <button type="submit">Send reset link</button>
        </form>
      </AuthPageShell>,
    );

    await user.tab();
    expect(screen.getByRole('textbox', { name: 'Email' })).toHaveFocus();
    await user.keyboard('reader@example.com{Enter}');

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('textbox', { name: 'Email' })).toHaveValue('reader@example.com');
    expect(screen.getByRole('button', { name: 'Send reset link' })).toBeEnabled();
  });
});
