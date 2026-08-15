import { apiFetch } from './requestClient';
import { forgotPassword, login, register, resetPassword } from './authApiClient';

vi.mock('./requestClient', () => ({
  apiFetch: vi.fn(),
}));

describe('authApiClient', () => {
  beforeEach(() => {
    apiFetch.mockResolvedValue({ ok: true });
  });

  test('login posts trimmed email credentials', async () => {
    await login({ email: ' user@example.com ', password: 'secret' });

    expect(apiFetch).toHaveBeenCalledWith('/auth/login/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'user@example.com', password: 'secret' }),
    });
  });

  test('register omits a blank optional username', async () => {
    await register({ email: 'user@example.com', username: ' ', password: 'secret' });

    expect(JSON.parse(apiFetch.mock.calls[0][1].body)).toEqual({
      email: 'user@example.com',
      password: 'secret',
    });
  });

  test('forgotPassword posts the email', async () => {
    await forgotPassword({ email: ' user@example.com ' });

    expect(apiFetch).toHaveBeenCalledWith(
      '/auth/forgot-password/',
      expect.objectContaining({ body: JSON.stringify({ email: 'user@example.com' }) }),
    );
  });

  test('resetPassword posts reset credentials', async () => {
    await resetPassword({ uid: 'uid', token: 'token', password: 'new-secret' });

    expect(apiFetch).toHaveBeenCalledWith(
      '/auth/reset-password/',
      expect.objectContaining({
        body: JSON.stringify({ uid: 'uid', token: 'token', password: 'new-secret' }),
      }),
    );
  });
});
