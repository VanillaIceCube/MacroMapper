# AGENTS.md
FullStackTemplate uses manual setup steps; do not assume Django or Node dependencies are installed.

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

Optional frontend variable:

- `REACT_APP_API_BASE_URL` (development default: `http://localhost:8000`; leave blank in same-origin production)

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
Production is designed for `https://app.example.com` behind Cloudflare and an origin Nginx proxy.

- Frontend: `/`
- Authentication: `/auth/`
- Django admin: `/admin/`
- Notification and future application APIs: `/api/`
- GitHub deployment branch: `env-prod`
- GHCR images: `fullstacktemplate-backend` and `fullstacktemplate-frontend`
- Suggested deployment path: `/root/apps/fullstacktemplate`

Review `deploy/nginx-proxy.conf`, the deploy workflow, Cloudflare settings, and all allowlist/base-URL variables whenever domains or routes change.

## GitHub automation
The copied Notoli automation includes lint, tests, CodeQL, dependency review, npm malware review, Dependabot auto-merge, AI PR reviewers, deployment, and scheduled security-alert aggregation.

Secret-dependent workflows must fail visibly when their credentials are unavailable. Keep GitHub App permissions and the credential separation described in `.github/README-WORKFLOWS.md`.
