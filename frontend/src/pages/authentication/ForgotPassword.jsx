import { Box, Button, TextField, Typography } from '@mui/material';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AuthPageShell from '../../components/AuthPageShell';
import { forgotPassword } from '../../services/authApiClient';
import { readOkJson } from '../../services/authSession';

export default function ForgotPassword({ showSnackbar }) {
  const [email, setEmail] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async () => {
    try {
      const response = await forgotPassword({ email });
      const data = await readOkJson(response, 'Password reset request failed.');
      showSnackbar(
        'success',
        data?.message || 'If that account exists, we sent a password reset link.',
      );
      navigate('/login');
    } catch (error) {
      const isNetworkError =
        error instanceof TypeError || error?.message?.toLowerCase().includes('network');
      showSnackbar(
        'error',
        isNetworkError ? 'Network error.' : error?.message || 'Password reset request failed.',
      );
    }
  };

  return (
    <AuthPageShell title="Reset your password">
      <Box
        component="form"
        sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
        onSubmit={(event) => {
          event.preventDefault();
          handleSubmit();
        }}
      >
        <TextField
          fullWidth
          sx={{ background: 'white' }}
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <Button
          fullWidth
          sx={{ backgroundColor: 'var(--secondary-color)' }}
          type="submit"
          variant="contained"
        >
          Send Reset Link
        </Button>
        <Typography variant="caption" sx={{ textAlign: 'center', color: 'var(--secondary-color)' }}>
          <Box
            component="button"
            type="button"
            className="auth-link"
            onClick={() => navigate('/login')}
          >
            Back to Login
          </Box>
        </Typography>
      </Box>
    </AuthPageShell>
  );
}
