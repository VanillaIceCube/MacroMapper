import { getSessionVersion } from './services/sessionState';
import useSession, { useSessionGuard } from './hooks/useSession';
import RouteContent from './components/app-core/RouteContent';
import { CssBaseline, ThemeProvider } from '@mui/material';
import { lazy, useCallback, useState } from 'react';
import { BrowserRouter as Router, Navigate, Route, Routes } from 'react-router';
import AppHeader from './components/app-core/AppHeader';
import AppNavigationDrawer from './components/app-core/AppNavigationDrawer';
import AppSnackbar from './components/app-core/AppSnackbar';
import AuthenticatedRoute from './components/app-core/AuthenticatedRoute';
import NavigationBridge from './components/app-core/NavigationBridge';
import appTheme from './theme';

const DiaryPage = lazy(() => import('./pages/DiaryPage'));
const ForgotPassword = lazy(() => import('./pages/authentication/ForgotPassword'));
const Login = lazy(() => import('./pages/authentication/Login'));
const Register = lazy(() => import('./pages/authentication/Register'));
const ResetPassword = lazy(() => import('./pages/authentication/ResetPassword'));
const ConnectedApps = lazy(() => import('./pages/connections/Connections'));
const OAuthConsent = lazy(() =>
  import('./pages/connections/Connections').then((module) => ({ default: module.OAuthConsent })),
);

function ApplicationSession({ showSnackbar }) {
  const isCurrentSession = useSessionGuard();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const showSessionSnackbar = (severity, message) => {
    if (isCurrentSession()) showSnackbar(severity, message);
  };

  return (
    <>
      <NavigationBridge />
      <AppHeader title="MacroMapper" setDrawerOpen={setDrawerOpen} />
      <AppNavigationDrawer open={drawerOpen} setOpen={setDrawerOpen} />
      <RouteContent>
        <Routes>
          {import.meta.env.VITE_MCP_ENABLED === '1' && (
            <>
              <Route
                path="/connections/authorize"
                element={
                  <AuthenticatedRoute>
                    <OAuthConsent />
                  </AuthenticatedRoute>
                }
              />
              <Route
                path="/connections"
                element={
                  <AuthenticatedRoute>
                    <ConnectedApps />
                  </AuthenticatedRoute>
                }
              />
            </>
          )}
          <Route path="/login" element={<Login showSnackbar={showSnackbar} />} />
          <Route path="/register" element={<Register showSnackbar={showSnackbar} />} />
          <Route path="/forgot-password" element={<ForgotPassword showSnackbar={showSnackbar} />} />
          <Route path="/reset-password" element={<ResetPassword showSnackbar={showSnackbar} />} />
          <Route
            path="/"
            element={
              <AuthenticatedRoute>
                <DiaryPage showSnackbar={showSessionSnackbar} />
              </AuthenticatedRoute>
            }
          />
          <Route
            path="/diary"
            element={
              <AuthenticatedRoute>
                <DiaryPage showSnackbar={showSessionSnackbar} />
              </AuthenticatedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </RouteContent>
    </>
  );
}

export default function App() {
  const { version } = useSession();
  const [snackbar, setSnackbar] = useState({ open: false, severity: 'info', message: '', version });
  const showSnackbar = useCallback((severity, message) => {
    setSnackbar({ open: true, severity, message, version: getSessionVersion() });
  }, []);
  return (
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <Router basename={import.meta.env.BASE_URL}>
        <ApplicationSession key={version} showSnackbar={showSnackbar} />
      </Router>
      <AppSnackbar
        open={snackbar.open && snackbar.version === version}
        severity={snackbar.severity}
        message={snackbar.message}
        onClose={(_event, reason) => {
          if (reason !== 'clickaway') setSnackbar((current) => ({ ...current, open: false }));
        }}
      />
    </ThemeProvider>
  );
}
