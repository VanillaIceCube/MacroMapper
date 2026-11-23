import { TextField } from '@mui/material';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { register } from '../../services/authApiClient';
import { formatAuthErrorMessage, persistAuthSession } from '../../services/authSession';
import AuthForm, { AuthLink } from './AuthForm';

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
      const data = await register({ email, username, password });
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
    <AuthForm
      title="Create account"
      onSubmit={handleRegister}
      isSubmitting={isSubmitting}
      submitLabel={isSubmitting ? 'Registering...' : 'Register'}
      footer={
        <>
          Already have an account? <AuthLink to="/login">Sign in</AuthLink>
        </>
      }
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
    </AuthForm>
  );
}
