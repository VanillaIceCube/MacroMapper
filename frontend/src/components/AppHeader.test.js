import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { logout } from '../services/requestClient';
import { renderWithProviders } from '../test-support/utils';
import AppHeader from './AppHeader';

jest.mock('../services/requestClient', () => ({
  logout: jest.fn(),
}));

describe('AppHeader', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  test('does not render on authentication pages', () => {
    renderWithProviders(<AppHeader />, { routeEntries: ['/login'] });

    expect(screen.queryByText('MacroMapper')).not.toBeInTheDocument();
  });

  test('shows the signed-in profile and logs out', async () => {
    sessionStorage.setItem('username', 'mapper');
    sessionStorage.setItem('email', 'mapper@example.com');
    renderWithProviders(<AppHeader />);

    await userEvent.click(screen.getByRole('button', { name: 'user profile' }));
    expect(screen.getByText('mapper')).toBeInTheDocument();
    expect(screen.getByText('mapper@example.com')).toBeInTheDocument();

    await userEvent.click(screen.getByText('Logout'));
    expect(logout).toHaveBeenCalled();
  });
});
