import { Box, Button, TextField, Typography } from '@mui/material';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import AuthPageShell from '../../components/AuthPageShell';
import { forgotPassword } from '../../services/authApiClient';
import { formatAuthErrorMessage, readOkJson } from '../../services/authSession';

export default function ForgotPassword({ showSnackbar }) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [email, setEmail] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      const response = await forgotPassword({ email });
      const data = await readOkJson(response, 'Password reset request failed.');
      showSnackbar(
        'success',
        data?.message || 'If that account exists, we sent a password reset link.',
      );
      navigate('/login');
    } catch (error) {
      showSnackbar('error', formatAuthErrorMessage(error, 'Password reset request failed.'));
    } finally {
      setIsSubmitting(false);
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
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <Button fullWidth type="submit" disabled={isSubmitting} variant="contained">
          {isSubmitting ? 'Sending...' : 'Send Reset Link'}
        </Button>
        <Typography variant="caption" sx={{ textAlign: 'center', color: 'var(--atlas-ink-muted)' }}>
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
