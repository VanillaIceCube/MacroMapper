# 🥗 MacroMapper
MacroMapper is a personal nutrition and activity tracker. Users will log meals
manually or describe them in natural language, then review an editable,
source-aware GPT estimate before it becomes part of their diary.

It is inspired by the fast daily logging experience of MyFitnessPal, with a
transparent Food Item catalog that can break a restaurant meal into editable
components while allowing each component to be logged on its own. MacroMapper
tracks calories, macros, nutrients, activity, goals, and trends without giving
medical, clinical, or prescriptive dietary advice.

Read the full [product vision and roadmap](docs/PRODUCT_VISION.md).

## ✨ Product Direction

- Individual accounts and private meal/activity histories.
- Manual food logging plus GPT-assisted, editable text-to-meal proposals.
- Reusable Food Items that may be standalone or composed from other Food Items.
- A shared, source-aware catalog with official, community-estimate, and personal
  records kept distinct.
- Daily nutrition goals, activity-adjusted budgets, and factual trend reporting.

## 🤖 GitHub Automation Setup
Start here. The pull-request workflow deliberately exposes missing reviewer
configuration, so add these GitHub repository settings before asking CI to run.

The complete Notoli-derived repository baseline is in
[the GitHub setup guide](docs/GITHUB_SETUP.md#0-match-the-repository-settings).
It covers merge methods, auto-merge, least-privilege Actions permissions, fork
approvals,
Dependabot, secret scanning, CodeQL, required labels, and the main-branch
ruleset. Apply it before opening the first pull request; repository settings are
not configured automatically; apply it before relying on the pull-request gates.

### Required CI and reviewer secrets
Add these under both **Settings → Secrets and variables → Actions → Secrets**
and **Settings → Secrets and variables → Dependabot → Secrets**:

```text
OPENAI_API_KEY
OBI_WAN_CODE_NOBI_PRIVATE_KEY
LINT_EASTWOOD_PRIVATE_KEY
ROBOCOP_PRIVATE_KEY
```

GitHub isolates workflows triggered by Dependabot from the Actions secret
store. Keeping the same four values in the Dependabot store lets its pull
requests run the required AI reviews; GitHub does not provide a way to copy
secret values between the two stores.

Add under **Actions → Variables**:

```text
OPENAI_PROJECT_ID
OBI_WAN_CODE_NOBI_APP_ID
LINT_EASTWOOD_APP_ID
ROBOCOP_APP_ID
```

The three private keys come from three GitHub Apps:

- Obi-Wan Code-nobi reviews application code.
- Lint Eastwood reviews build failures and can push lint-only fixes.
- RoboCop reviews security results and manages security-alert issues.

Use [the GitHub setup guide](docs/GITHUB_SETUP.md) to create the Apps with the
correct minimum permissions, install them on the repository, and create the
matching GitHub Project.

### Required security aggregation settings
```text
Variable: SECURITY_ALERTS_PROJECT_ID
Secret:   SECURITY_ALERTS_TOKEN
```

The Project initializer copies Notoli's Project structure, links the new
repository, verifies its fields/views/workflows, and sets
`SECURITY_ALERTS_PROJECT_ID` automatically.
`SECURITY_ALERTS_TOKEN` is a separate user token with access to that Project.
It is not copied from Notoli and must be created in the new repository. Code
scanning, Dependabot alerts/security updates, secret scanning, and push
protection must also be enabled in repository settings; the exact switches are
listed in the setup guide.

### Deployment settings can wait
The deploy workflow runs only from `env-prod` or manual dispatch. It needs the
DigitalOcean, Cloudflare, and Resend values listed in
[deploy/README.md](deploy/README.md), but those do not block the first
application pull request.

## 🧰 Legacy Template Initializer
MacroMapper began as a reusable application foundation. The initializer remains
for historical maintenance but is not part of the MacroMapper product workflow:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/initialize-template.ps1 `
  -ApplicationName 'ExampleApplication' `
  -ApplicationSlug 'example-application' `
  -ProductionHost 'example-application.example.com' `
  -GitHubOwner 'YOUR_GITHUB_OWNER'
```

Use `-WhatIf` first to preview the files and renames. The initializer updates
display names, Docker/Conda identifiers, GHCR image names, workflow markers,
the production host, and every local host to:

```text
https://[application-slug].localhost
```

That subdomain convention is an invariant of the template. Browsers resolve
`.localhost` names to loopback, so no hosts-file entry is normally needed.
Production uses the same shape: `https://[application-slug].[base-domain]`.
All browser traffic stays same-origin; Nginx routes `/auth`, `/api`, and
`/admin` to Django and all other paths to React.

Review the initializer diff, replace the starter SVG mark, then complete the
GitHub settings above before opening the first PR.

## 🚀 Current Implementation
- React 19, Vite, Vitest, Material UI, and a responsive application shell
- Django REST Framework, custom user model, and versioned migrations
- Email-first registration and JWT login/refresh
- Forgot-password and tokenized reset email delivery through Resend
- Protected routes and automatic session renewal
- Header with a generic navigation drawer, notifications, profile details, and
  logout
- Recipient-scoped notification APIs with read and clear actions
- One intentionally minimal protected Material UI Paper ready to replace with
  application-specific content
- Docker images, Docker Compose, same-origin Nginx proxy, local HTTPS, GHCR,
  SSH deployment, and migrations
- Ruff, ESLint, Prettier, React/Django tests, CodeQL, dependency review, malware
  review, Dependabot, and auto-merge gates
- Three AI reviewer identities and scheduled security-alert-to-Project
  aggregation
- Modified MIT License restricted to non-commercial use

Food, meal, activity, goal, and GPT-estimation features are planned work, not
present application behavior. Their scoped issues live on the
[MacroMapper Project](https://github.com/users/VanillaIceCube/projects/11).

## 🐳 Run Locally In Docker
Requirements: Docker Desktop and either `mkcert` or OpenSSL.

```powershell
Copy-Item deploy/backend.env deploy/.env
New-Item -ItemType File -Path deploy/db.sqlite3 -Force
./deploy/create-local-certificate.ps1

docker build -t ghcr.io/vanillaicecube/macromapper-backend:latest ./backend
docker build -t ghcr.io/vanillaicecube/macromapper-frontend:latest ./frontend

Set-Location deploy
docker compose up -d
docker compose exec -T backend python manage.py migrate
```

Open `https://macromapper.localhost`, register, and log in. The protected
home page contains the reusable application header and a minimal placeholder
Paper.

`deploy/.env`, `deploy/db.sqlite3`, and certificate keys are ignored. Do not
commit them.

## Run Docker Hot-Reload Development
Use the development Compose file when iterating on source code. It mounts the
frontend and backend directories into development containers, so React and
Django reload changes without rebuilding production images:

```powershell
Copy-Item deploy/backend.env deploy/.env
New-Item -ItemType File -Path deploy/db.sqlite3 -Force
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml up --build -d
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml exec -T backend python manage.py migrate
```

Open `http://macromapper.localhost:3000`. The frontend calls Django at
`http://macromapper.localhost:8000`. Both ports bind to localhost only.
To override them, set `MACROMAPPER_DEV_FRONTEND_PORT` or
`MACROMAPPER_DEV_BACKEND_PORT` in `deploy/.env`. Stop this workflow with:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml down
```

This development workflow does not need a local certificate or Nginx proxy.
Use the production Compose workflow above when testing the HTTPS proxy and
deployment-shaped containers.

## 💻 Run Without Docker
Requirements: Python 3.12 and Node.js 24.15 or newer. Docker remains the simplest option
when suitable local runtimes are not already installed.

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

Open `http://macromapper.localhost:3000`.

## ✅ Validate Changes
```powershell
Set-Location frontend
npm run format:check
npm run lint:strict
npm test
npm run build

Set-Location ../backend
ruff format --check .
ruff check .
python manage.py makemigrations --check --dry-run
python manage.py test

Set-Location ..
node --test .github/actions/collect-upstream-major-upgrade-evidence/collect-upstream-major-upgrade-evidence.test.js `
  .github/actions/collect-codeql-evidence/collect-codeql-evidence.test.js `
  .github/actions/publish-ai-review/publish-ai-review.test.js `
  .github/actions/security-alerts/sync-security-alerts.test.js
```

CI runs the same application and automation checks, plus CodeQL, dependency,
malware, AI review gates, and a stable `Auto Merge` status check. The latter
reports every pull request while a separate Dependabot-only job enables
auto-merge for eligible dependency updates.

RoboCop treats a path-scoped CodeQL language skip as expected only when the
scope detector and aggregate gate succeed and the omitted language has a
default-branch baseline. Neutral GitHub summaries for those expected omissions
are informational; failed scope detection, failed gates, and missing baselines
remain review-blocking evidence gaps.

Obi-Wan's review adds an advisory **Major upgrade brief** to Dependabot
semver-major updates. It combines upstream release evidence, primary-source
web research, and a bounded search of tracked repository usage to explain why
the upstream project drew a major-version boundary, whether this application
uses the affected behavior, what the upgrade provides, and what verification
remains. The brief keeps that explanation compact: dependency, why the upgrade
matters, repository impact, recommendation, and sources. The verdict retains
Obi-Wan's calm mentor voice while the structured brief stays technically
direct; it is not an extra merge gate.

## 📚 Documentation
- [Product vision and delivery roadmap](docs/PRODUCT_VISION.md)
- [GitHub Apps, Project, reviewers, and branch rules](docs/GITHUB_SETUP.md)
- [Cloudflare, DigitalOcean, Resend, Docker, and deployment](deploy/README.md)
- [Backend API and email settings](backend/README.md)
- [Frontend routes and component conventions](frontend/README.md)
- [Workflow behavior](.github/README-WORKFLOWS.md)
- [Repository working conventions](AGENTS.md)
- [Changelog](CHANGELOG.md)

## 📜 License
MacroMapper uses the
[Modified MIT License (Non-Commercial Use Only)](LICENSE.md). It permits use,
copying, modification, and distribution for non-commercial purposes; commercial
use requires separate permission from the copyright holder.
