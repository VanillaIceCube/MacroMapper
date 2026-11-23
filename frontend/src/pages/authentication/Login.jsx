import { connectionReturnTo } from '../../services/authRedirect';
import { Box, Button, TextField, Typography } from '@mui/material';
import { useEffect, useState } from 'react';
import { Link as RouterLink, useLocation, useNavigate } from 'react-router';
import AuthPageShell from '../../components/AuthPageShell';
import { login } from '../../services/authApiClient';
import { formatAuthErrorMessage, persistAuthSession } from '../../services/authSession';

export default function Login({ showSnackbar }) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const raw = sessionStorage.getItem('pendingSnackbar');
    if (!raw) return;

    sessionStorage.removeItem('pendingSnackbar');
    try {
      const payload = JSON.parse(raw);
      showSnackbar(payload?.severity || 'error', payload?.message || 'Please log in again.');
    } catch (_err) {
      showSnackbar('error', 'Please log in again.');
    }
  }, [showSnackbar]);

  const handleLogin = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      const data = await login({ email, password });
      persistAuthSession(data);
      showSnackbar('success', `Welcome ${data.username || email.split('@')[0] || 'there'}!`);
      const next =
        import.meta.env.VITE_MCP_ENABLED === '1'
          ? connectionReturnTo(new URLSearchParams(location.search).get('next'))
          : null;
      navigate(next || '/');
    } catch (error) {
      showSnackbar('error', formatAuthErrorMessage(error, 'Login failed.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthPageShell title="Login">
      <Box
        component="form"
        autoComplete="on"
        sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
        onSubmit={(event) => {
          event.preventDefault();
          handleLogin();
        }}
      >
        <TextField
          fullWidth
          label="Email"
          type="email"
          name="email"
          autoComplete="username"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <TextField
          fullWidth
          label="Password"
          type="password"
          name="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <Button fullWidth type="submit" disabled={isSubmitting} variant="contained">
          {isSubmitting ? 'Logging in...' : 'Login'}
        </Button>
        <Typography variant="caption" sx={{ textAlign: 'center', color: 'var(--atlas-ink-muted)' }}>
          <Box component={RouterLink} className="auth-link" to="/forgot-password">
            Forgot Password?
          </Box>
          {' · '}
          <Box component={RouterLink} className="auth-link" to="/register">
            Create Account
          </Box>
        </Typography>
      </Box>
    </AuthPageShell>
  );
}
