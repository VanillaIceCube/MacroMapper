import { Navigate } from 'react-router';

export default function AuthenticatedRoute({ children }) {
  const token = sessionStorage.getItem('accessToken');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
}
