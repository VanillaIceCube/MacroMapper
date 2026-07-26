import { Box, Button, TextField, Typography } from '@mui/material';
import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import AuthPageShell from '../../components/AuthPageShell';
import { resetPassword } from '../../services/authApiClient';
import { readOkJson } from '../../services/authSession';

export default function ResetPassword({ showSnackbar }) {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const navigate = useNavigate();
  const location = useLocation();
  const params = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const uid = params.get('uid') || '';
  const token = params.get('token') || '';

  const handleSubmit = async () => {
    if (!uid || !token) {
      showSnackbar('error', 'Invalid or expired reset link.');
      return;
    }
    if (!password || password !== confirmPassword) {
      showSnackbar('error', 'Passwords do not match.');
      return;
    }

    try {
      const response = await resetPassword({ uid, token, password });
      const data = await readOkJson(response, 'Password reset failed.');
      showSnackbar('success', data?.message || 'Password reset successful.');
      navigate('/login');
    } catch (error) {
      const isNetworkError =
        error instanceof TypeError || error?.message?.toLowerCase().includes('network');
      showSnackbar(
        'error',
        isNetworkError ? 'Network error.' : error?.message || 'Password reset failed.',
      );
    }
  };

  return (
    <AuthPageShell title="Choose a new password">
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
          label="New Password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <TextField
          fullWidth
          sx={{ background: 'white' }}
          label="Confirm Password"
          type="password"
          autoComplete="new-password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
        />
        <Button
          fullWidth
          sx={{ backgroundColor: 'var(--secondary-color)' }}
          type="submit"
          variant="contained"
        >
          Reset Password
        </Button>
        <Typography variant="caption" sx={{ textAlign: 'center' }}>
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
