import { TextField } from '@mui/material';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { register } from '../../services/authApiClient';
import { formatAuthErrorMessage } from '../../services/apiResponse';
import { startSession } from '../../services/sessionState';
import { useSessionGuard } from '../../hooks/useSession';
import AuthForm, { AuthLink } from '../../components/app-core/AuthForm';

export default function Register({ showSnackbar }) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const navigate = useNavigate();
  const isCurrentSession = useSessionGuard({ trackLocation: true });

  const handleRegister = async () => {
    if (isSubmitting) return;
    if (!password || password !== confirmPassword) {
      showSnackbar('error', 'Passwords do not match.');
      return;
    }

    setIsSubmitting(true);
    let acceptedResponse = false;
    try {
      const data = await register({ email, username, password });
      if (!isCurrentSession()) return;
      acceptedResponse = true;
      startSession(data);
      showSnackbar('success', 'Account created! Welcome to MacroMapper!');
      navigate('/');
    } catch (error) {
      // A session storage failure can also advance the session version.
      if (!acceptedResponse && !isCurrentSession()) return;
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
