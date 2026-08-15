import { screen } from '@testing-library/react';
import HomePage from './HomePage';
import { renderWithProviders } from '../test-support/utils';

describe('HomePage', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  test('renders the MacroMapper dashboard for the signed-in user', () => {
    sessionStorage.setItem('username', 'Diana');
    renderWithProviders(<HomePage />);

    expect(
      screen.getByRole('heading', { name: 'Welcome to MacroMapper, Diana' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Private by default' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Review every estimate' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Understand the whole day' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Your account is ready' })).toBeInTheDocument();
  });
});
