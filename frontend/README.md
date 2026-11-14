# 🎨 MacroMapper frontend

The React application uses Vite and Material UI for pages, navigation,
authentication, and the application shell.

## 🧭 Structure

- `src/components/`: reusable interface components.
- `src/pages/`: application pages and routes.
- `src/services/`: API requests and session handling.
- `src/domain/`: pure nutrition, portion, and meal calculations.
- `src/__tests__/`, `e2e/`: component and isolated browser tests.

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
`dist/`. See the [frontend reference](REFERENCE.md) for routes and settings.

## 🧪 Checks

From `frontend/`:

```powershell
npm test
npm run lint:strict
npm run format:check
npm run build
```

For isolated browser tests, install backend dependencies, then run
`npx playwright install chromium` and `npm run test:e2e` from `frontend/`.
The reference covers disposable data, required ports, and failure reports.

## 📚 Reference

- [Routes, components, browser tests, and maintenance](REFERENCE.md).
- [Backend and MCP integration](../backend/README.md).
- [Docker dependencies and image maintenance](../deploy/README.md#development-dependency-reproducibility).
- [Application tour](docs/APPLICATION-TOUR.md).


<details>
<summary>Routing, testing, and maintenance sections</summary>

<a id="domain-entry-points"></a>

- [Domain entry points](REFERENCE.md#domain-entry-points)

<a id="-visual-system"></a>

- [🧭 Visual system](REFERENCE.md#-visual-system)

<a id="domain-architecture"></a>

- [Domain architecture](REFERENCE.md#domain-architecture)

<a id="-routes"></a>

- [🧭 Routes](REFERENCE.md#-routes)

<a id="-authentication-and-shell-behavior"></a>

- [🔐 Authentication And Shell Behavior](REFERENCE.md#-authentication-and-shell-behavior)

<a id="-planned-product-surfaces"></a>

- [✨ Planned Product Surfaces](REFERENCE.md#-planned-product-surfaces)

<a id="-local-setup"></a>

- [💻 Local Setup](REFERENCE.md#-local-setup)

<a id="docker-hot-reload"></a>

- [Docker Hot Reload](REFERENCE.md#docker-hot-reload)

- [🧰 Checks](REFERENCE.md#-checks)

<a id="-shared-mcp-framework"></a>

- [🔌 Shared MCP framework](REFERENCE.md#-shared-mcp-framework)

<a id="-transitive-dependency-maintenance"></a>

- [🔒 Transitive dependency maintenance](REFERENCE.md#-transitive-dependency-maintenance)

<a id="authentication-and-notification-reliability"></a>

- [Authentication and notification reliability](REFERENCE.md#authentication-and-notification-reliability)

<a id="development-dependency-reproducibility"></a>

- [Development dependency reproducibility](REFERENCE.md#development-dependency-reproducibility)

<a id="optional-isolated-browser-tests"></a>

- [Optional isolated browser tests](REFERENCE.md#optional-isolated-browser-tests)

<a id="native-diary-picker-anchoring"></a>

- [Native diary picker anchoring](REFERENCE.md#native-diary-picker-anchoring)

<a id="calculation-and-input-regression-guidance"></a>

- [Calculation and input regression guidance](REFERENCE.md#calculation-and-input-regression-guidance)

<a id="nutrition-evidence-display"></a>

- [Nutrition evidence display](REFERENCE.md#nutrition-evidence-display)

<a id="jsdom-31-layout-tests"></a>

- [jsdom 31 layout tests](REFERENCE.md#jsdom-31-layout-tests)

</details>
