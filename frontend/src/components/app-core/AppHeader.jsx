import useSession from '../../hooks/useSession';
import AccountCircle from '@mui/icons-material/AccountCircle';
import MenuIcon from '@mui/icons-material/Menu';
import {
  AppBar,
  Box,
  Divider,
  IconButton,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  Toolbar,
  Typography,
} from '@mui/material';
import { useState } from 'react';
import { Link as RouterLink, useLocation } from 'react-router';
import { logout } from '../../services/requestClient';
import NotificationsMenu from './NotificationsMenu';

const AUTH_PATHS = ['/login', '/register', '/forgot-password', '/reset-password'];

export default function AppHeader({ title, setDrawerOpen }) {
  const location = useLocation();
  const [profileAnchorEl, setProfileAnchorEl] = useState(null);
  const session = useSession();
  const { username: profileUsername, email: profileEmail } = session;
  const profilePrimary = profileUsername || profileEmail.split?.('@')?.[0] || 'Account';
  const profileSecondary = profileEmail || null;
  if (AUTH_PATHS.includes(location.pathname)) return null;

  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="sticky">
        <Toolbar sx={{ width: '100%', maxWidth: 1280, mx: 'auto', gap: { xs: 0, sm: 0.5 } }}>
          <Stack
            direction="row"
            spacing={1.25}
            sx={{
              alignItems: 'center',
              flexGrow: 1,
            }}
          >
            <Box
              component="img"
              src={`${import.meta.env.BASE_URL}macromapper-mark.png`}
              alt=""
              aria-hidden="true"
              sx={{ width: 34, height: 34 }}
            />
            <Typography
              variant="h5"
              component="div"
              noWrap
              sx={{ color: 'var(--surface-text)', fontWeight: 650, letterSpacing: '-0.02em' }}
            >
              {title}
            </Typography>
          </Stack>
          <NotificationsMenu />
          <IconButton
            size="large"
            color="inherit"
            aria-label="user profile"
            onClick={(event) => setProfileAnchorEl(event.currentTarget)}
            sx={{
              color: 'var(--surface-text)',
              '&:hover': { bgcolor: 'var(--atlas-mineral-soft)' },
            }}
          >
            <AccountCircle />
          </IconButton>
          <Menu
            anchorEl={profileAnchorEl}
            open={Boolean(profileAnchorEl)}
            onClose={() => setProfileAnchorEl(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            slotProps={{
              paper: {
                sx: {
                  backgroundColor: 'var(--surface-background)',
                  color: 'var(--surface-text)',
                  boxShadow: '0 18px 50px rgba(23, 50, 77, 0.14)',
                  border: '1px solid var(--atlas-border-strong)',
                  borderRadius: 'var(--atlas-radius-prominent)',
                  minWidth: 220,
                },
              },
            }}
          >
            <MenuItem
              disableRipple
              sx={{
                cursor: 'default',
                '&:hover': { backgroundColor: 'transparent' },
                py: 0.75,
              }}
            >
              <ListItemText
                primary={profilePrimary}
                secondary={profileSecondary}
                slotProps={{
                  primary: { sx: { fontWeight: 'bold', color: 'var(--surface-text)' } },
                  secondary: { sx: { color: 'var(--muted-text)', opacity: 1 } },
                }}
              />
            </MenuItem>
            <Divider
              variant="middle"
              sx={{ my: 0.25, mx: 1, borderColor: 'var(--atlas-border)' }}
            />
            {import.meta.env.VITE_MCP_ENABLED === '1' && (
              <MenuItem
                component={RouterLink}
                to="/connections"
                onClick={() => setProfileAnchorEl(null)}
              >
                Connected Apps
              </MenuItem>
            )}
            <MenuItem
              sx={{
                py: 0.5,
                px: 1.5,
                minHeight: 'auto',
                fontWeight: 'bold',
                color: 'var(--atlas-forest-dark)',
              }}
              onClick={() => {
                setProfileAnchorEl(null);
                logout();
              }}
            >
              Logout
            </MenuItem>
          </Menu>
          <IconButton
            size="large"
            edge="end"
            color="inherit"
            aria-label="menu"
            onClick={() => setDrawerOpen((current) => !current)}
            sx={{
              color: 'var(--surface-text)',
              '&:hover': { bgcolor: 'var(--atlas-mineral-soft)' },
            }}
          >
            <MenuIcon />
          </IconButton>
        </Toolbar>
      </AppBar>
    </Box>
  );
}
