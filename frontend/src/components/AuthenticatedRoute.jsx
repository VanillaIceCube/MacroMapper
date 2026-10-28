import { Navigate, useLocation } from 'react-router';
import { loginPath } from '../services/authRedirect';

export default function AuthenticatedRoute({ children }) {
  const location = useLocation();
  const token = sessionStorage.getItem('accessToken');
  if (!token) {
    const returnTo =
      import.meta.env.VITE_MCP_ENABLED === '1' ? `${location.pathname}${location.search}` : null;
    return <Navigate to={loginPath(returnTo)} replace />;
  }
  return children;
}
