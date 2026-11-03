import { Box, Button, TextField, Typography } from '@mui/material';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import AuthPageShell from '../../components/AuthPageShell';
import { register } from '../../services/authApiClient';
import { formatAuthErrorMessage, persistAuthSession, readOkJson } from '../../services/authSession';

export default function Register({ showSnackbar }) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const navigate = useNavigate();

  const handleRegister = async () => {
    if (isSubmitting) return;
    if (!password || password !== confirmPassword) {
      showSnackbar('error', 'Passwords do not match.');
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await register({ email, username, password });
      const data = await readOkJson(response, 'Registration failed.');
      persistAuthSession(data);
      showSnackbar('success', 'Account created! Welcome to MacroMapper!');
      navigate('/');
    } catch (error) {
      showSnackbar('error', formatAuthErrorMessage(error, 'Registration failed.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthPageShell title="Create account">
      <Box
        component="form"
        sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
        onSubmit={(event) => {
          event.preventDefault();
          handleRegister();
        }}
      >
        <TextField
          fullWidth
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <TextField
          fullWidth
          label="Username (optional)"
          autoComplete="username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
        />
        <TextField
          fullWidth
          label="Password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <TextField
          fullWidth
          label="Confirm Password"
          type="password"
          autoComplete="new-password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
        />
        <Button fullWidth type="submit" disabled={isSubmitting} variant="contained">
          {isSubmitting ? 'Registering...' : 'Register'}
        </Button>
        <Typography variant="caption" sx={{ textAlign: 'center', color: 'var(--atlas-ink-muted)' }}>
          Already have an account?{' '}
          <Box
            component="button"
            type="button"
            className="auth-link"
            onClick={() => navigate('/login')}
          >
            Sign in
          </Box>
        </Typography>
      </Box>
    </AuthPageShell>
  );
}
