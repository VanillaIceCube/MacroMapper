import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Menu, MenuItem } from '@mui/material';
import { useState } from 'react';
import '@testing-library/jest-dom';

function TestMenu() {
  const [anchor, setAnchor] = useState(null);
  return (
    <div>
      <button onClick={(e) => setAnchor(e.currentTarget)}>Open</button>
      <Menu disablePortal open={Boolean(anchor)} anchorEl={anchor} onClose={() => setAnchor(null)}>
        <MenuItem onClick={() => setAnchor(null)}>Item 1</MenuItem>
      </Menu>
    </div>
  );
}

test('menu opens', async () => {
  const user = userEvent.setup();
  render(<TestMenu />);
  await user.click(screen.getByText('Open'));
  expect(screen.getByText('Item 1')).toBeInTheDocument();
});
