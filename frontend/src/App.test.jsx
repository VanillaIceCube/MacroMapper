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

  test('shows the protected Hello World page to signed-in users', async () => {
    sessionStorage.setItem('accessToken', 'token');
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Hello World' })).toBeInTheDocument();
    expect(screen.getByText('MacroMapper')).toBeInTheDocument();
  });
});
