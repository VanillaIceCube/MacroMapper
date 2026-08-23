# 🎨 MacroMapper Frontend (React)
MacroMapper's frontend is a Vite-powered React 19 single-page application built
with Material UI and React Router 8. It will provide an individual meal and
activity diary, source-aware GPT meal proposals, nutrition goals, and trend
reporting through MacroMapper's warm, editorial Field Atlas visual system.

The current implementation includes the authenticated application shell,
private meal diary, and GPT-assisted estimate-review flow. See the
[product vision](../docs/PRODUCT_VISION.md) for the remaining user experience
and release sequence.

## 🧭 Visual system

The frontend uses the Field Atlas direction described in
[`docs/design/FIELD_ATLAS.md`](../docs/design/FIELD_ATLAS.md). Shared theme
configuration lives in `src/theme.js`, with matching semantic CSS tokens in
`src/App.css`.

- Bone and warm paper surfaces keep the application calm and editorial.
- Midnight ink provides text and structural contrast.
- Forest marks primary actions and confirmed states, Persimmon marks editable
  estimates, and Mineral blue supports neutral nutrition and activity data.
- Nutrition data uses Midnight ink for calories, Forest for protein, dark
  Mineral for carbohydrates, and Persimmon for fat.
- Newsreader supplies editorial headings; Inter is used for controls, labels,
  navigation, and body copy.
- Color is always paired with labels, icons, borders, or other non-color cues.

See [`STYLE_GUIDE.md`](STYLE_GUIDE.md) before adding or restyling frontend
components.

## 🧭 Routes
- `/login`: email and password login
- `/register`: account creation with an optional username
- `/forgot-password`: password-reset email request
- `/reset-password?uid=...&token=...`: choose a new password
- `/`: protected MacroMapper dashboard and product-status overview
- `/diary`: protected dated meal diary with daily nutrition totals
- Any unknown route resolves to the protected home page

Signed-out users who request a protected route are redirected to `/login`.

The diary offers manual entry and an **Estimate meal** path. Estimation resolves
multiple typo-tolerant food and quantity matches from the visible catalog by
complete food clause, then requests sourced GPT items only for clauses that
remain unresolved. Partial catalog candidates cannot silently discard a
product-defining term or be combined with an AI replacement for the same food.
Users must review the persisted draft before saving: they can rename the meal,
switch between validated unit/portion options, adjust the amount without
changing the nutritional basis, remove ingredients, and add catalog foods.
Official/verified, catalog-estimate, AI-estimate, and **AI estimate — adjusted
by you** labels always accompany their sources and confidence rather than
relying on color alone. Initial AI definitions are reusable shared catalog
foods; substantive review edits are saved as private versions derived from the
shared base.

React Router 8 requires no production routing API changes in MacroMapper. The
application already imports its DOM routing APIs from `react-router` rather than
the removed `react-router-dom` compatibility package. The test wrapper no
longer passes the v7 future flags, whose behavior is standard in v8, and the
application integration tests cover browser-router navigation, protected
redirects, and unknown-route fallback behavior.

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
