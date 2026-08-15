# 🎨 MacroMapper Frontend (React)
MacroMapper's frontend is a React 19 single-page application built with
Material UI and React Router. It will provide an individual meal and activity
diary, source-aware GPT meal proposals, nutrition goals, and trend reporting.

The current implementation is the authenticated application shell that those
features will build on. See the [product vision](../docs/PRODUCT_VISION.md) for
the planned user experience and release sequence.

## 🧭 Routes
- `/login`: email and password login
- `/register`: account creation with an optional username
- `/forgot-password`: password-reset email request
- `/reset-password?uid=...&token=...`: choose a new password
- `/`: protected application shell with one placeholder Paper
- Any unknown route resolves to the protected home page

Signed-out users who request a protected route are redirected to `/login`.

## 🔐 Authentication And Shell Behavior
- Access and refresh tokens are stored in `sessionStorage`.
- The profile name and email are stored for the app header.
- API requests that receive a `401` attempt one refresh-token exchange.
- An invalid refresh token clears the session and redirects to login.
- Login and registration navigate directly to the protected home page.
- The app header title is `MacroMapper`.
- The header retains the generic navigation drawer, recipient-scoped
  notifications, profile display, and logout action.
- The drawer contains one Home destination and placeholder copy for future
  application navigation.

## ✨ Planned Product Surfaces

The authenticated shell will grow to include a daily diary, Food Item search
and editing, an AI meal-review flow, nutrition and activity goals, and trends.
These are planned features; the current Home page remains a placeholder until
their corresponding backend APIs and user flows are implemented.

Authentication endpoint functions live in `src/services/authApiClient.js`.
Notification functions live in `src/services/notificationApiClient.js`. Token
refresh and unauthorized-response behavior live in
`src/services/requestClient.js`.

## 💻 Local Setup
The checked-in frontend dependencies require Node.js 25, matching
`package.json`, CI, and the production Docker image.

```powershell
npm ci
npm start
```

Open the development frontend at
`http://macromapper.localhost:3000`. The development API default is
`http://localhost:8000`. Override it with:

```env
REACT_APP_API_BASE_URL=http://localhost:8000
```

Production builds should normally leave `REACT_APP_API_BASE_URL` blank so
`/auth/...` and `/api/...` requests use the current origin.

The production frontend image uses `nginx.conf` to serve the CRA `build`
directory and forward `/auth/`, `/api/`, and `/admin/` to the Compose backend
service.

## Docker Hot Reload
From the repository root, run:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml up --build -d
```

The development image uses `Dockerfile.dev`, mounts `frontend/`, and keeps
`node_modules` in a Docker volume. React watches the mounted source and reloads
without rebuilding the production image. Open
`http://macromapper.localhost:3000`; the development API runs at
`http://macromapper.localhost:8000`. Both ports are localhost-only by
default and can be changed with the `MACROMAPPER_DEV_*_PORT` variables
in `deploy/.env`.

## 🧰 Checks
```powershell
npm test -- --runInBand
npm run lint:strict
npm run format:check
npm run build
```
