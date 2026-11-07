# 🎨 MacroMapper Frontend (React)

Production release ownership: use the [app-only release/recovery guide](../deploy/production/README.md).

MacroMapper's frontend is a Vite-powered React 19 single-page application built
with Material UI and React Router 8. It will provide an individual meal and
activity diary, source-aware GPT meal proposals, nutrition goals, and trend
reporting through MacroMapper's warm, editorial Field Atlas visual system.

The current implementation includes the authenticated application shell,
private meal diary, and GPT-assisted estimate-review flow. See the
[product vision](../docs/PRODUCT_VISION.md) for the remaining user experience
and release sequence.

AI estimation can take up to two minutes; the dialog explains the wait and keeps
the description when the backend returns a safe timeout error. Both the local
frontend image's API proxy and the production Infrastructure gateway allow
120 seconds, with a 110-second total AI budget in Django.

## 🧭 Visual system

The coordinated rollback was cancelled before production changed. The owner then clarified #382: undo #377’s date-control visual changes. The prior responsive alignment, button sizing and native-input placement remain; the independent nonempty-date safety guard prevents clearing the input from breaking navigation. Earlier Food & Servings heading/full-cell alignment is retained. This does not resolve #255’s original native-picker anchoring concern; #255/#200 remain open for renewed acceptance. [Historical batch evidence and clarified scope](docs/visual-bugs-255-200.md) are retained without reapplying the rejected visuals.

Run `npm run build` then `npx playwright test --config playwright.diary.config.mjs` for mobile/desktop date, food and meal-review presentation against the production build. The cases also run in the existing `npm run test:e2e` suite. Set `E2E_DIARY_BASE_URL` to the deployed origin to inspect its actual public assets; the fixtures intercept every application API request, use synthetic session data, and abort unexpected requests before any placeholder credential or write reaches a host. These checks do not prove an authenticated production backend journey or native OS calendar chrome.

The frontend uses the Field Atlas direction described in
[`docs/design/FIELD_ATLAS.md`](docs/design/FIELD_ATLAS.md). Shared theme
configuration lives in `src/theme.js`, with matching semantic CSS tokens in
`src/App.css`.

Design mockups live alongside the guide in `docs/design/`, and the root README's
application screenshots live in `docs/images/`. These documentation files are
excluded from Docker build contexts.

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

## Domain architecture

Reusable nutrition and meal-item logic lives under `src/domain/`:

```text
src/domain/
├── nutrition/
│   ├── definitions.js   # Nutrient keys, units, classifications, and energy ratios
│   └── calculations.js  # Normalization, totals, macro calories, and aggregation
└── mealItem/
    ├── portions.js      # Portion selection and serving conversions
    ├── adapters.js      # Catalog, proposal, and saved-meal transformations
    └── tree.js          # Immutable nested meal edits and nutrient scaling
```

Components and pages import these modules directly. Domain modules depend only
on other domain modules or neutral utilities; they never import React, Material
UI, components, or pages. Locale-aware number formatting is shared through
`src/utils/nutritionFormatting.js` because portion labels and UI displays use the
same conventions.

Nutrient labels, CSS colors, chart gradients, and chart decoration belong in
`src/components/nutrition/nutritionPresentation.js`. It combines presentation
metadata with the authoritative domain definitions and calculated values.
Domain tests live alongside their modules, and the architecture tests check
dependency direction and circular imports. All consumers use the new paths,
so no compatibility re-export files are needed.

## 🧭 Routes
- `/login`: email and password login
- `/register`: account creation with an optional username
- `/forgot-password`: password-reset email request
- `/reset-password?uid=...&token=...`: choose a new password
- `/`: protected MacroMapper dashboard and product-status overview
- `/diary`: protected dated meal diary with daily nutrition totals
- Any unknown route resolves to the protected home page

Signed-out users who request a protected route are redirected to `/login`.

The diary offers manual entry and an **Estimate meal** path. Estimation keeps a
fast deterministic catalog path for complete matches. When natural-language
input remains unresolved, AI extracts separate provider-aware food searches;
the app resolves each one against the visible catalog and requests sourced
nutrition estimates only for foods still missing. Product-defining terms keep
partial matches from selecting a different menu item.
During review, an **Adjust with AI** field can add a forgotten food or apply a
clear top-level removal or serving correction without discarding current edits.
New follow-up foods also search the catalog before a shared estimate is created.
Ambiguous quantities and targets receive a disclosed best-effort assumption at
lower confidence; failed requests keep the draft and input available for retry.
Users must review the persisted draft before saving: they can rename the meal,
switch between validated unit/portion options, adjust the amount without
changing the nutritional basis, remove ingredients, and add catalog foods.
The same Map Your Meal editor and full set of nutrition, portion, catalog, and
nested-component controls are used for AI-reviewed meals, manual mapping, and
editing existing diary entries. Existing meals save back to the same entry
rather than creating a duplicate.
Add from the Catalog combines text search with personal/shared scope, provider,
and provenance filters. Active filters can be cleared individually or reset,
results retain serving/source/nutrition details, and adding a result leaves the
builder open with an explicit confirmation.
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
- Login and registration navigate directly to the protected Meal Diary.
- The app header title is `MacroMapper`.
- The header provides MacroMapper navigation, recipient-scoped
  notifications, profile display, and logout action.
- The drawer contains the Meal Diary destination and MacroMapper product description.
- The responsive meal diary lets users search the
  visible catalog, create a personal food, add/remove foods, change quantities,
  inspect saved composite ingredients, and create, edit, or delete meals.

## ✨ Planned Product Surfaces

The authenticated shell opens directly to the daily diary and includes the
Food Item search and creation needed for manual meal logging. It will grow to
include an AI meal-review flow, nutrition and activity goals, and trends.

Authentication endpoint functions live in `src/services/authApiClient.js`.
Notification functions live in `src/services/notificationApiClient.js`. Token
refresh and unauthorized-response behavior live in
`src/services/requestClient.js`.
Meal, daily-total, catalog-search, and personal-food requests live in
`src/services/mealApiClient.js`.

## 💻 Local Setup
The checked-in frontend dependencies require Node.js 24.15+ within 24.x or Node.js 26.x. CI reads
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

On the shared production host, Notoli's existing public Nginx routes the
MacroMapper hostname to its private frontend and sends `/auth/`, `/api/`,
`/admin/`, and Django static assets directly to the private backend. CI builds
with `VITE_API_BASE_URL` empty; provider credentials belong only to Django's
runtime environment. SPA deep links retain the existing frontend fallback.
See the [deployment guide](../deploy/README.md) for both Compose overlays.

## Docker Hot Reload
The development Compose file supplies frontend environment variables directly,
including `VITE_API_BASE_URL`, so this setup requires no frontend `.env` file.

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
The Vite configuration controls frontend builds and tests. Browser-target
overrides belong in `vite.config.mjs` through `build.target`.

```powershell
npm test
npm run test:watch
npm run lint:strict
npm run format:check
npm run build
```


## 🔌 Shared MCP framework

See [the app MCP guide](../docs/MCP.md). Consent, the profile-menu Connected Apps link and connection revocation require `VITE_MCP_ENABLED=1`. The production Dockerfile defaults this build argument to `1`; raw Vite development remains opt-in. Pass `--build-arg VITE_MCP_ENABLED=0` for a deliberately disabled image. Preserve JWT-only consent and validated connection return paths. The existing UI lists the actual requested read/write/estimate permissions; enabling it does not create an OAuth client or grant.

## 🔒 Transitive dependency maintenance

The frontend temporarily overrides `minimatch@>=9 <11.0.1` to `^11.0.1` for
[GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249).
ESLint, its config-array, the JSX accessibility plugin and typescript-estree
still request older majors; upgrading ESLint alone does not remove the advisory.
The lockfile resolves minimatch 11.0.4. These are build/lint dependencies, not
browser globbing APIs. Keep the version selector scoped to the affected modern
API family; do not apply it to legacy callable minimatch 3 consumers.

Minimatch 11 removes `makeRe`, `AST` and internal matcher methods. The current
parents use the retained matching API. Validate a clean `npm ci`, `npm ls
minimatch glob --all`, strict lint, tests and the production build whenever a
parent or override changes. Review upstream API changes before widening the
selector. Remove overrides once all parent ranges natively accept patched
versions, regenerate the lockfile and repeat those checks. Canonical rollout:
[FullStackTemplate #267](https://github.com/VanillaIceCube/FullStackTemplate/issues/267).

## Authentication and notification reliability

All four authentication forms disable submission while requests are pending and
restore it after failure. New sessions trim profile strings and remove absent or
blank username/email fields. The request client normalizes object, tuple-array
and native `Headers` inputs, preserves custom headers on one JWT refresh/retry,
and attaches the stored access token when explicit Authorization is absent
outside public auth forms. Invalid refresh credentials clear tokens/profile;
transient refresh failures preserve the session. Existing consent return paths
remain application-specific.

Notifications expose Retry and retain failed actions. Item/bulk controls disable
overlapping actions through response parsing. Failed/malformed mark-read responses
keep the inbox open instead of navigating. See [the audit](../docs/AUTH-PARITY.md).

## Development dependency reproducibility

Development images pin reviewed multi-platform Node 26 and Miniforge 26.9.4-0
registry digests. Production Dockerfiles and the independent release engine are
unchanged by this development-image policy. Refresh tags/digests together after
registry verification and a disposable build/configuration check.

The frontend development entrypoint hashes both `package.json` and
`package-lock.json` inside its persistent `node_modules` volume. Fresh volumes
install with `npm ci`; unchanged restarts reuse dependencies; changing either
manifest reinstalls. Missing manifests or a failed installation stop startup and
retry on the next invocation. Use one volume per checkout and restart after edits.
Run `node --test tests/dev-dependencies.test.cjs` from the repository root for the
credential-free mocked lifecycle/exit-status regression. Compose configuration
checks do not deploy or touch application data.

Supported test/build runtimes are Node24.15+ within24.x or Node26.x. jsdom30 explicitly excludes the end-of-life Node25 line; do not treat >=24 as universal support. Use the same supported runtime for before/after timings.

## Optional isolated browser tests

Install the backend requirements in an activated Python environment, then from
`frontend` run the following with Node 24.15+ within 24.x or Node 26.x:

```powershell
npm ci
npx playwright install chromium
npm run test:e2e
```

Linux CI uses `npx playwright install --with-deps chromium`. The wrapper creates
a marked temporary directory, starts fresh Django/SQLite on 127.0.0.1:8001 and
Vite on 127.0.0.1:3001, and removes only its generated state after both servers
stop. Those ports must be free; existing servers are never reused. The backend
does not load developer `.env` files, uses synthetic users, disables MCP, and
writes reset messages to the temporary mail directory. No SMTP or model calls
are made. Registration, reload/session isolation, logout/protected routing, bad
credentials, expired access and valid/invalid password-reset tokens are covered.

There is one Chromium worker, no retries, and a ten-minute global timeout. Local
runs of the three shared journeys take roughly one minute after installation;
CI also pays Python/npm/browser installation cost. Failure traces/screenshots
and the HTML report are local in `test-results/` and `playwright-report/`. CI
retains at most 20 MiB/file and 50 MiB/run for seven days, listing omitted files
in `browser-evidence/INDEX.txt`; full text remains in the job log. Reports may
contain disposable test tokens and should not be copied into public issues.

Add product journeys under `e2e/` using these isolated users and existing APIs.
Keep authentication journeys shared; domain fixtures belong to their app. Do not
add real customer accounts, external email or paid-model requests. Infrastructure
has no browser application and retains its ingress/Docker protocol suites.
