import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import AppNavigationDrawer from './AppNavigationDrawer';
import { renderWithProviders } from '../test-support/utils';

function DrawerHarness({ onOpenChange }) {
  const [open, setOpen] = useState(false);

  const updateOpen = (nextOpen) => {
    setOpen(nextOpen);
    onOpenChange(nextOpen);
  };

  return (
    <>
      <button type="button" onClick={() => updateOpen(true)}>
        open navigation
      </button>
      <AppNavigationDrawer open={open} setOpen={updateOpen} />
    </>
  );
}

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
    const onOpenChange = vi.fn();
    renderWithProviders(<DrawerHarness onOpenChange={onOpenChange} />);

    const openControl = screen.getByRole('button', { name: 'open navigation' });
    await user.click(openControl);
    await user.click(screen.getByLabelText('close navigation'));

    expect(onOpenChange).toHaveBeenLastCalledWith(false);
    await waitFor(() => expect(openControl).toHaveFocus());
  });
});
