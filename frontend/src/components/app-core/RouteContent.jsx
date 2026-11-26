import { Component, Suspense } from 'react';
import { Box, Button, Typography } from '@mui/material';
import { useLocation } from 'react-router';
import { browserLocation } from '../../services/navigation/navigationService';

class PageErrorBoundary extends Component {
  state = { failed: false, routeKey: null };

  static getDerivedStateFromProps({ routeKey }, state) {
    return routeKey !== state.routeKey ? { failed: false, routeKey } : null;
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <Box role="alert" sx={{ p: 3 }}>
          <Typography>This page could not be loaded.</Typography>
          <Button variant="contained" sx={{ mt: 2 }} onClick={browserLocation.reload}>
            Reload page
          </Button>
        </Box>
      );
    }
    return this.props.children;
  }
}

export default function RouteContent({ children }) {
  const location = useLocation();
  return (
    <PageErrorBoundary routeKey={`${location.pathname}${location.search}${location.hash}`}>
      <Suspense
        fallback={
          <Box role="status" sx={{ p: 3 }}>
            Loading page…
          </Box>
        }
      >
        {children}
      </Suspense>
    </PageErrorBoundary>
  );
}
