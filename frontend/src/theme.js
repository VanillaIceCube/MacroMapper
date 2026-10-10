import { alpha, createTheme } from '@mui/material/styles';

export const fieldAtlasTokens = {
  bone: '#F6F1E7',
  paper: '#FFFDF8',
  ink: '#17324D',
  inkMuted: '#52687A',
  forest: '#2E6B4F',
  forestDark: '#23513C',
  persimmon: '#E46B3C',
  persimmonDark: '#A94420',
  mineral: '#A9CAD4',
  mineralDark: '#47798A',
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
    borderRadius: 12,
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
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: {
          minHeight: 44,
          borderRadius: 12,
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
          '&.Mui-focused fieldset': { borderWidth: 2 },
        },
      },
    },
    MuiInputLabel: {
      styleOverrides: {
        root: { color: fieldAtlasTokens.inkMuted },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { borderRadius: 999, fontWeight: 700 },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          border: `1px solid ${alpha(fieldAtlasTokens.ink, 0.18)}`,
          borderRadius: 12,
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
