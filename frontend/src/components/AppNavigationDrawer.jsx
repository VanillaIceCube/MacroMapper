import CloseIcon from '@mui/icons-material/Close';
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
  const isDiary = location.pathname === '/' || location.pathname === '/diary';

  const navigationItemStyles = (active) => ({
    color: active ? 'var(--atlas-forest-dark)' : 'var(--atlas-ink)',
    bgcolor: active ? 'var(--atlas-forest-soft)' : 'transparent',
    borderRadius: 1.5,
    border: active ? '1px solid rgba(46, 107, 79, 0.2)' : '1px solid transparent',
    '&:hover': { bgcolor: active ? 'var(--atlas-forest-soft)' : 'var(--atlas-mineral-soft)' },
  });

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
        <Stack
          direction="row"
          sx={{
            alignItems: 'center',
            justifyContent: 'space-between',
            p: 2,
          }}
        >
          <Stack
            direction="row"
            spacing={1.25}
            sx={{
              alignItems: 'center',
            }}
          >
            <Box
              component="img"
              src="/macromapper-mark.png"
              alt=""
              sx={{ width: 34, height: 34 }}
            />
            <Typography variant="h5" sx={{ fontWeight: 650, color: 'var(--atlas-ink)' }}>
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
          <ListItemButton onClick={goDiary} selected={isDiary} sx={navigationItemStyles(isDiary)}>
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
