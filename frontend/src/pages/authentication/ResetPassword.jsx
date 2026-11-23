import { TextField } from '@mui/material';
import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { resetPassword } from '../../services/authApiClient';
import { formatAuthErrorMessage } from '../../services/authSession';
import AuthForm, { AuthLink } from './AuthForm';

export default function ResetPassword({ showSnackbar }) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const navigate = useNavigate();
  const location = useLocation();
  const params = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const uid = params.get('uid') || '';
  const token = params.get('token') || '';

  const handleSubmit = async () => {
    if (isSubmitting) return;
    if (!uid || !token) {
      showSnackbar('error', 'Invalid or expired reset link.');
      return;
    }
    if (!password || password !== confirmPassword) {
      showSnackbar('error', 'Passwords do not match.');
      return;
    }

    setIsSubmitting(true);
    try {
      const data = await resetPassword({ uid, token, password });
      showSnackbar('success', data?.message || 'Password reset successful.');
      navigate('/login');
    } catch (error) {
      showSnackbar('error', formatAuthErrorMessage(error, 'Password reset failed.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthForm
      title="Choose a new password"
      onSubmit={handleSubmit}
      isSubmitting={isSubmitting}
      submitLabel={isSubmitting ? 'Resetting...' : 'Reset Password'}
      footer={<AuthLink to="/login">Back to Login</AuthLink>}
    >
      <TextField
        fullWidth
        label="New Password"
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
    </AuthForm>
  );
}
