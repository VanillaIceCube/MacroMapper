import AccountCircle from '@mui/icons-material/AccountCircle';
import {
  AppBar,
  Box,
  Divider,
  IconButton,
  ListItemText,
  Menu,
  MenuItem,
  Toolbar,
  Typography,
} from '@mui/material';
import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { logout } from '../services/requestClient';

const AUTH_PATHS = new Set(['/login', '/register', '/forgot-password', '/reset-password']);

function safeGetSessionItem(key) {
  try {
    return sessionStorage.getItem(key) || '';
  } catch (_err) {
    return '';
  }
}

export default function AppHeader() {
  const location = useLocation();
  const [profileAnchorEl, setProfileAnchorEl] = useState(null);

  if (AUTH_PATHS.has(location.pathname)) {
    return null;
  }

  const username = safeGetSessionItem('username');
  const email = safeGetSessionItem('email');
  const profileName = username || email.split('@')[0] || 'User';

  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar
        position="static"
        sx={{
          color: 'var(--secondary-background-color)',
          background: 'var(--background-color)',
          boxShadow: 'none',
        }}
      >
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1, fontWeight: 'bold' }}>
            MacroMapper
          </Typography>
          <IconButton
            size="large"
            color="inherit"
            aria-label="user profile"
            onClick={(event) => setProfileAnchorEl(event.currentTarget)}
          >
            <AccountCircle />
          </IconButton>
          <Menu
            anchorEl={profileAnchorEl}
            open={Boolean(profileAnchorEl)}
            onClose={() => setProfileAnchorEl(null)}
          >
            <MenuItem disableRipple sx={{ cursor: 'default' }}>
              <ListItemText primary={profileName} secondary={email || null} />
            </MenuItem>
            <Divider />
            <MenuItem
              onClick={() => {
                setProfileAnchorEl(null);
                logout();
              }}
            >
              Logout
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>
    </Box>
  );
}
