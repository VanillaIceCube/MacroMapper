import CloseIcon from '@mui/icons-material/Close';
import HomeIcon from '@mui/icons-material/Home';
import RestaurantMenuIcon from '@mui/icons-material/RestaurantMenu';
import {
  Box,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  Typography,
} from '@mui/material';
import { useLocation, useNavigate } from 'react-router';

export default function AppNavigationDrawer({ open, setOpen }) {
  const navigate = useNavigate();
  const location = useLocation();
  const isHome = location.pathname === '/';
  const isDiary = location.pathname === '/diary';

  const navigationItemStyles = (active) => ({
    color: active ? 'var(--atlas-forest-dark)' : 'var(--atlas-ink)',
    bgcolor: active ? 'var(--atlas-forest-soft)' : 'transparent',
    borderRadius: 1.5,
    border: active ? '1px solid rgba(46, 107, 79, 0.2)' : '1px solid transparent',
    '&:hover': { bgcolor: active ? 'var(--atlas-forest-soft)' : 'var(--atlas-mineral-soft)' },
  });

  const goHome = () => {
    setOpen(false);
    navigate('/');
  };

  const goDiary = () => {
    setOpen(false);
    navigate('/diary');
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={() => setOpen(false)}
      sx={{
        '& .MuiDrawer-paper': {
          bgcolor: 'var(--atlas-paper)',
          color: 'var(--atlas-ink)',
          borderLeft: '1px solid var(--atlas-border-strong)',
          borderTopLeftRadius: 20,
          borderBottomLeftRadius: 20,
          boxShadow: '-18px 0 50px rgba(23, 50, 77, 0.12)',
        },
        '& .MuiListItemText-primary': { fontWeight: 'bold' },
      }}
    >
      <Box
        sx={{
          width: { xs: 280, sm: 320 },
          minHeight: '100%',
          bgcolor: 'var(--atlas-paper)',
          color: 'var(--atlas-ink)',
        }}
        role="navigation"
      >
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ p: 2 }}>
          <Stack direction="row" alignItems="center" spacing={1.25}>
            <Box
              component="img"
              src="/macromapper-mark.svg"
              alt=""
              sx={{ width: 38, height: 38 }}
            />
            <Typography
              variant="h5"
              sx={{
                fontFamily: '"Inter", "Segoe UI", Arial, sans-serif',
                fontWeight: 800,
                letterSpacing: '-0.035em',
                color: '#06285F',
              }}
            >
              MacroMapper
            </Typography>
          </Stack>
          <IconButton
            aria-label="close navigation"
            onClick={() => setOpen(false)}
            sx={{ color: 'var(--atlas-ink)' }}
          >
            <CloseIcon />
          </IconButton>
        </Stack>
        <Divider sx={{ mx: 2, borderColor: 'var(--atlas-border)' }} />
        <List sx={{ px: 1.5, pt: 2 }}>
          <ListItemButton onClick={goHome} selected={isHome} sx={navigationItemStyles(isHome)}>
            <ListItemIcon
              sx={{
                color: isHome ? 'var(--atlas-forest)' : 'var(--atlas-ink-muted)',
                minWidth: 40,
              }}
            >
              <HomeIcon />
            </ListItemIcon>
            <ListItemText primary="Home" />
          </ListItemButton>
          <ListItemButton
            onClick={goDiary}
            selected={isDiary}
            sx={{ mt: 0.75, ...navigationItemStyles(isDiary) }}
          >
            <ListItemIcon
              sx={{
                color: isDiary ? 'var(--atlas-forest)' : 'var(--atlas-ink-muted)',
                minWidth: 40,
              }}
            >
              <RestaurantMenuIcon />
            </ListItemIcon>
            <ListItemText primary="Meal diary" />
          </ListItemButton>
        </List>
        <Typography variant="body2" sx={{ px: 2.5, py: 2, color: 'var(--atlas-ink-muted)' }}>
          Nutrition and activity, mapped clearly.
        </Typography>
      </Box>
    </Drawer>
  );
}
