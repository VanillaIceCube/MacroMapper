import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AppNavigationDrawer from './AppNavigationDrawer';
import { renderWithProviders } from '../test-support/utils';

describe('AppNavigationDrawer', () => {
  test('renders generic navigation without workspace controls', () => {
    renderWithProviders(<AppNavigationDrawer open setOpen={jest.fn()} />);

    expect(screen.getByText('Full Stack Template')).toBeInTheDocument();
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Add application navigation here.')).toBeInTheDocument();
    expect(screen.queryByText(/Workspace/)).not.toBeInTheDocument();
  });

  test('closes from the close control', async () => {
    const user = userEvent.setup();
    const setOpen = jest.fn();
    renderWithProviders(<AppNavigationDrawer open setOpen={setOpen} />);

    await user.click(screen.getByLabelText('close navigation'));

    expect(setOpen).toHaveBeenCalledWith(false);
  });
});
