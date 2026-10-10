import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AppNavigationDrawer from './AppNavigationDrawer';
import { renderWithProviders } from '../test-support/utils';

describe('AppNavigationDrawer', () => {
  test('renders MacroMapper navigation', () => {
    renderWithProviders(<AppNavigationDrawer open setOpen={vi.fn()} />);

    expect(screen.getByText('MacroMapper')).toBeInTheDocument();
    expect(screen.queryByText('Home')).not.toBeInTheDocument();
    expect(screen.getByText('Meal diary')).toBeInTheDocument();
    expect(screen.getByText('Nutrition and activity, mapped clearly.')).toBeInTheDocument();
    expect(screen.queryByText(/Workspace/)).not.toBeInTheDocument();
  });

  test('closes from the close control', async () => {
    const user = userEvent.setup();
    const setOpen = vi.fn();
    renderWithProviders(<AppNavigationDrawer open setOpen={setOpen} />);

    await user.click(screen.getByLabelText('close navigation'));

    expect(setOpen).toHaveBeenCalledWith(false);
  });
});
