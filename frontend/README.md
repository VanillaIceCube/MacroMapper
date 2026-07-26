# MacroMapper frontend

The frontend is a Vite-powered React 19 single-page application built with Material UI and React Router.

## Routes

- `/login`: email and password login
- `/register`: account creation with an optional username
- `/forgot-password`: password-reset email request
- `/reset-password?uid=...&token=...`: choose a new password
- `/`: protected starter page displaying `Hello World`
- Any other route currently resolves to the protected starter page

Signed-out users who request a protected route are redirected to `/login`.

## Authentication behavior

- Access and refresh tokens are stored in `sessionStorage`.
- The profile name and email are stored for the app header.
- API requests that receive a `401` attempt one refresh-token exchange.
- An invalid refresh token clears the session and redirects to login.
- Login and registration navigate directly to the protected home page.
- The app header provides the current profile and logout action.

Authentication endpoint functions live in `src/services/authApiClient.js`. Token refresh and unauthorized-response behavior live in `src/services/requestClient.js`.

## Local setup

```powershell
npm ci
npm start
```

The development API default is `http://localhost:8000`. Override it with:

```env
REACT_APP_API_BASE_URL=http://localhost:8000
```

Production builds should normally leave `REACT_APP_API_BASE_URL` blank so `/auth/...` requests use the current origin.

The production frontend image uses `nginx.conf` to serve the SPA and forward
`/auth/`, `/api/`, and `/admin/` to the Compose `backend` service. This keeps
same-origin API requests working when the frontend container is accessed
directly as well as through the origin proxy.

## Checks

```powershell
npm test
npm run lint:strict
npm run format:check
npm run build
```
