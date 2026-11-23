import { Fragment } from 'react';
import useSession from '../../hooks/authentication/useSession';
import { Navigate, useLocation } from 'react-router';
import { loginPath } from '../../services/authentication/authRedirect';

export default function AuthenticatedRoute({ children }) {
  const location = useLocation();
  const session = useSession();
  if (!session.accessToken) {
    const returnTo =
      import.meta.env.VITE_MCP_ENABLED === '1' ? `${location.pathname}${location.search}` : null;
    return <Navigate to={loginPath(returnTo)} replace />;
  }
  return <Fragment key={session.version}>{children}</Fragment>;
}
