# AGENTS.md

Production release ownership: use the [app-only release/recovery guide](deploy/production/README.md).
Common release code/tests and workflow stages are pinned to the Infrastructure
release standard. Update the shared source, then synchronize both applications;
CI's parity check rejects independent vendor edits. App policy lives in
`deploy/production/app.json`; preserve its intentional network/readiness differences.

## 🌿 Main-first release history

Land reviewed source changes on `main` before an authorized `env-prod` promotion.
Production may intentionally lag while rollout dependencies or acceptance are
unfinished; do not deploy merely to make branch trees equal. An exceptional,
explicitly owner-authorized production-branch fix must be reviewed and reconciled into `main` before the next
promotion. Preserve existing release history and checks rather than resetting or
force-pushing either branch. See the [production guide](deploy/production/README.md)
and [#329](https://github.com/VanillaIceCube/MacroMapper/issues/329).

MacroMapper uses manual setup steps; do not assume Django or Node dependencies are installed.

When setup, routing, environment variables, deployment, or CI/CD changes, update the relevant documentation:

- Root overview: `README.md`
- Backend/authentication: `backend/README.md`
- Frontend/routing: `frontend/README.md`
- Deployment: `deploy/README.md`
- GitHub automation: `.github/README-WORKFLOWS.md`
- User-visible or operational changes: `CHANGELOG.md`

## Changelog format
Add a dated section at the top of `CHANGELOG.md` and use only the non-empty headings below, in this order:

1. `### Added`
2. `### Fixed`
3. `### Changed`
4. `### Removed`

## Local development
Backend:

```powershell
python -m pip install -r backend/requirements.txt
python backend/manage.py migrate
python backend/manage.py runserver 8000
```

Frontend:

```powershell
Set-Location frontend
npm ci
npm start
```

Optional backend variables:

- `DJANGO_SECRET_KEY` (a local-only development default is provided)
- `DJANGO_DEBUG` (local default: `1`)
- `DJANGO_SQLITE_PATH` (default: `backend/db.sqlite3`)
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CORS_ALLOWED_ORIGINS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_FORCE_SCRIPT_NAME` (leave blank for subdomain-root routing)
- `DJANGO_FRONTEND_BASE_URL` (default: `http://localhost:3000`)
- `DJANGO_EMAIL_BACKEND`
- `DJANGO_EMAIL_HOST`
- `DJANGO_EMAIL_PORT`
- `DJANGO_EMAIL_USE_TLS`
- `DJANGO_EMAIL_HOST_USER`
- `DJANGO_EMAIL_HOST_KEY`
- `DJANGO_EMAIL_TIMEOUT`
- `DJANGO_DEFAULT_FROM_EMAIL`
- `MACROMAPPER_OPENAI_API_KEY` (required for GPT estimates that do not match the catalog)
- `OPENAI_MEAL_ESTIMATION_MODEL` (default: `gpt-5.6-luna`)
- `OPENAI_MEAL_ESTIMATION_TIMEOUT` (total AI budget; default/max: `110` seconds)

Optional frontend variable:

- `VITE_API_BASE_URL` (development default: `http://localhost:8000`; leave blank in same-origin production)

## Checks
Run checks in proportion to the change:

```powershell
python backend/manage.py test
ruff check backend
ruff format backend --check
Set-Location frontend
npm test
npm run lint:strict
npm run format:check
npm run build
```

## Production
Production is designed for `https://macromapper.judeandrewalaba.com` behind
Cloudflare and an origin Nginx proxy.

- Frontend: `/`
- Authentication: `/auth/`
- Django admin: `/admin/`
- Notification and future nutrition/activity APIs: `/api/`
- GitHub deployment branch: `env-prod`
- GHCR images: `macromapper-backend` and `macromapper-frontend`
- Deployment path: `/opt/apps/macromapper`

For production domain or route changes, review the Infrastructure gateway/vhosts,
the app release configuration and allowlist/base-URL variables.
`deploy/nginx-proxy.conf` and `deploy/docker-compose.yml` are local/legacy-only;
use the [local Docker guide](deploy/README.md) for hot reload and standalone HTTPS.
Production operations follow only the [app release guide](deploy/production/README.md)
and the separately authorized Infrastructure plan.

## GitHub automation
MacroMapper automation includes lint, tests, CodeQL, dependency review, npm
malware review, Dependabot auto-merge, AI PR reviewers, deployment, and
scheduled security-alert aggregation.

Secret-dependent workflows must fail visibly when their credentials are unavailable. Keep GitHub App permissions and the credential separation described in `.github/README-WORKFLOWS.md`.

External GitHub Actions use immutable commit SHAs with version comments.
Keep that convention when updating workflows or composite actions; preserve
review/scanner failure gates and do not treat action updates as deployment approval.

## Jules recurring agents

Nora and Marty use the [v3 operating rules](.jules/README.md): at most one open
PR per agent per repository. Repeat runs maintain the existing PR, integrate
current main, and verify its latest head instead of opening another PR.

## 🔑 OpenAI reviewer isolation

Use `OBI_WAN_OPENAI_API_KEY`, `LINT_EASTWOOD_OPENAI_API_KEY`, and
`ROBOCOP_OPENAI_API_KEY` for their respective reviewers; RoboCop also owns
all security-alert model calls. `OPENAI_REVIEWERS_PROJECT_ID` identifies this repository's
reviewer project. Keep credentials separate across repositories and application
environments, preserve visible missing-key failures, and follow the deferred
cutover steps in `.github/README-WORKFLOWS.md`.

Meal estimation keeps `MACROMAPPER_OPENAI_API_KEY`, with separate production
and local keys/projects. Store local values only in ignored `backend/.env` or
`deploy/.env`; production values enter the approved private release bundle via
the Actions repository secret. Never store keys in `deploy/backend.env`.


## 🔌 Shared MCP framework

MCP framework changes follow [docs/MCP-FRAMEWORK.md](docs/MCP-FRAMEWORK.md). FullStackTemplate owns the canonical Python package; keep all consumer hashes/pins aligned. MacroMapper stays disabled without business tools. Preserve Notoli credentials, scopes, tool permissions and exact proxy trust.


## 🧭 MCP ownership and deferred implementation

MacroMapper owns any future MCP tools and OAuth provider. Infrastructure supplies
ordinary Nginx routing; do not restore a shared MCP authorization service, YNAB
runtime or cross-app issuer dependency. The previous central resource implementation
was unreleased and has been removed. Keep production `DJANGO_MCP_ENABLED=0`, frontend
connection routes off, ordinary login/REST/AI behavior intact and domain MCP work
in [#284](https://github.com/VanillaIceCube/MacroMapper/issues/284). The existing
canonical optional framework remains app-owned scaffolding; it does not make
MacroMapper a working connector. See [MCP status](docs/MCP.md).

## 🤖 Reviewer model policy

Use `gpt-6-luna` for OpenAI code, build and security reviewers and security-alert grouping. Preserve each reviewer’s existing key/project isolation, budgets and blocking gates. Application AI model selection remains app-owned.
