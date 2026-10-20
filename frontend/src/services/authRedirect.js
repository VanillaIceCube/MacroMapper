// Only the two connection pages can override the existing post-login landing.
export function connectionReturnTo(value) {
  if (typeof value !== 'string' || !value.startsWith('/')) return null;
  try {
    const url = new URL(value, 'https://application.invalid');
    if (
      url.origin === 'https://application.invalid' &&
      ['/connections', '/connections/authorize'].includes(url.pathname)
    ) {
      return `${url.pathname}${url.search}`;
    }
  } catch (_err) {
    // Invalid or external destinations fall back to the usual application landing.
  }
  return null;
}

export function loginPath(returnTo) {
  const destination = connectionReturnTo(returnTo);
  return destination ? `/login?next=${encodeURIComponent(destination)}` : '/login';
}
