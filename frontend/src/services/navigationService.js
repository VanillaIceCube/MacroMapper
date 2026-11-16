// Native browser actions remain separate from React Router navigation.
export const browserLocation = { reload: () => window.location.reload() };

let navigateImpl = null;

export function setNavigate(navigate) {
  navigateImpl = typeof navigate === 'function' ? navigate : null;
}

export function clearNavigate() {
  navigateImpl = null;
}

export function navigate(to, options) {
  if (!navigateImpl) return false;
  navigateImpl(to, options);
  return true;
}
