import { Box, Button, TextField, Typography } from '@mui/material';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import AuthPageShell from '../../components/AuthPageShell';
import { login } from '../../services/authApiClient';
import { formatAuthErrorMessage, persistAuthSession, readOkJson } from '../../services/authSession';

export default function Login({ showSnackbar }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

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
    try {
      const response = await login({ email, password });
      const data = await readOkJson(response, 'Login failed.');
      persistAuthSession(data);
      showSnackbar('success', `Welcome ${data.username || email.split('@')[0] || 'there'}!`);
      navigate('/');
    } catch (error) {
      showSnackbar('error', formatAuthErrorMessage(error, 'Login failed.'));
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
        <Button fullWidth type="submit" variant="contained">
          Login
        </Button>
        <Typography variant="caption" sx={{ textAlign: 'center', color: 'var(--atlas-ink-muted)' }}>
          <Box
            component="button"
            type="button"
            className="auth-link"
            onClick={() => navigate('/forgot-password')}
          >
            Forgot Password?
          </Box>
          {' · '}
          <Box
            component="button"
            type="button"
            className="auth-link"
            onClick={() => navigate('/register')}
          >
            Create Account
          </Box>
        </Typography>
      </Box>
    </AuthPageShell>
  );
}
