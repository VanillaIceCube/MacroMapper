# 🎨 MacroMapper Frontend (React)
MacroMapper's frontend is a Vite-powered React 19 single-page application built
with Material UI and React Router 7. It will provide an individual meal and
activity diary, source-aware GPT meal proposals, nutrition goals, and trend
reporting with MacroMapper's dark, pale-yellow, amber, and gray visual theme.

The current implementation is the authenticated application shell that those
features will build on. See the [product vision](../docs/PRODUCT_VISION.md) for
the planned user experience and release sequence.

## 🧭 Routes
- `/login`: email and password login
- `/register`: account creation with an optional username
- `/forgot-password`: password-reset email request
- `/reset-password?uid=...&token=...`: choose a new password
- `/`: protected MacroMapper dashboard and product-status overview
- `/diary`: protected dated meal diary with daily nutrition totals
- Any unknown route resolves to the protected home page

Signed-out users who request a protected route are redirected to `/login`.

## 🔐 Authentication And Shell Behavior
- Access and refresh tokens are stored in `sessionStorage`.
- The profile name and email are stored for the app header.
- API requests that receive a `401` attempt one refresh-token exchange.
- An invalid refresh token clears the session and redirects to login.
- Login and registration navigate directly to the protected home page.
- The app header title is `MacroMapper`.
- The header provides MacroMapper navigation, recipient-scoped
  notifications, profile display, and logout action.
- The drawer contains the Home destination and MacroMapper product description.
- The drawer links to the responsive meal diary, where users can search the
  visible catalog, create a personal food, add/remove foods, change quantities,
  inspect saved composite ingredients, and create, edit, or delete meals.

## ✨ Planned Product Surfaces

The authenticated shell now includes the daily diary and Food Item search and
creation needed for manual meal logging. It will grow to include an AI
meal-review flow, nutrition and activity goals, and trends. The Home page is an
intentional MacroMapper dashboard that distinguishes active account
capabilities from product features still on the roadmap.

Authentication endpoint functions live in `src/services/authApiClient.js`.
Notification functions live in `src/services/notificationApiClient.js`. Token
refresh and unauthorized-response behavior live in
`src/services/requestClient.js`.
Meal, daily-total, catalog-search, and personal-food requests live in
`src/services/mealApiClient.js`.

## 💻 Local Setup
The checked-in frontend dependencies require Node.js 24.15 or newer. CI reads
that range from `package.json`, and the production Docker image uses Node.js 26.

```powershell
npm ci
npm start
```

Open the development frontend at
`http://macromapper.localhost:3000`. The development API default is
`http://localhost:8000`. Override it with:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Production builds should normally leave `VITE_API_BASE_URL` blank so
`/auth/...` and `/api/...` requests use the current origin.

Vite exposes client-side variables only when they use the `VITE_` prefix. The
production frontend image uses `nginx.conf` to serve Vite's `dist` directory
and forward `/auth/`, `/api/`, and `/admin/` to the Compose backend service.

## Docker Hot Reload
From the repository root, run:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml up --build -d
```

The development image uses `Dockerfile.dev`, mounts `frontend/`, and keeps
`node_modules` in a Docker volume. Vite watches the mounted source and reloads
without rebuilding the production image. Open
`http://macromapper.localhost:3000`; the development API runs at
`http://macromapper.localhost:8000`. Both ports are localhost-only by
default and can be changed with the `MACROMAPPER_DEV_*_PORT` variables
in `deploy/.env`.

## 🧰 Checks
```powershell
npm test
npm run test:watch
npm run lint:strict
npm run format:check
npm run build
```
