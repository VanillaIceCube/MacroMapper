import { TextField } from '@mui/material';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { forgotPassword } from '../../services/authApiClient';
import { formatAuthErrorMessage } from '../../services/authSession';
import AuthForm, { AuthLink } from '../../components/app-core/AuthForm';

export default function ForgotPassword({ showSnackbar }) {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [email, setEmail] = useState('');

  const handleSubmit = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      const data = await forgotPassword({ email });
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
    <AuthForm
      title="Reset your password"
      onSubmit={handleSubmit}
      isSubmitting={isSubmitting}
      submitLabel={isSubmitting ? 'Sending...' : 'Send Reset Link'}
      footer={<AuthLink to="/login">Back to Login</AuthLink>}
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
    </AuthForm>
  );
}
