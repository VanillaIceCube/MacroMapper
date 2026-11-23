import { connectionReturnTo } from '../../services/authRedirect';
import { TextField } from '@mui/material';
import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { login } from '../../services/authApiClient';
import { formatAuthErrorMessage } from '../../services/apiResponse';
import { startSession } from '../../services/sessionState';
import { useSessionGuard } from '../../hooks/useSession';
import AuthForm, { AuthLink } from '../../components/app-core/AuthForm';

export default function Login({ showSnackbar }) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();
  const isCurrentSession = useSessionGuard({ trackLocation: true });
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
    let acceptedResponse = false;
    try {
      const data = await login({ email, password });
      if (!isCurrentSession()) return;
      acceptedResponse = true;
      startSession(data);
      showSnackbar('success', `Welcome ${data.username || email.split('@')[0] || 'there'}!`);
      const next =
        import.meta.env.VITE_MCP_ENABLED === '1'
          ? connectionReturnTo(new URLSearchParams(location.search).get('next'))
          : null;
      navigate(next || '/');
    } catch (error) {
      // A session storage failure can also advance the session version.
      if (!acceptedResponse && !isCurrentSession()) return;
      showSnackbar('error', formatAuthErrorMessage(error, 'Login failed.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthForm
      title="Login"
      onSubmit={handleLogin}
      isSubmitting={isSubmitting}
      submitLabel={isSubmitting ? 'Logging in...' : 'Login'}
      footer={
        <>
          <AuthLink to="/forgot-password">Forgot Password?</AuthLink>
          {' · '}
          <AuthLink to="/register">Create Account</AuthLink>
        </>
      }
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
    </AuthForm>
  );
}
