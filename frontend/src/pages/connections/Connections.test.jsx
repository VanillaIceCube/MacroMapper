import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes, useLocation } from 'react-router';
import { renderWithProviders } from '../../test-support/utils';
import AuthenticatedRoute from '../../components/AuthenticatedRoute';
import ConnectedApps, { OAuthConsent } from './Connections';
import Login from '../authentication/Login';
import * as connections from '../../services/connectionsClient';
import { login } from '../../services/authApiClient';

vi.mock('../../services/connectionsClient');
vi.mock('../../services/authApiClient', () => ({ login: vi.fn() }));

const query =
  '?client_id=sample-chatgpt&state=a%26b%3D%3F&resource=https%3A%2F%2Fsample.example%2Fmcp';
const readDescription = 'Check this connection; no application data access';
const consent = {
  application: { name: 'Sample application for ChatGPT', client_id: 'sample-chatgpt' },
  user: { username: 'alice' },
  permissions: [{ scope: 'sample:connect', description: readDescription }],
  ticket: 'SIGNED-CONSENT',
};

function LocationDisplay() {
  const location = useLocation();
  return (
    <div data-testid="location">
      {location.pathname}
      {location.search}
    </div>
  );
}

function renderFlow(route = `/connections/authorize${query}`) {
  return renderWithProviders(
    <>
      <Routes>
        <Route path="/" element={<div>Home</div>} />
        <Route
          path="/connections/authorize"
          element={
            <AuthenticatedRoute>
              <OAuthConsent />
            </AuthenticatedRoute>
          }
        />
        <Route
          path="/connections"
          element={
            <AuthenticatedRoute>
              <ConnectedApps />
            </AuthenticatedRoute>
          }
        />
        <Route path="/login" element={<Login showSnackbar={vi.fn()} />} />
      </Routes>
      <LocationDisplay />
    </>,
    { routeEntries: [route] },
  );
}

beforeEach(() => {
  vi.stubEnv('VITE_MCP_ENABLED', '1');
  vi.clearAllMocks();
  sessionStorage.clear();
  sessionStorage.setItem('accessToken', 'JWT');
  connections.loadConsent.mockResolvedValue(consent);
  connections.decideConsent.mockResolvedValue({
    redirect_url: 'https://chatgpt.com/callback?code=CODE&state=STATE',
  });
  connections.loadConnections.mockResolvedValue({
    applications: [{ id: 1, name: 'ChatGPT', client_id: 'gpt' }],
  });
  connections.revokeConnection.mockResolvedValue({ revoked: true });
  login.mockResolvedValue({
    ok: true,
    json: async () => ({ access: 'NEW-JWT', refresh: 'REFRESH', username: 'alice' }),
  });
});

test('an authenticated user goes directly to consent with application, identity and permissions', async () => {
  renderFlow();
  expect(await screen.findByText('Signed in as alice')).toBeInTheDocument();
  expect(screen.getByText('Sample application for ChatGPT')).toBeInTheDocument();
  expect(screen.getByText('Application ID: sample-chatgpt')).toBeInTheDocument();
  expect(screen.getByText(readDescription)).toBeInTheDocument();
  expect(connections.loadConsent).toHaveBeenCalledWith(query);
  expect(login).not.toHaveBeenCalled();
});

test('signed-out users use existing login, preserve the exact request, and return to consent', async () => {
  sessionStorage.clear();
  renderFlow();
  expect(screen.getByTestId('location')).toHaveTextContent(
    `/login?next=${encodeURIComponent(`/connections/authorize${query}`)}`,
  );
  expect(connections.loadConsent).not.toHaveBeenCalled();
  await userEvent.type(screen.getByLabelText('Email'), 'alice@example.com');
  await userEvent.type(screen.getByLabelText('Password'), 'password');
  await userEvent.click(screen.getByRole('button', { name: 'Login' }));
  expect(await screen.findByText('Signed in as alice')).toBeInTheDocument();
  expect(screen.getByTestId('location')).toHaveTextContent(`/connections/authorize${query}`);
  expect(sessionStorage.getItem('accessToken')).toBe('NEW-JWT');
});

test('an external login next parameter cannot redirect the user off-site', async () => {
  sessionStorage.clear();
  renderFlow('/login?next=https%3A%2F%2Fattacker.example%2Fconnections');
  await userEvent.type(screen.getByLabelText('Email'), 'alice@example.com');
  await userEvent.type(screen.getByLabelText('Password'), 'password');
  await userEvent.click(screen.getByRole('button', { name: 'Login' }));
  await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(/^\/$/));
  expect(connections.loadConsent).not.toHaveBeenCalled();
  expect(connections.followOAuthCallback).not.toHaveBeenCalled();
});

test.each([
  ['Allow', 'allow'],
  ['Cancel', 'cancel'],
])('%s submits the signed request and follows the Django callback', async (label, decision) => {
  renderFlow();
  await screen.findByText('Signed in as alice');
  await userEvent.click(screen.getByRole('button', { name: label }));
  await waitFor(() =>
    expect(connections.followOAuthCallback).toHaveBeenCalledWith(
      'https://chatgpt.com/callback?code=CODE&state=STATE',
    ),
  );
  expect(connections.decideConsent).toHaveBeenCalledWith('SIGNED-CONSENT', decision, query);
});

test('invalid consent shows an error and cannot authorize an application', async () => {
  connections.loadConsent.mockRejectedValue(new Error('Invalid redirect URI.'));
  renderFlow();
  expect(await screen.findByRole('alert')).toHaveTextContent('Invalid redirect URI.');
  expect(screen.queryByRole('button', { name: 'Allow' })).not.toBeInTheDocument();
  expect(connections.followOAuthCallback).not.toHaveBeenCalled();
});

test('failed approval displays the server error without following a callback', async () => {
  connections.decideConsent.mockRejectedValue(new Error('invalid_consent'));
  renderFlow();
  await screen.findByText('Signed in as alice');
  await userEvent.click(screen.getByRole('button', { name: 'Allow' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('invalid_consent');
  expect(connections.followOAuthCallback).not.toHaveBeenCalled();
});

test('Connected Apps lists and revokes an application', async () => {
  renderFlow('/connections');
  await userEvent.click(await screen.findByRole('button', { name: 'Revoke ChatGPT' }));
  expect(await screen.findByText('No connected apps.')).toBeInTheDocument();
  expect(connections.revokeConnection).toHaveBeenCalledWith(1);
});

test('Connected Apps can revoke a pending-only authorization before token exchange', async () => {
  connections.loadConnections.mockResolvedValue({
    applications: [{ id: 7, name: 'Pending app', client_id: 'pending-client' }],
  });
  renderFlow('/connections');
  expect(await screen.findByText('pending-client')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Revoke Pending app' }));
  expect(await screen.findByText('No connected apps.')).toBeInTheDocument();
  expect(connections.revokeConnection).toHaveBeenCalledWith(7);
});

test('failed revocation keeps the connection visible', async () => {
  connections.revokeConnection.mockRejectedValue(new Error('Network error'));
  renderFlow('/connections');
  await userEvent.click(await screen.findByRole('button', { name: 'Revoke ChatGPT' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Network error');
  expect(screen.getByText('ChatGPT')).toBeInTheDocument();
});

afterEach(() => vi.unstubAllEnvs());
