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
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  clearAllNotifications,
  clearNotification,
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../services/notificationApiClient';
import { logout } from '../services/requestClient';

const AUTH_PATHS = ['/login', '/register', '/forgot-password', '/reset-password'];

function safeGetSessionItem(key) {
  try {
    return sessionStorage.getItem(key) || '';
  } catch (_error) {
    return '';
  }
}

export default function AppHeader({ title, setDrawerOpen }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [profileAnchorEl, setProfileAnchorEl] = useState(null);
  const [notificationAnchorEl, setNotificationAnchorEl] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const [notificationError, setNotificationError] = useState('');

  const profileUsername = safeGetSessionItem('username');
  const profileEmail = safeGetSessionItem('email');
  const accessToken = safeGetSessionItem('accessToken');
  const profilePrimary = profileUsername || profileEmail.split?.('@')?.[0] || 'username';
  const profileSecondary =
    profileEmail || (profilePrimary === 'username' ? 'username@gmail.com' : null);
  const unreadCount = useMemo(
    () => notifications.filter((notification) => !notification.is_read).length,
    [notifications],
  );

  const loadNotifications = useCallback(async () => {
    if (!accessToken) {
      setNotifications([]);
      return;
    }

    setNotificationsLoading(true);
    setNotificationError('');
    try {
      const response = await fetchNotifications(accessToken);
      if (!response.ok) throw new Error('Unable to load notifications.');
      setNotifications(await response.json());
    } catch (_error) {
      setNotificationError('Notifications are unavailable right now.');
    } finally {
      setNotificationsLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    loadNotifications();
  }, [loadNotifications]);

  const updateNotification = async (notificationId, operation, errorMessage) => {
    setNotificationError('');
    try {
      const response = await operation(notificationId, accessToken);
      if (!response.ok) throw new Error(errorMessage);
      return response;
    } catch (_error) {
      setNotificationError(errorMessage);
      return null;
    }
  };

  const handleMarkRead = async (notificationId) => {
    const response = await updateNotification(
      notificationId,
      markNotificationRead,
      'Could not update that notification.',
    );
    if (!response) return;
    const updated = await response.json();
    setNotifications((current) =>
      current.map((notification) => (notification.id === updated.id ? updated : notification)),
    );
  };

  const handleClearNotification = async (notificationId) => {
    const response = await updateNotification(
      notificationId,
      clearNotification,
      'Could not clear that notification.',
    );
    if (!response) return;
    setNotifications((current) =>
      current.filter((notification) => notification.id !== notificationId),
    );
  };

  const handleOpenNotification = async (notification) => {
    if (!notification.is_read) await handleMarkRead(notification.id);
    if (notification.target_path) {
      setNotificationAnchorEl(null);
      navigate(notification.target_path);
    }
  };

  const handleMarkAllRead = async () => {
    setNotificationError('');
    try {
      const response = await markAllNotificationsRead(accessToken);
      if (!response.ok) throw new Error();
      setNotifications((current) =>
        current.map((notification) => ({ ...notification, is_read: true })),
      );
    } catch (_error) {
      setNotificationError('Could not update notifications.');
    }
  };

  const handleClearAll = async () => {
    setNotificationError('');
    try {
      const response = await clearAllNotifications(accessToken);
      if (!response.ok) throw new Error();
      setNotifications([]);
    } catch (_error) {
      setNotificationError('Could not clear notifications.');
    }
  };

  if (AUTH_PATHS.includes(location.pathname)) return null;

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
          <Typography variant="h6" component="div" noWrap sx={{ flexGrow: 1 }}>
            {title}
          </Typography>
          <IconButton
            size="large"
            color="inherit"
            aria-label="notifications"
            onClick={(event) => setNotificationAnchorEl(event.currentTarget)}
          >
            <Badge badgeContent={unreadCount} color="error">
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
                  backgroundColor: 'var(--secondary-background-color)',
                  color: 'var(--secondary-color)',
                  boxShadow: 3,
                  border: '2.5px solid var(--background-color)',
                  borderRadius: 1.5,
                  width: { xs: 320, sm: 380 },
                  maxWidth: 'calc(100vw - 24px)',
                },
              },
            }}
          >
            <Box sx={{ p: 1.5 }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between" gap={1}>
                <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                  Notifications
                </Typography>
                {notifications.length > 0 && (
                  <Button
                    size="small"
                    sx={{ color: 'var(--secondary-color)', fontWeight: 'bold' }}
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
                <Typography role="status" variant="body2" sx={{ py: 2 }}>
                  {notificationError}
                </Typography>
              )}
              {!notificationsLoading && !notificationError && notifications.length === 0 && (
                <Typography variant="body2">No notifications yet.</Typography>
              )}
              {!notificationsLoading && !notificationError && notifications.length > 0 && (
                <List dense disablePadding sx={{ maxHeight: 360, overflowY: 'auto' }}>
                  {notifications.map((notification, index) => (
                    <ListItem
                      key={notification.id}
                      disablePadding
                      divider={index < notifications.length - 1}
                    >
                      <ListItemButton
                        onClick={() => handleOpenNotification(notification)}
                        sx={{
                          alignItems: 'flex-start',
                          bgcolor: notification.is_read ? 'transparent' : 'rgba(0, 0, 0, 0.06)',
                        }}
                      >
                        <ListItemText
                          primary={notification.title}
                          secondary={notification.message}
                          slotProps={{
                            primary: {
                              sx: {
                                color: 'var(--secondary-color)',
                                fontWeight: notification.is_read ? 500 : 'bold',
                              },
                            },
                            secondary: { sx: { color: 'var(--secondary-color)' } },
                          }}
                        />
                        <Tooltip title="Clear notification">
                          <IconButton
                            aria-label="Clear notification"
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
                              color: 'var(--secondary-color)',
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
                  backgroundColor: 'var(--secondary-background-color)',
                  color: 'var(--secondary-color)',
                  boxShadow: 3,
                  border: '2.5px solid var(--background-color)',
                  borderRadius: 1.5,
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
                  primary: { sx: { fontWeight: 'bold', color: 'var(--secondary-color)' } },
                  secondary: { sx: { color: 'var(--secondary-color)', opacity: 1 } },
                }}
              />
            </MenuItem>
            <Divider
              variant="middle"
              sx={{ my: 0.25, mx: 1, borderBottomWidth: 2, bgcolor: 'var(--secondary-color)' }}
            />
            <MenuItem
              sx={{
                py: 0.5,
                px: 1.5,
                minHeight: 'auto',
                fontWeight: 'bold',
                color: 'var(--secondary-color)',
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
          >
            <MenuIcon />
          </IconButton>
        </Toolbar>
      </AppBar>
    </Box>
  );
}
