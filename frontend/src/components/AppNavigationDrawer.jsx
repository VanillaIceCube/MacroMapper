import CloseIcon from '@mui/icons-material/Close';
import HomeIcon from '@mui/icons-material/Home';
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
import { useNavigate } from 'react-router';

export default function AppNavigationDrawer({ open, setOpen }) {
  const navigate = useNavigate();

  const goHome = () => {
    setOpen(false);
    navigate('/');
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
          <ListItemButton
            onClick={goHome}
            sx={{
              color: 'var(--atlas-forest-dark)',
              bgcolor: 'var(--atlas-forest-soft)',
              borderRadius: 1.5,
              border: '1px solid rgba(46, 107, 79, 0.2)',
            }}
          >
            <ListItemIcon sx={{ color: 'var(--atlas-forest)', minWidth: 40 }}>
              <HomeIcon />
            </ListItemIcon>
            <ListItemText primary="Home" />
          </ListItemButton>
        </List>
        <Typography variant="body2" sx={{ px: 2.5, py: 2, color: 'var(--atlas-ink-muted)' }}>
          Nutrition and activity, mapped clearly.
        </Typography>
      </Box>
    </Drawer>
  );
}
