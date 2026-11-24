# AGENTS.md

## 🧭 Ownership and shared rollout

FullStackTemplate owns reusable application engineering and the canonical MCP
Python framework. Infrastructure owns shared ingress, host operations and the
versioned application release engine. Each application owns its domain behavior,
credentials, OAuth issuer, consent, permissions and MCP tools; do not introduce a
shared authorization service, cross-application account mapping or YNAB dependency.

Follow the [shared rollout policy](https://github.com/VanillaIceCube/FullStackTemplate/blob/main/.github/README.md#-shared-engineering-ownership-and-rollout)
for reusable framework, automation, test or security changes. One canonical
FullStackTemplate parent must inventory all four repositories as required,
not applicable, already satisfied or explicitly deferred with reasons and evidence.
Infrastructure-owned deployment/host changes use an Infrastructure parent with
linked downstream work; do not relocate source ownership.
The parent is complete only after required downstream adoptions are merged and
verified, or explicitly deferred with an owner, tracking issue and acceptance.
Record final-head/main checks and exact PR/commit/evidence links; template-only
success is insufficient. Preserve active PRs, issue history, production controls
and non-triggering labels when consolidating work.

## 📚 Documentation ownership

The main README introduces the repository. Keep setup, commands, configuration,
and maintenance details in the owning folder README and its linked references.
Use consistent headings: 🧭 Structure, 💻 Local development, ⚙️ Configuration,
🧪 Checks, 🔌 MCP integration, and 📚 Reference where applicable.
Use the owning folder READMEs linked below for setup and maintenance.
Keep this file current when its commands or constraints change, and update the
owning README/reference when setup, routing, environment, deployment or CI changes.
Record user-visible or operational changes in `CHANGELOG.md`.

GitHub setup belongs in [.github/README.md](.github/README.md), workflow behavior
in [.github/workflows/README.md](.github/workflows/README.md), and the shared
reviewer/action contract in [.github/actions/README.md](.github/actions/README.md).

Application setup/API/authentication belongs in [backend/README.md](backend/README.md),
frontend routing/configuration/style in [frontend/README.md](frontend/README.md),
and local Docker/deployment setup in [deploy/README.md](deploy/README.md).

## 📝 Changelog format

Keep the single `# Changelog` title and established introduction at the top;
never place entries above them. Use newest-first `## YYYY-MM-DD` sections,
reusing the existing date instead of creating a duplicate. Within each date,
use only nonempty `### Added`, `### Fixed`, `### Changed`, `### Removed` groups,
in that order, with no duplicate categories and entries filed under the correct
group. Use `- ` bullets and one blank line around headings. Preserve substantive
history and valid UTF-8 text when editing or merging entries.

## 💻 Local development

Use manual setup; do not assume Django or Node dependencies are installed.
Use uv 0.13.8 to manage the locked Python 3.12 environment and the Node version range in
`frontend/package.json`. From the repository root:

```powershell
uv sync --locked --project backend
uv run --locked --project backend python backend/manage.py migrate
uv run --locked --project backend python backend/manage.py runserver 8000
```

In a separate shell, from the repository root:

```powershell
Set-Location frontend
npm ci
npm start
```

Backend image definitions live in `backend/docker/`; keep `backend/` as the
Docker build context. Frontend image definitions and Nginx configuration live in
`frontend/docker/`; keep `frontend/` as the Docker build context. Each Dockerfile
uses its adjacent `Dockerfile.dockerignore` or `Dockerfile.hotswap.dockerignore`;
patterns remain relative to the backend/frontend context root. Keep frontend
Nginx configuration and development startup files available to image builds.

For local Docker hot reload and optional standalone HTTPS, follow
[deploy/README.md](deploy/README.md). Initialize only missing local environment
and database files; never truncate an existing SQLite file. Local Compose/proxy
files are not production release inputs.

## ⚙️ Configuration

Optional backend variables:

- `DJANGO_SECRET_KEY` (a local-only development default is provided)
- `DJANGO_DEBUG` (local default: `1`)
- `DJANGO_SQLITE_PATH` (default: `backend/db.sqlite3`)
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CORS_ALLOWED_ORIGINS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
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

Use [backend/README.md](backend/README.md) for configuration semantics and
ignored local dotenv files, and [frontend/README.md](frontend/README.md) for
build-time settings. Client-side variables must contain no secrets.

## 🧪 Checks

Keep backend tests in owning `tests/` packages with descriptive behavior-based
`test_*.py` modules and empty `__init__.py` files. Shared fixture helpers must not
define discoverable test cases or import test modules. Group modules and classes
by behavior, preserve test discovery and assertions when splitting, and keep the
canonical MCP framework tests aligned across applications.

Run checks in proportion to the change, from the repository root:

```powershell
uv run --locked --project backend python backend/manage.py test backend
uv run --locked --project backend ruff check backend
uv run --locked --project backend ruff format backend --check
```

From `frontend/`:

```powershell
npm test
npm run lint:strict
npm run format:check
npm run build
```

Shared frontend test setup and helpers live in `frontend/src/test-helpers/`.
App, startup and feature tests stay beside their implementation. Vitest discovers
`*.test.js` and `*.test.jsx`.

For shared release changes, run `python deploy/production/build_bundle.py --check-parity` and
`python -m unittest discover -s deploy/tests -v` with a disposable local/CI Docker
daemon, plus all applicable consumer suites. Never test against production.

## 🚀 Production

Ordinary changes merge through reviewed `main` before promoting an exact reviewed
source tree through the repository's existing `env-prod` process. Preserve all
required CI, reviews, owner authorization and recovery gates. Explicitly
owner-authorized deployment experiments must return promptly to `main` through
review before the next ordinary promotion. Preserve both histories and newer main
work; never reset or force-push to manufacture parity. Intentional release lag is
allowed while prerequisites or acceptance remain unfinished. History reconciliation
does not authorize deployment, and an absent production branch is not a reason
to create one. Follow the [main-first release policy](https://github.com/VanillaIceCube/FullStackTemplate/blob/main/.github/README.md#main-first-releases).

Common release code, verification, tests and workflow are owned by Infrastructure.
Change `app-release/v1` at the source, regenerate its manifest, then synchronize
all consumers to the same immutable source commit. Application repositories track
that source in `shared_source` in `deploy/production/app.json`; never edit only a vendored copy.
Preserve app-specific Compose, network/readiness policy, immutable image digests,
SQLite capture/recovery and explicit rollback. Keep shared ingress/certificates
and host operations within their separately authorized Infrastructure scope.

Use the [app-only release/recovery guide](deploy/production/README.md).
`deploy/production/app.json` owns the app's intentional network/readiness policy.
Review Infrastructure gateway/vhosts, Cloudflare DNS/proxy/Redirect/WAF/Caching
settings and allowlist/base-URL variables when domains or routes change.
Retain prior release images and matched private recovery data; no host-wide Docker
pruning. Cleanup requires the host operator to review disk usage and select unused
app images explicitly. Releases manage only the app's backend/frontend; local
`deploy/compose.yml` and `deploy/nginx.conf` are local/legacy-only.

Production uses `https://macromapper.judeandrewalaba.com` behind Cloudflare and
origin Nginx, with deployment path `/opt/apps/macromapper` and GHCR images
`macromapper-backend`/`macromapper-frontend`. Frontend is `/`, authentication
`/auth/`, admin `/admin/` and application APIs `/api/`. Preserve the app's release
history and intentional holds described in
[MacroMapper #329](https://github.com/VanillaIceCube/MacroMapper/issues/329).
Production operations follow the app guide and separately authorized
Infrastructure plan; local Compose/proxy files are not release inputs.

## 🤖 GitHub automation

Preserve existing required checks, scanner/lint/test gates and reviewer budgets.
Eligible same-repository human and Dependabot PRs retain their reviewers; forks
remain excluded from secret-bearing reviews. Keep reviewer identities and
serialized writers separate, validated optional `AI_REVIEW_*` settings aligned,
and Dependabot lint auto-fixes disabled. External GitHub Actions use immutable
commit SHAs with version comments. Workflow updates do not authorize deployment.

The shared publisher fails after every `REQUEST_CHANGES`, including repeated or
unchanged verdicts; valid `APPROVE`/`COMMENT` pass and unavailable/invalid output
fails. Missing credentials, incomplete required major-upgrade briefs and oversized
diffs must fail visibly. The shared diff budget is 2 MB (2,000,000 bytes). Obi-Wan's semver-major
Dependabot brief uses complete primary-source evidence; web search remains limited
to that review path. Run the repository's publisher regression tests and
Actionlint when changing this contract. Where used, the read-only `verify-gates.js` audit requires actual
successful reviewer results, including after cancelled or skipped runs.

Dependency review retains full JSON in the `dependency-review-evidence` artifact,
passes it through a file rather than environment variables, and limits RoboCop's
report to 16 KiB plus summary metadata. Disclose omitted entries; bounded reports
must not change the independent gate's non-success verdict. Missing evidence
fails. Preserve CodeQL scope outputs, full default-branch coverage and RoboCop
baseline evidence; concurrent security-alert closure requires verified final state.

Secret-dependent workflows fail visibly when credentials are unavailable.
RoboCop's short-lived App token reads alerts and authors issue mutations;
`SECURITY_ALERTS_TOKEN` is isolated to personal GitHub Project v2 synchronization.
Keep App IDs/private keys, least-privilege permissions, trigger policy and field
setup documented in `.github/README.md`. Security-alert variables resolve in the
three caller workflows, not local composite metadata; pass explicit model, effort
and token inputs. Run `.github/actions/custom-regressions/security-alert-contract.test.js`
after changes; actual loading acceptance requires fresh controlled dispatches on
corrected main. Preserve applicable bounded malware review and documented
coverage decisions. Keep the CI architecture diagrams aligned with workflow edits.

Main requires `AI Code Review / Obi-Wan Code-nobi code review`,
`AI Build Sheriff Review / Lint Eastwood build sheriff review`, and
`AI Security Review / RoboCop security review`. Preserve all other existing
ruleset requirements and the documented CodeQL scope/analyzer checks. The
standalone `CodeQL` Code Scanning results context is not emitted by documentation-only
PRs; scope/analyzer checks preserve the failure gate. Keep same-repository
Dependabot auto-merge within its existing policy and independent checks. Run
both publisher test files when changing the reviewer contract.

## 🔑 OpenAI reviewer isolation

Use `OBI_WAN_OPENAI_API_KEY`, `LINT_EASTWOOD_OPENAI_API_KEY`, and
`ROBOCOP_OPENAI_API_KEY` for their respective reviewers; RoboCop also owns
all security-alert model calls. `OPENAI_REVIEWERS_PROJECT_ID` identifies this
repository's reviewer project. Keep credentials separate across repositories
and application environments, preserve visible missing-key failures, and follow
the credential ownership and cutover verification in `.github/README.md`.
Store the three reviewer OpenAI keys and three reviewer App private keys in both
Actions and Dependabot. Keep production, application, SSH and Project-token
secrets outside Dependabot. A human PR smoke test does not prove Dependabot access.

Use `gpt-6-luna` for OpenAI code, build and security reviewers and security-alert
grouping. Preserve each reviewer's key/project isolation, budgets and blocking
gates. Application AI model selection remains app-owned.

Meal estimation keeps `MACROMAPPER_OPENAI_API_KEY`, with separate production
and local keys/projects. Store local values only in ignored `backend/.env` or
`deploy/.env`; production values enter the approved private release bundle via
the Actions repository secret. Never store keys in `deploy/.env.example`.

## ✉️ Email delivery

Use the pinned django-anymail Resend backend directly; do not recreate a custom
provider wrapper. Preserve console-local and explicit SMTP/custom selections,
existing credentials, bounded API timeout with the 10-second fallback, disabled
API dumps and no automatic retries. Missing-key configuration errors must fail
before HTTP. Keep generic reset responses and safe caller-only error logging;
never log exception/provider bodies, recipients, reset tokens or credentials.
Use mocked Requests-boundary tests in `backend/config/tests/` and the
retained authentication privacy tests. No live mail or new webhook routes are
part of this contract; see the [backend guide](backend/README.md#-email).

## 🔌 MCP integration

Shared MCP framework changes originate in FullStackTemplate's canonical Python
package; synchronize reviewed runtime changes across consumers and record source
commits in the coordinated tracking issue. Derived applications own enablement,
registries, scopes and business tools. Infrastructure supplies ordinary gateway
routing and its optional MCP contract. Preserve existing Notoli credentials,
scopes, tool permissions, connection and exact proxy trust. The retired central
issuer is not a deployment prerequisite. Advertise an app service only after its
own registry, OAuth and readiness checks pass; framework adoption alone does not
authorize activation, client registration, owner consent or plugin installation.

Follow the [app MCP contract](backend/apps/mcp/README.md#application-tools) and
[MacroMapper #284](https://github.com/VanillaIceCube/MacroMapper/issues/284).
MacroMapper owns OAuth, existing-account consent, its registry and scopes;
shared framework changes stay canonical and identical across consumers. Preserve REST JWT/login behavior and
exact trusted peer `172.20.0.3`. Read is the default scope. MCP additions,
field/item-collection edits and read flags execute directly through a closed allowlist
with an automatically generated request UUID and atomic durable receipt. Paid AI
executes directly with read/write/estimate scopes and a durable reservation before
provider I/O. Only food archive, meal/proposal/notification deletion and notification
clearing require preparation and separate approval by the matching signed-in app user.
Meal creation/drafts require explicit nonblank names; nonpaid actions never call AI.
Optional preparation of any non-removal request, including paid work, cannot be
downgraded through direct execution. Never fabricate an approved state for direct work.
The app JWT-only approval channel is independent of the MCP bearer; a client
boolean or OAuth grant cannot set approval. Keep exact payload/target/catalog,
client/token/owner/scope binding, five-minute expiry, cancellation and one-use
consumption. Generate request UUIDs automatically, retain durable receipts and
never retry uncertain paid calls under a new UUID automatically. Recheck grants
and ownership, keep provider waits outside writer transactions, and commit
publication with its receipt atomically. Preserve host consent/safety controls.

Use the existing optional shared framework approval hook and Connections screen;
Notoli uses the same hook for sensitive actions, with its own scopes and domain
snapshots. FullStackTemplate leaves the hook unavailable. Shared framework/UI
source remains identical; paid-provider behavior is MacroMapper-specific. Approval verifies an explicit decision using the matching app user's
credentials, not physical human presence or protection against compromise of those
credentials. See the [threat model](backend/apps/mcp/README.md#-access-and-permissions).
Preserve required CI and independent review gates.

Production policy and frontend Docker builds enable the reviewed app connector;
local backend defaults remain off. Run both backend profiles and frontend tests,
plus disposable app release tests and parity checks. Preserve SQLite capture and
explicit recovery. A failed first enable uses the retained previous disabled
controller and its readiness policy, never an edited enabled bundle. Client
registration, owner consent and plugin installation remain separate actions.

## 🧩 Repository-specific contracts

Preserve MacroMapper's AI/data and domain contracts in the
[backend README](backend/README.md), [frontend README](frontend/README.md),
[catalog identity guide](backend/README.md#-canonical-food-identity),
[meal interpretation guide](backend/README.md#-meal-interpretation-and-portions) and
[nutrition integrity guide](backend/README.md#-nutrition-evidence). Catalog/manual diary
work needs no AI key. Keep provider calls mocked in tests, bounded estimation
budgets, draft preservation and atomic publication; do not publish late results.
Preserve source/confidence/provenance, historical nutrition snapshots, food
identity/portion semantics and private user adjustments. Keep frontend domain
modules independent of React/presentation and use their public entry points.

Frontend uses Vite, Vitest/jsdom, ESLint 10 and `frontend/dist/`; production API
requests remain same-origin with blank `VITE_API_BASE_URL`. Keep compatible
Material UI/icon versions and dependency overrides documented in the frontend
README. The estimates suite remains a discoverable `apps/estimates/tests/` package;
root-level full backend discovery requires `uv run --locked --project backend python backend/manage.py test backend`.
