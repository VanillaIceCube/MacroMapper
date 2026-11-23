# 🎨 MacroMapper frontend

The React application uses Vite and Material UI for pages, navigation,
authentication, and the application shell.

## 🧭 Structure

- `docker/`: production/development Dockerfiles, their matching
  `Dockerfile.dockerignore` / `Dockerfile.dev.dockerignore`, and Nginx configuration.
  Docker builds keep `frontend/` as their context; ignore patterns are relative
  to that context root. Nginx and development startup files remain build inputs.
- `src/theme.js`: palette and nutrient tokens, typography, document colors and
  Material UI defaults. `CssBaseline` exposes its tokens as CSS custom properties.
- `src/index.css`: the single global stylesheet, loaded by `src/index.jsx`; keep
  platform rendering, element resets, app layout, contour artwork, native links
  and reduced-motion rules here, consuming the theme's custom properties.
- `src/components/`: reusable interface components.
  Standard components maintained across the three apps live in [src/components/app-core/](src/components/app-core/).
- `src/pages/`: application pages and routes.
- `src/services/`: API requests, response parsing in `apiResponse.js` and session storage in `sessionState.js`.
- `src/hooks/`: reactive session access and shared notification lifecycle behavior.
- `src/domain/`: pure nutrition, portion, and meal calculations.
- `src/test-helpers/`: shared test setup and reusable helpers.
  App, startup and feature tests stay beside the files they exercise.

Keep `components/`, `pages/`, `hooks/` and `services/` flat by default. Group modules you
usually edit together one level down. A source file and its adjacent test count as one module.

### Where to change things

| To change | Start here |
| --- | --- |
| Routes and layout | [App](src/App.jsx) |
| Header and notifications | [AppHeader](src/components/app-core/AppHeader.jsx), [NotificationsMenu](src/components/app-core/NotificationsMenu.jsx) |
| Sign-in, registration, and password reset | [AuthForm](src/components/app-core/AuthForm.jsx) and [route pages](src/pages/authentication/) |
| Shared colors, typography, and component styles | [Theme](src/theme.js) |
| Diary and daily totals | [DiaryPage](src/pages/DiaryPage.jsx) and [saved meal cards](src/components/DiaryMealCard.jsx) |
| Meal drafts, estimates, and saving | [MealEditorDialog](src/components/meal-editor/MealEditorDialog.jsx) |
| Food search, filters, and pagination | [FoodCatalogPicker](src/components/meal-editor/FoodCatalogPicker.jsx) and [food result cards](src/components/meal-editor/CatalogFoodCard.jsx) |

## 💻 Local development

Use Node.js 24.15+ within 24.x or Node.js 26.x, matching `package.json`.
From the repository root:

```powershell
Set-Location frontend
npm ci
npm start
```

Open `http://macromapper.localhost:3000`. For Docker hot reload, follow the
[deployment guide](../deploy/README.md).

## ⚙️ Configuration

`VITE_API_BASE_URL` controls the API origin. Leave it blank for production same-origin
requests; client-side settings must contain no secrets. The build output is
`dist/`.

Development Compose supplies `VITE_API_BASE_URL` through its `environment`
settings. Production Docker builds pass the matching build argument, which is
compiled into the static assets; a blank value selects same-origin requests.
Local `.env` files are excluded from Docker build contexts.

`docker/nginx.conf` sets backend proxy headers once and groups routes with the
same behavior. Slash redirects, SPA deep links and consent-page headers stay
explicit. The API keeps its longer timeout in a separate location.

For direct `npm` development, an unset API origin uses `http://localhost:8000`.
An explicit shell value overrides that default; an explicit blank uses same-origin.
Vite's `base` setting supplies `%BASE_URL%` for HTML assets and
`import.meta.env.BASE_URL` for the router basename and shell, drawer and authentication logos.
Production uses domain-root routes; a subdirectory also needs matching server and API routing.
The API origin is separate
from both settings. Development uses port 3000; production Nginx serves the static
build and preserves SPA deep links.

## 🗺️ Routes and behavior

Route pages load through `React.lazy` and the shared `RouteContent` boundary.
The application shell stays usable while a page loads. Authentication guards
run before protected lazy pages render, and a failed import offers a full-page
reload at the current URL, preserving its query and deployment base. Navigating
to another route clears that route's error state. The build emits separate page
chunks; shared vendor code remains part of the signed-out dependency graph.

- `/login`: email and password login
- `/register`: account creation with an optional username
- `/forgot-password`: password-reset email request
- `/reset-password?uid=...&token=...`: choose a new password
- `/`: protected dated meal diary with daily nutrition totals (also available at `/diary`)
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
switch between validated unit/portion options, remove ingredients, and add catalog foods.
Natural serving sizes supplied for the specific food (for example, Small,
Medium, and Large apples) remain separate from its canonical name. Switching
between these sizes preserves the count and recalculates consumed nutrition
from their gram equivalents; measurement units such as grams and ounces convert
the displayed amount while preserving the consumed weight. Foods without natural
size definitions keep their declared serving and available weight/volume options.
Selected portions survive proposal review and saved-meal editing alongside the
historical nutrition snapshot.
Composite ingredient rows show the amounts for one full portion. The parent
count records the fraction eaten, and scales the composite total once; it does
not rewrite recipe ingredients or separately added foods. AI hierarchy corrections
replace the displayed tree with the validated response, keeping ingredient
identifiers and quantities rather than adding a second copy at meal level.
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

## 🧭 Product intent

MacroMapper is personal-use first: accounts, meals and custom foods remain private.
Catalog-first text estimates expose components, quantities, sources and confidence
for review before saving a pinned diary snapshot. A Food Item can be consumed
directly or composed of other Food Items; personal meal edits never redefine the
shared canonical food. Official/verified, reusable community/AI estimates and private
personal records retain distinct trust states. Unknown nutrients are unavailable,
never zero. Track calories, protein, carbohydrate, fat, fiber, sugar, sodium,
cholesterol and available micronutrients without implying clinical guidance.

Goals, calculated user-editable targets, activity logging and expanded trends remain
planned. The planned baseline describes non-exercise life; only activities explicitly
counted toward the budget add estimated calories. Avoid double-counting regular
exercise. Activity estimates and targets are editable tracking information, never
medical advice. Weight tracking, photos/barcodes and household/social/coaching
features remain deferred.

Authentication-page destinations use React Router links with real `href` values,
keyboard activation and native new-tab behavior. Connected Apps is discoverable
in the profile menu when the connector is enabled.

## 🔐 Sessions and connections

`src/services/sessionState.js` is the sole owner of the compatible access/refresh
and username/email storage keys. Its cached snapshots and subscriptions feed
`useSession`; login/logout replace the account generation, while guarded refresh
updates tokens without replacing that generation. Do not read or mutate auth
storage in components or API adapters. Use the snapshot for request-time reads,
the hook for rendering, and the store operations for writes. The unrelated
`pendingSnackbar` key remains the login-message handoff.

The application shell and protected content reset on account changes, including
open menus, private drafts and Notoli's board drawer state. Async continuations
use `useSessionGuard` before account-scoped navigation or global UI updates. Authentication forms also check the current URL so a late response cannot take over after navigation starts.
Logout/expiry queue their login message before publishing the cleared session;
root snackbar state preserves successful login/register feedback and excludes
messages from an older generation.

`useNotifications` owns loading, retries, unread state and synchronous item/bulk
locks. `NotificationsMenu` connects the hook to the app's notification API and
handles presentation and navigation. The hook discards stale results after
account changes or unmount. Token rotation preserves pending work, and an
earlier list request cannot undo a newer mutation.

Authentication forms disable submission while pending. Tokens and profile data
live in `sessionStorage`; new sessions trim profile fields and clear absent values.
Protected requests use the stored JWT when the caller omits Authorization.
Public authentication forms do not receive an injected access token.

The request wrapper preserves object, tuple-array, and native `Headers` values
through one JWT refresh/retry. Invalid refresh credentials or a second protected
401 after refresh clear the session;
temporary refresh failures retain it. Refresh results belong to the login that
started them: logout or a new login invalidates pending work. Background failures
preserve an active, validated connection path and query through login.
Notification failures keep actions available
for Retry, and malformed mark-read responses must not navigate away.
Use semantic links for destinations and buttons for actions, with keyboard and
native new-tab coverage.

Optional consent and Connected Apps use `VITE_MCP_ENABLED=1`. Preserve JWT-only
consent and validated return paths. See the [backend MCP guide](../backend/README.md#-mcp-integration).
The production Dockerfile enables this build argument by default; raw Vite
development remains opt-in. Enabling the UI does not register a client or grant.

The existing `/connections/authorize?approval_id=<opaque UUID>` screen supports
app-owned action review. It loads the complete preview with the app JWT, renders
untrusted text without HTML, and submits only the signed ticket plus explicit
Approve/Cancel. It never auto-approves or puts credentials in links. Invalid/stale
tickets clear controls and require fresh review. Framed action review is refused;
frontend Nginx applies `frame-ancestors 'none'`, `X-Frame-Options: DENY`, no-store and
no-referrer to the exact `/connections/authorize` page, preserving embedding policy
elsewhere. MacroMapper and Notoli configure app-owned approval handlers.
FullStackTemplate supplies the reusable flow for applications that register a
handler.

### Connections response contract

Successful consent, decision, list and revoke responses must be JSON objects.
Unreadable, empty, null, scalar or array successes reject with `Request failed.`;
a protocol failure must not follow a callback or claim revocation succeeded.
HTTP failures use the first nonblank string in `error_description`, `detail`, then
`error`, otherwise `HTTP <status>`. Never expose raw HTML/plaintext, parser errors,
nested objects or unrelated JSON fields as fallback messages. Backend public error
fields must be safe to display. Preserve JWT-only headers, omitted cookies, form
encoding, signed consent tickets and validated callbacks. Invalid refresh credentials
clear the session; transient proxy/refresh failures retain it for retry. All three applications share the same post-refresh 401
and session-lifecycle contract.

## 🧮 Domain architecture

Components and pages import meal-item operations from `src/domain/meal-item` and
nutrition operations/definitions from `src/domain/nutrition`, using named imports
relative to the consumer. Each package's `index.js` exposes its public API;
consumers should not reach into `adapters`, `portions`, `tree`, `calculations`,
or `definitions` directly. Keep export names unique within a package.

Within domain implementations, direct relative imports remain appropriate and
avoid routing a module's own dependencies through its entry point. Domain code
may depend on other domain modules and pure utilities, but remains independent
of React, Material UI, components, pages and presentation metadata. Keep labels
and theme details in the existing presentation layer.

Add behavior tests beside domain implementations and run the full frontend suite
and production build when changing entry points or their consumers.

## 🔎 Nutrition evidence

Meal review retains official parent nutrition while showing inferred component
values separately. Details expose mixed/partial evidence, clickable sources,
per-nutrient coverage, model confidence and failed/unavailable research warnings.
User changes clear verification for the changed definition; consumed count changes
preserve per-serving evidence. Legacy records remain readable. See the
[backend evidence contract](../backend/README.md#-nutrition-evidence).
Natural-size changes also preserve the food's per-serving evidence. Changing an
ingredient's size changes its recipe contribution, so verification and confidence
on enclosing composites are cleared and their totals are recalculated. Switching
measurement units alone preserves both consumed nutrition and composite evidence.

## 🎨 Style guide

Use `--page-background` and `--page-text` for the document, and
`--surface-background` and `--surface-text` for panels and controls. The app theme
defines these colors. Keep sibling JSX sections in the order they appear on
screen so keyboard navigation follows the layout.

### Foundations

- Use Material UI components and responsive `sx` values before adding custom
  layout primitives.
- Use the centralized Material UI theme in `src/theme.js`. Its `MuiCssBaseline`
  overrides publish the existing CSS custom properties, including derived border,
  contour and link-focus colors; do not duplicate palette values in `src/index.css`.
  `App` and the shared test renderer install the app theme and `CssBaseline`.
- Keep common MUI typography, input/focus behavior and app-bar chrome in the theme.
  Keep responsive geometry, contextual surfaces and menu frames in their owning
  components; diary and ingredient menus intentionally differ from header overlays.
  The global stylesheet retains the explicit border-box reset, numeric formatting,
  contour layout, native authentication-link behavior and reduced-motion rules.
- Follow the Field Atlas direction: warm paper surfaces, ink structure, restrained
  cartographic details, and factual rather than clinical language.
- Use Bone `#F6F1E7` for the canvas, Midnight ink `#17324D` for text and
  structure, Forest `#2E6B4F` for confirmed states and primary actions,
  Persimmon `#E46B3C` for editable estimates, and Mineral blue `#A9CAD4` for
  neutral data surfaces.
- Use Midnight ink for calories, Forest for protein, the accessible dark
  Mineral token for carbohydrates, Persimmon for fat, and the named nutrient
  tokens for the remaining tracked nutrients. Apply these semantic tokens consistently to cards,
  legends, and charts. Pair every state color with text, an icon, or another
  non-color cue.
- Use `Newsreader` for editorial headings and `Inter` for navigation, controls,
  labels, and body copy. Apply tabular numerals to nutrition data with the
  `numeric-data` class.
- Prefer one-pixel ink borders, 10–14 px radii, and surface shifts to elevation.
  Shadows should remain subtle and limited to floating menus or focus layers.
- Preserve 44 px minimum interactive targets, visible keyboard focus, reduced
  motion behavior, and WCAG 2.2 AA contrast.
- Keep authenticated and public routes visually consistent with the shared
  application shell.

### Product language and layout

Use sentence case and factual `within target`, `above target`, and `below target`
labels. Source badges combine icon and text; unknown values display `Unavailable`.
Keep editorial mapping language around Describe → Review components → Save to diary;
use ordinary language for settings. Compass/route/pin motifs orient and explain
provenance; decorative coordinates must never imply a user's real location.
Desktop rails and optional detail inspectors retain list context. Mobile actions
remain visible above fixed navigation, and secondary destinations use overflow
rather than crowding primary tabs. Charts describe patterns without praise, blame
or medical interpretation.

### Authentication

- Build public authentication pages with `AuthForm`.
- Give every form a visible heading, native submit behavior, and browser
  autocomplete metadata.
- Show API outcomes through the shared application snackbar.
- Avoid exposing whether an email address belongs to an account in
  forgot-password responses.

### Application shell

- Keep `MacroMapper` as the app-header title.
- Preserve the drawer, notification, profile, and logout entry points when
  adding product routes.
- Keep the Home page specific to MacroMapper and clearly distinguish active
  capabilities from roadmap features.
- Add future product routes behind `AuthenticatedRoute` unless they are
  intentionally public.
- Keep contour lines low contrast and away from dense forms, tables, and data
  visualizations.
- Concentrate mapping language around meal creation and provenance; use plain
  language for ordinary settings and account actions.

### Nutrition surfaces

- Import nutrient definitions and calculations from `src/domain/nutrition/` and
  meal-item portions, adapters, and tree operations from `src/domain/meal-item/`.
  Keep domain modules independent of React, Material UI, components, and pages.
- Keep labels, semantic colors, gradients, and chart decoration in
  `components/nutrition/nutritionPresentation.js`. Share locale-aware number
  formatting through `utils/nutritionFormatting.js`.

- Present daily totals as bordered data cards with tabular numerals. Use the
  semantic calorie, protein, carbohydrate, and fat tokens; keep secondary
  nutrients on neutral paper surfaces. Calories use Midnight ink as a neutral
  total and must not reuse a macro color.
- In component-calorie comparisons, use thicker horizontal bars whose total
  length represents component calories and whose stacked Forest, dark Mineral,
  and Persimmon segments represent calories from protein, carbohydrates, and
  fat. Fall back to Midnight ink when macro data is incomplete.
- Use Forest to identify saved meals and confirmed catalog actions, Mineral for
  neutral date and search surfaces, and Persimmon for user-entered food
  estimates.
- Call saved records “meal items” in the interface. Reserve component language
  for the optional ingredient breakdown within a composite food.

Diary reads ignore obsolete responses after the date changes or the page unmounts.
Network failures release loading, save and estimation controls, retain draft input,
and expose an error for retry; network failures do not automatically retry writes
or paid estimates.

## 🧪 Checks

Keep every test beside its implementation with the same basename and extension:
`Component.jsx` pairs with `Component.test.jsx`, and `service.js` pairs with
`service.test.js`. Put behavior and integration scenarios in that owning suite
using scoped `describe` blocks, rather than adding standalone behavior-named or
`.integration.test` files. JavaScript hooks and components that return no JSX keep
`.test.js` harnesses using `createElement` when necessary. Shared setup and reusable
helpers belong in `src/test-helpers/`; tests of a domain package's public API pair
with its `index.js` entry point.

Keep shared session, request, connection and navigation regressions aligned across
FullStackTemplate, MacroMapper and Notoli when the behavior applies. Preserve real
React Router and Material UI keyboard/exit coverage when consolidating suites;
app-specific domain and route expectations remain in their owning application.

Direct shell and nutrition component tests cover accessible headings, keyboard
form submission, known versus unavailable nutrient values, editable inputs and
composite calorie-only editing. Meal-item adapter and tree tests own their focused
cases; `domain/meal-item/index.test.js` retains cross-module public API workflows.

The session store and hooks have direct race/reactivity coverage, with request-client
and real application tests covering refresh, account changes and auth feedback.
Nutrient definitions, the nutrition re-export entry point and `theme.js` are
exercised through calculation, presentation and real themed component tests;
avoid duplicate suites that merely copy metadata, exports or style declarations.

`src/index.test.jsx` boots the real entry point, React root and application in
jsdom, then checks the signed-out login route and usable form without private API
requests or uncaught startup errors. It unmounts the real root and restores test
state afterward. Existing Material UI test shims still apply; browser layout and
built HTML are outside this test's scope.

`npm run build` runs strict lint before Vite's production build. Use
`npm run lint:fix` to apply available lint fixes.

From `frontend/`:

```powershell
npm test
npm run lint:strict
npm run format:check
npm run build
```

## 🛠️ Maintenance

Shared frontend dependency ranges align across the template and both applications:
React/React DOM 19.3.1, Material UI/icons 9.5, React Router 8.5.1, and Prettier 3.10.
Use `react-router` imports. Testing Library belongs in development dependencies;
TypeScript is explicitly pinned for the tooling peer graph. Keep app-specific
packages, including Notoli drag-and-drop and its test lint plugin, app-owned.

The flat ESLint configuration uses Vitest globals, matching the configured test
runner.

Keep `showPicker()` synchronous inside the user handler, with its existing click
fallback. Preserve the nonempty-date guard, responsive navigation bounds and
Today behavior.

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
versions, regenerate the lockfile and repeat those checks.

Keep Material UI and icons on compatible versions and regenerate the lockfile
together. Prefer `sx` and `slotProps`; preserve accessible control labels. For
jsdom CSS assertions, check computed transition/animation longhands; inspect
responsive geometry in a browser. Follow the Node range in `package.json`,
and verify clean installs, strict lint, formatting, tests and production builds.
See [Docker dependency maintenance](../deploy/README.md#development-dependency-reproducibility).

<a id="-related-guides"></a>

## 📚 Reference

- [Backend and MCP integration](../backend/README.md).
- [Local Docker and production releases](../deploy/README.md).
