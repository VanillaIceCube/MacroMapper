import { screen } from '@testing-library/react';
import HomePage from './HomePage';
import { renderWithProviders } from '../test-support/utils';

describe('HomePage', () => {
  test('renders the placeholder paper', () => {
    renderWithProviders(<HomePage />);

    expect(screen.getByText(/Lorem ipsum dolor sit amet/)).toBeInTheDocument();
    expect(screen.queryByText(/Workspace/)).not.toBeInTheDocument();
  });
});
