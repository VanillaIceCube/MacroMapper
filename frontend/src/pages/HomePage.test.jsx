import { screen } from '@testing-library/react';
import HomePage from './HomePage';
import { renderWithProviders } from '../test-support/utils';

describe('HomePage', () => {
  test('renders the starter content', () => {
    renderWithProviders(<HomePage />);

    expect(screen.getByRole('heading', { name: 'Hello World' })).toBeInTheDocument();
  });
});
