# Deployment guide

Production uses the [app-only release and recovery guide](production/README.md).
The host-owned ingress implementation lives in JudeAndrewAlabaInfrastructure;
MacroMapper releases manage only their backend/frontend, immutable images,
private configuration and SQLite recovery. Activate after the separately
approved gateway and Notoli transition under architecture v2.

The [PR #239 audit](PR239-AUDIT.md) and [earlier handoff](PRODUCTION-LAUNCH-HANDOFF.md)
are historical preparation. Obsolete bridge source is removed; Git history retains it.
Do not run the retired scripts or standalone Compose on the shared host. Installed
live bridge files remain in place until Agent 3's approved cutover and recovery.

## Local Docker with `macromapper.localhost`

For source iteration, copy `backend.env` to `deploy/.env` only if you do not
already have a local environment file, then initialize only a missing database:

```powershell
if (-not (Test-Path deploy/.env)) { Copy-Item deploy/backend.env deploy/.env }
if (-not (Test-Path deploy/db.sqlite3)) { New-Item -ItemType File -Path deploy/db.sqlite3 }
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml up --build -d
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml exec -T backend python manage.py migrate
```

This mounts both source trees, runs Vite and Django autoreload, and uses direct
HTTP ports 3000/8000 on localhost. Override host ports with
`MACROMAPPER_DEV_FRONTEND_PORT`/`MACROMAPPER_DEV_BACKEND_PORT` in `deploy/.env`.
No certificate or Nginx is required. Open `http://macromapper.localhost:3000`.

For standalone HTTPS/image checks, prepare the same local environment/database,
then use:

```powershell
./scripts/create-local-certificate.ps1
docker build -t ghcr.io/vanillaicecube/macromapper-backend:latest ./backend
docker build -t ghcr.io/vanillaicecube/macromapper-frontend:latest ./frontend
Set-Location deploy
docker compose up -d
docker compose exec -T backend python manage.py migrate
```

The optional certificate helper writes `origin.pem`/`origin.key` to ignored
`certs/`. Open `https://macromapper.localhost`. This standalone project owns its
proxy and defaults to ports 80/443/8000/3000; override its `MACROMAPPER_*_PORT`
variables when another local app owns those ports. Do not use this standalone
command on the shared production host.

## Routing and persistence

The host ingress routes `/` and SPA deep links to the frontend; `/auth/`, `/api/`,
`/admin/` and Django static files go directly to the backend. Neither production
app service publishes a host port. Both retain their existing private/egress
networks, and unique ingress aliases prevent cross-app DNS collisions.

SQLite remains `deploy/db.sqlite3` locally and `/opt/apps/macromapper/db.sqlite3`
on the server. Keep one backend replica; use the production guide's explicit
snapshot/restore transaction for recovery. Registration, email, AI and data-write
acceptance require the separately approved operational test scope.
