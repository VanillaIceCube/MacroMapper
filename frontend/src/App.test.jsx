import { render, screen } from '@testing-library/react';
import App from './App';

describe('App', () => {
  beforeEach(() => {
    sessionStorage.clear();
    window.history.replaceState({}, '', '/');
  });

  test('redirects signed-out users to login', async () => {
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Login' })).toBeInTheDocument();
  });

  test('shows the protected application shell to signed-in users', async () => {
    sessionStorage.setItem('accessToken', 'token');
    render(<App />);

    expect(await screen.findByText('Full Stack Template')).toBeInTheDocument();
    expect(screen.getByText(/Lorem ipsum dolor sit amet/)).toBeInTheDocument();
    expect(screen.getByLabelText('notifications')).toBeInTheDocument();
    expect(screen.getByLabelText('user profile')).toBeInTheDocument();
    expect(screen.getByLabelText('menu')).toBeInTheDocument();
  });
});
