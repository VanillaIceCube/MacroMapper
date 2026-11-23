import { alpha, createTheme } from '@mui/material/styles';

const themeTokens = {
  pageBackground: '#F6F1E7',
  surfaceBackground: '#FFFDF8',
  surfaceText: '#17324D',
  mutedText: '#52687A',
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

const appTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: themeTokens.forest,
      dark: themeTokens.forestDark,
      contrastText: '#FFFFFF',
    },
    secondary: {
      main: themeTokens.persimmon,
      dark: themeTokens.persimmonDark,
      contrastText: '#FFFFFF',
    },
    info: {
      main: themeTokens.mineralDark,
      light: themeTokens.mineral,
      contrastText: '#FFFFFF',
    },
    background: {
      default: themeTokens.pageBackground,
      paper: themeTokens.surfaceBackground,
    },
    text: {
      primary: themeTokens.surfaceText,
      secondary: themeTokens.mutedText,
    },
    divider: alpha(themeTokens.surfaceText, 0.18),
  },
  shape: {
    borderRadius: themeTokens.radiusSurface,
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
          '--page-background': themeTokens.pageBackground,
          '--surface-background': themeTokens.surfaceBackground,
          '--surface-text': themeTokens.surfaceText,
          '--page-text': themeTokens.surfaceText,
          '--muted-text': themeTokens.mutedText,
          '--atlas-forest': themeTokens.forest,
          '--atlas-forest-dark': themeTokens.forestDark,
          '--atlas-forest-soft': themeTokens.forestSoft,
          '--atlas-persimmon': themeTokens.persimmon,
          '--atlas-persimmon-dark': themeTokens.persimmonDark,
          '--atlas-persimmon-soft': themeTokens.persimmonSoft,
          '--atlas-mineral': themeTokens.mineral,
          '--atlas-mineral-dark': themeTokens.mineralDark,
          '--atlas-mineral-soft': themeTokens.mineralSoft,
          '--atlas-border': alpha(themeTokens.surfaceText, 0.18),
          '--atlas-border-strong': alpha(themeTokens.surfaceText, 0.38),
          '--atlas-radius-compact': `${themeTokens.radiusCompact}px`,
          '--atlas-radius-surface': `${themeTokens.radiusSurface}px`,
          '--atlas-radius-prominent': `${themeTokens.radiusProminent}px`,
          '--atlas-radius-pill': `${themeTokens.radiusPill}px`,
          '--atlas-contour-ink': alpha(themeTokens.surfaceText, 0.045),
          '--atlas-contour-ink-soft': alpha(themeTokens.surfaceText, 0.035),
          '--atlas-contour-forest': alpha(themeTokens.forest, 0.045),
          '--atlas-contour-forest-soft': alpha(themeTokens.forest, 0.035),
          '--atlas-link-underline': alpha(themeTokens.forestDark, 0.45),
          '--atlas-link-focus': alpha(themeTokens.persimmon, 0.35),
          '--calorie-color': 'var(--surface-text)',
          '--protein-color': 'var(--atlas-forest)',
          '--carbohydrate-color': 'var(--atlas-mineral-dark)',
          '--fat-color': 'var(--atlas-persimmon)',
          '--fiber-color': themeTokens.fiber,
          '--sugar-color': themeTokens.sugar,
          '--sodium-color': themeTokens.sodium,
          '--cholesterol-color': themeTokens.cholesterol,
        },
        body: {
          minWidth: 320,
          backgroundColor: themeTokens.pageBackground,
          color: themeTokens.surfaceText,
        },
        '::selection': {
          backgroundColor: themeTokens.mineral,
          color: themeTokens.surfaceText,
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          color: themeTokens.surfaceText,
          background: alpha(themeTokens.surfaceBackground, 0.96),
          boxShadow: 'none',
          borderBottom: `1px solid ${alpha(themeTokens.surfaceText, 0.18)}`,
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
          '&:hover': { backgroundColor: themeTokens.forestDark },
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          minWidth: 44,
          minHeight: 44,
          '&:focus-visible': {
            outline: `3px solid ${alpha(themeTokens.persimmon, 0.45)}`,
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
          '& fieldset': { borderColor: alpha(themeTokens.surfaceText, 0.32) },
          '&:hover fieldset': { borderColor: themeTokens.mutedText },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderColor: themeTokens.forest,
            borderWidth: 2,
          },
        },
      },
    },
    MuiInputLabel: {
      styleOverrides: {
        root: {
          color: themeTokens.mutedText,
          '&.Mui-focused': { color: themeTokens.forestDark },
        },
      },
    },
    MuiInput: {
      styleOverrides: { underline: { '&:after': { borderBottomColor: themeTokens.forest } } },
    },
    MuiFilledInput: {
      styleOverrides: { underline: { '&:after': { borderBottomColor: themeTokens.forest } } },
    },
    MuiChip: {
      styleOverrides: {
        root: { borderRadius: 'var(--atlas-radius-pill)', fontWeight: 700 },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          border: `1px solid ${alpha(themeTokens.surfaceText, 0.18)}`,
          borderRadius: 'var(--atlas-radius-surface)',
          color: themeTokens.surfaceText,
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
          color: themeTokens.forestDark,
          fontWeight: 700,
        },
      },
    },
  },
});

export default appTheme;
