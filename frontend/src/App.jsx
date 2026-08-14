import './App.css';
import { useState } from 'react';
import { BrowserRouter as Router, Navigate, Route, Routes } from 'react-router-dom';
import AppHeader from './components/AppHeader';
import AppNavigationDrawer from './components/AppNavigationDrawer';
import AppSnackbar from './components/AppSnackbar';
import AuthenticatedRoute from './components/AuthenticatedRoute';
import NavigationBridge from './components/NavigationBridge';
import HomePage from './pages/HomePage';
import ForgotPassword from './pages/authentication/ForgotPassword';
import Login from './pages/authentication/Login';
import Register from './pages/authentication/Register';
import ResetPassword from './pages/authentication/ResetPassword';

function Protected({ children }) {
  return <AuthenticatedRoute>{children}</AuthenticatedRoute>;
}

export default function App() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, severity: 'info', message: '' });

  const showSnackbar = (severity, message) => {
    setSnackbar({ open: true, severity, message });
  };

  return (
    <>
      <Router
        basename={process.env.PUBLIC_URL || '/'}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <NavigationBridge />
        <AppHeader title="Full Stack Template" setDrawerOpen={setDrawerOpen} />
        <AppNavigationDrawer open={drawerOpen} setOpen={setDrawerOpen} />
        <Routes>
          <Route path="/login" element={<Login showSnackbar={showSnackbar} />} />
          <Route path="/register" element={<Register showSnackbar={showSnackbar} />} />
          <Route path="/forgot-password" element={<ForgotPassword showSnackbar={showSnackbar} />} />
          <Route path="/reset-password" element={<ResetPassword showSnackbar={showSnackbar} />} />
          <Route
            path="/"
            element={
              <Protected>
                <HomePage />
              </Protected>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
      <AppSnackbar
        open={snackbar.open}
        severity={snackbar.severity}
        message={snackbar.message}
        onClose={(_event, reason) => {
          if (reason !== 'clickaway') {
            setSnackbar((current) => ({ ...current, open: false }));
          }
        }}
      />
    </>
  );
}
