import useNotifications from '../hooks/useNotifications';
import useSession from '../hooks/useSession';
import { getSessionVersion } from '../services/sessionState';
import AccountCircle from '@mui/icons-material/AccountCircle';
import ClearIcon from '@mui/icons-material/Clear';
import MenuIcon from '@mui/icons-material/Menu';
import NotificationsIcon from '@mui/icons-material/Notifications';
import {
  AppBar,
  Badge,
  Box,
  Button,
  CircularProgress,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Menu,
  MenuItem,
  Popover,
  Stack,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material';
import { useState } from 'react';
import { Link as RouterLink, useLocation, useNavigate } from 'react-router';
import {
  clearAllNotifications,
  clearNotification,
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../services/notificationApiClient';
import { getResponseErrorMessage } from '../services/authSession';
import { logout } from '../services/requestClient';

const AUTH_PATHS = ['/login', '/register', '/forgot-password', '/reset-password'];

const notificationApi = {
  fetchNotifications,
  markNotificationRead,
  clearNotification,
  markAllNotificationsRead,
  clearAllNotifications,
};

export default function AppHeader({ title, setDrawerOpen }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [profileAnchorEl, setProfileAnchorEl] = useState(null);
  const [notificationAnchorEl, setNotificationAnchorEl] = useState(null);
  const session = useSession();
  const { username: profileUsername, email: profileEmail } = session;
  const profilePrimary = profileUsername || profileEmail.split?.('@')?.[0] || 'Account';
  const profileSecondary = profileEmail || null;
  const {
    notifications,
    notificationsLoading,
    notificationError,
    actionPending,
    pendingIds,
    unreadCount,
    loadNotifications,
    markRead,
    clearNotification: handleClearNotification,
    markAllRead: handleMarkAllRead,
    clearAll: handleClearAll,
  } = useNotifications(notificationApi, getResponseErrorMessage);

  const handleOpenNotification = async (notification) => {
    if (!(await markRead(notification)) || getSessionVersion() !== session.version) return;
    if (notification.target_path) {
      setNotificationAnchorEl(null);
      navigate(notification.target_path);
    }
  };

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
              sx={{ color: 'var(--atlas-ink)', fontWeight: 650, letterSpacing: '-0.02em' }}
            >
              {title}
            </Typography>
          </Stack>
          <IconButton
            size="large"
            color="inherit"
            aria-label="notifications"
            onClick={(event) => setNotificationAnchorEl(event.currentTarget)}
            sx={{ color: 'var(--atlas-ink)', '&:hover': { bgcolor: 'var(--atlas-mineral-soft)' } }}
          >
            <Badge badgeContent={unreadCount} color="secondary">
              <NotificationsIcon />
            </Badge>
          </IconButton>
          <Popover
            anchorEl={notificationAnchorEl}
            open={Boolean(notificationAnchorEl)}
            onClose={() => setNotificationAnchorEl(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            slotProps={{
              paper: {
                sx: {
                  backgroundColor: 'var(--atlas-paper)',
                  color: 'var(--atlas-ink)',
                  boxShadow: '0 18px 50px rgba(23, 50, 77, 0.14)',
                  border: '1px solid var(--atlas-border-strong)',
                  borderRadius: 'var(--atlas-radius-prominent)',
                  width: { xs: 320, sm: 380 },
                  maxWidth: 'calc(100vw - 24px)',
                },
              },
            }}
          >
            <Box sx={{ p: 1.5 }}>
              <Stack
                direction="row"
                sx={{
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 1,
                }}
              >
                <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                  Notifications
                </Typography>
                {notifications.length > 0 && (
                  <Button
                    size="small"
                    disabled={actionPending || pendingIds.size > 0}
                    sx={{ color: 'var(--atlas-forest-dark)', fontWeight: 'bold' }}
                    onClick={unreadCount > 0 ? handleMarkAllRead : handleClearAll}
                  >
                    {unreadCount > 0 ? 'Mark all read' : 'Clear all'}
                  </Button>
                )}
              </Stack>
              <Divider sx={{ my: 1 }} />
              {notificationsLoading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
                  <CircularProgress size={24} />
                </Box>
              )}
              {!notificationsLoading && notificationError && (
                <Stack spacing={1} sx={{ alignItems: 'flex-start' }}>
                  <Typography role="status" variant="body2" sx={{ py: 2 }}>
                    {notificationError}
                  </Typography>
                  {notifications.length === 0 && (
                    <Button
                      size="small"
                      color="inherit"
                      disabled={actionPending || pendingIds.size > 0}
                      onClick={loadNotifications}
                    >
                      Retry
                    </Button>
                  )}
                </Stack>
              )}
              {!notificationsLoading && !notificationError && notifications.length === 0 && (
                <Typography variant="body2">No notifications yet.</Typography>
              )}
              {!notificationsLoading && notifications.length > 0 && (
                <List dense disablePadding sx={{ maxHeight: 360, overflowY: 'auto' }}>
                  {notifications.map((notification, index) => (
                    <ListItem
                      key={notification.id}
                      disablePadding
                      divider={index < notifications.length - 1}
                    >
                      <ListItemButton
                        disabled={actionPending || pendingIds.has(notification.id)}
                        onClick={() => handleOpenNotification(notification)}
                        sx={{
                          alignItems: 'flex-start',
                          borderRadius: 'var(--atlas-radius-surface)',
                          bgcolor: notification.is_read
                            ? 'transparent'
                            : 'var(--atlas-mineral-soft)',
                        }}
                      >
                        <ListItemText
                          primary={notification.title}
                          secondary={notification.message}
                          slotProps={{
                            primary: {
                              sx: {
                                color: 'var(--atlas-ink)',
                                fontWeight: notification.is_read ? 500 : 'bold',
                              },
                            },
                            secondary: { sx: { color: 'var(--atlas-ink-muted)' } },
                          }}
                        />
                        <Tooltip title="Clear notification">
                          <IconButton
                            aria-label="Clear notification"
                            disabled={actionPending || pendingIds.has(notification.id)}
                            size="small"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleClearNotification(notification.id);
                            }}
                            sx={{
                              width: 40,
                              height: 40,
                              ml: 1,
                              alignSelf: 'center',
                              flexShrink: 0,
                              color: 'var(--atlas-ink)',
                            }}
                          >
                            <ClearIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </ListItemButton>
                    </ListItem>
                  ))}
                </List>
              )}
            </Box>
          </Popover>
          <IconButton
            size="large"
            color="inherit"
            aria-label="user profile"
            onClick={(event) => setProfileAnchorEl(event.currentTarget)}
            sx={{ color: 'var(--atlas-ink)', '&:hover': { bgcolor: 'var(--atlas-mineral-soft)' } }}
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
                  backgroundColor: 'var(--atlas-paper)',
                  color: 'var(--atlas-ink)',
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
                  primary: { sx: { fontWeight: 'bold', color: 'var(--atlas-ink)' } },
                  secondary: { sx: { color: 'var(--atlas-ink-muted)', opacity: 1 } },
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
            sx={{ color: 'var(--atlas-ink)', '&:hover': { bgcolor: 'var(--atlas-mineral-soft)' } }}
          >
            <MenuIcon />
          </IconButton>
        </Toolbar>
      </AppBar>
    </Box>
  );
}
