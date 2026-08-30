import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MenuList, MenuItem } from '@mui/material';
import '@testing-library/jest-dom';

test('menulist with menuitem', async () => {
  render(
    <MenuList>
      <MenuItem>Item 1</MenuItem>
    </MenuList>
  );
  expect(screen.getByText('Item 1')).toBeInTheDocument();
});
