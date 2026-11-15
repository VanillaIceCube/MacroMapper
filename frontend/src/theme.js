import { alpha, createTheme } from '@mui/material/styles';

const fieldAtlasTokens = {
  bone: '#F6F1E7',
  paper: '#FFFDF8',
  ink: '#17324D',
  inkMuted: '#52687A',
  forest: '#2E6B4F',
  forestDark: '#23513C',
  forestSoft: '#E4EFE8',
  persimmon: '#E46B3C',
  persimmonDark: '#A94420',
  persimmonSoft: '#F9E8DF',
  mineral: '#A9CAD4',
  mineralDark: '#47798A',
  mineralSoft: '#E5F0F3',
  fiber: '#667D3F',
  sugar: '#A54F76',
  sodium: '#66699B',
  cholesterol: '#9B672F',
  radiusCompact: 6,
  radiusSurface: 12,
  radiusProminent: 18,
  radiusPill: 999,
};

const headingFont = '"Newsreader", "Source Serif 4", Georgia, serif';
const utilityFont = '"Inter", "Segoe UI", Arial, sans-serif';

const fieldAtlasTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: fieldAtlasTokens.forest,
      dark: fieldAtlasTokens.forestDark,
      contrastText: '#FFFFFF',
    },
    secondary: {
      main: fieldAtlasTokens.persimmon,
      dark: fieldAtlasTokens.persimmonDark,
      contrastText: '#FFFFFF',
    },
    info: {
      main: fieldAtlasTokens.mineralDark,
      light: fieldAtlasTokens.mineral,
      contrastText: '#FFFFFF',
    },
    background: {
      default: fieldAtlasTokens.bone,
      paper: fieldAtlasTokens.paper,
    },
    text: {
      primary: fieldAtlasTokens.ink,
      secondary: fieldAtlasTokens.inkMuted,
    },
    divider: alpha(fieldAtlasTokens.ink, 0.18),
  },
  shape: {
    borderRadius: fieldAtlasTokens.radiusSurface,
  },
  typography: {
    fontFamily: utilityFont,
    h1: { fontFamily: headingFont, fontWeight: 600, letterSpacing: '-0.025em' },
    h2: { fontFamily: headingFont, fontWeight: 600, letterSpacing: '-0.02em' },
    h3: { fontFamily: headingFont, fontWeight: 600, letterSpacing: '-0.02em' },
    h4: { fontFamily: headingFont, fontWeight: 600, letterSpacing: '-0.015em' },
    h5: { fontFamily: headingFont, fontWeight: 600 },
    h6: { fontFamily: headingFont, fontWeight: 600 },
    button: { fontWeight: 700, letterSpacing: '0.01em', textTransform: 'none' },
    overline: { fontWeight: 700, letterSpacing: '0.12em' },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        // The theme is the source for both MUI defaults and existing CSS consumers.
        ':root': {
          '--atlas-bone': fieldAtlasTokens.bone,
          '--atlas-paper': fieldAtlasTokens.paper,
          '--atlas-ink': fieldAtlasTokens.ink,
          '--atlas-ink-muted': fieldAtlasTokens.inkMuted,
          '--atlas-forest': fieldAtlasTokens.forest,
          '--atlas-forest-dark': fieldAtlasTokens.forestDark,
          '--atlas-forest-soft': fieldAtlasTokens.forestSoft,
          '--atlas-persimmon': fieldAtlasTokens.persimmon,
          '--atlas-persimmon-dark': fieldAtlasTokens.persimmonDark,
          '--atlas-persimmon-soft': fieldAtlasTokens.persimmonSoft,
          '--atlas-mineral': fieldAtlasTokens.mineral,
          '--atlas-mineral-dark': fieldAtlasTokens.mineralDark,
          '--atlas-mineral-soft': fieldAtlasTokens.mineralSoft,
          '--atlas-border': alpha(fieldAtlasTokens.ink, 0.18),
          '--atlas-border-strong': alpha(fieldAtlasTokens.ink, 0.38),
          '--atlas-radius-compact': `${fieldAtlasTokens.radiusCompact}px`,
          '--atlas-radius-surface': `${fieldAtlasTokens.radiusSurface}px`,
          '--atlas-radius-prominent': `${fieldAtlasTokens.radiusProminent}px`,
          '--atlas-radius-pill': `${fieldAtlasTokens.radiusPill}px`,
          '--atlas-contour-ink': alpha(fieldAtlasTokens.ink, 0.045),
          '--atlas-contour-ink-soft': alpha(fieldAtlasTokens.ink, 0.035),
          '--atlas-contour-forest': alpha(fieldAtlasTokens.forest, 0.045),
          '--atlas-contour-forest-soft': alpha(fieldAtlasTokens.forest, 0.035),
          '--atlas-link-underline': alpha(fieldAtlasTokens.forestDark, 0.45),
          '--atlas-link-focus': alpha(fieldAtlasTokens.persimmon, 0.35),
          '--calorie-color': 'var(--atlas-ink)',
          '--protein-color': 'var(--atlas-forest)',
          '--carbohydrate-color': 'var(--atlas-mineral-dark)',
          '--fat-color': 'var(--atlas-persimmon)',
          '--fiber-color': fieldAtlasTokens.fiber,
          '--sugar-color': fieldAtlasTokens.sugar,
          '--sodium-color': fieldAtlasTokens.sodium,
          '--cholesterol-color': fieldAtlasTokens.cholesterol,
          '--background-color': 'var(--atlas-bone)',
          '--secondary-background-color': 'var(--atlas-paper)',
          '--secondary-color': 'var(--atlas-ink)',
          '--text-color': 'var(--atlas-ink)',
        },
        body: {
          minWidth: 320,
          backgroundColor: fieldAtlasTokens.bone,
          color: fieldAtlasTokens.ink,
        },
        '::selection': {
          backgroundColor: fieldAtlasTokens.mineral,
          color: fieldAtlasTokens.ink,
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          color: fieldAtlasTokens.ink,
          background: alpha(fieldAtlasTokens.paper, 0.96),
          boxShadow: 'none',
          borderBottom: `1px solid ${alpha(fieldAtlasTokens.ink, 0.18)}`,
          backdropFilter: 'blur(12px)',
        },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: {
          minHeight: 44,
          borderRadius: 'var(--atlas-radius-surface)',
          paddingInline: 20,
        },
        containedPrimary: {
          '&:hover': { backgroundColor: fieldAtlasTokens.forestDark },
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          minWidth: 44,
          minHeight: 44,
          '&:focus-visible': {
            outline: `3px solid ${alpha(fieldAtlasTokens.persimmon, 0.45)}`,
            outlineOffset: 2,
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: '#FFFFFF',
          '& fieldset': { borderColor: alpha(fieldAtlasTokens.ink, 0.32) },
          '&:hover fieldset': { borderColor: fieldAtlasTokens.inkMuted },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderColor: fieldAtlasTokens.forest,
            borderWidth: 2,
          },
        },
      },
    },
    MuiInputLabel: {
      styleOverrides: {
        root: {
          color: fieldAtlasTokens.inkMuted,
          '&.Mui-focused': { color: fieldAtlasTokens.forestDark },
        },
      },
    },
    MuiInput: {
      styleOverrides: { underline: { '&:after': { borderBottomColor: fieldAtlasTokens.forest } } },
    },
    MuiFilledInput: {
      styleOverrides: { underline: { '&:after': { borderBottomColor: fieldAtlasTokens.forest } } },
    },
    MuiChip: {
      styleOverrides: {
        root: { borderRadius: 'var(--atlas-radius-pill)', fontWeight: 700 },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          border: `1px solid ${alpha(fieldAtlasTokens.ink, 0.18)}`,
          borderRadius: 'var(--atlas-radius-surface)',
          color: fieldAtlasTokens.ink,
        },
        standardSuccess: { backgroundColor: '#E8F2EC' },
        standardInfo: { backgroundColor: '#E6F0F3' },
        standardWarning: { backgroundColor: '#FBEDE5' },
        standardError: { backgroundColor: '#F7E8E5' },
      },
    },
    MuiLink: {
      styleOverrides: {
        root: {
          color: fieldAtlasTokens.forestDark,
          fontWeight: 700,
        },
      },
    },
  },
});

export default fieldAtlasTheme;
