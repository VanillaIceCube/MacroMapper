# AGENTS.md

Production release ownership: use the [app-only release/recovery guide](deploy/production/README.md).
Common release code/tests and workflow stages are pinned to the Infrastructure
release standard. Update the shared source, then synchronize both applications;
CI's parity check rejects independent vendor edits. App policy lives in
`deploy/production/app.json`; preserve its intentional network/readiness differences.

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

MCP framework changes follow [docs/MCP-FRAMEWORK.md](docs/MCP-FRAMEWORK.md). FullStackTemplate owns the canonical Python package; keep all consumer hashes/pins aligned. MacroMapper source defaults off and central production policy awaits coordinated env-prod activation; domain tools remain app-owned. Preserve Notoli credentials, scopes, tool permissions and exact proxy trust.

## MacroMapper MCP

The app-owned MCP contract is in [docs/MCP.md](docs/MCP.md). Source defaults off.
Central `app.json` prepares `DJANGO_MCP_ENABLED=1` and exact trusted proxy
`172.20.0.3`; root alone coordinates env-prod activation after shared issuer,
YNAB/client and ingress acceptance. Use the exact canonical framework pin; do not
edit the vendor independently. Central MCP auth is separate from regular login,
REST JWTs and AI estimation. Never auto-link/create users from email or username.
Explicit issuer/UUID-subject links, local active/ownership checks and intentional,
scoped single-use meal confirmations are mandatory. No AI billing tools.
The dedicated `MACROMAPPER_MCP_INTROSPECTION_SECRET` enters the existing private
release env bundle; local copies belong only in ignored env files. Do not store
it in `deploy/backend.env`, logs or Git. Production policy is prepared in `deploy/production/app.json`; its explicit
disabled recovery delta is `deploy/production/mcp-disabled-policy.json`. Preserve
common release parity.
The central app release policy expects five gateway route networks; see the MCP
runbook for coordinated explicit disabled-profile rollback to a matched legacy
three-network bundle. Never weaken topology checks or silently return exposed
hostnames to base. Pin only the reviewed single MacroMapper ingress peer in
`DJANGO_TRUSTED_PROXY_IPS=172.20.0.3`; no CIDR/frontend/other-peer forwarding trust.
Before first enabled rollout, stage the app-owned disabled-policy rollback tool
with `prepare_mcp_recovery.py` as documented. Failed enabled releases cannot be
recovered by starting a new disabled deploy or using enabled readiness against a
captured disabled backend. Use the separately staged tool only for a verified
disabled capture; never edit immutable bundles or remove failure barriers.
