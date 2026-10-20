# Local Docker development

For shared-host deployment, use the [production release and recovery guide](production/README.md).
The commands below operate local development stacks.

API proxies in standalone HTTPS and the frontend image allow 120 seconds for
an upstream response. The backend's default 110-second total AI budget leaves
time to return a controlled error. Production uses the separately owned
Infrastructure gateway with the same 120-second API read timeout.

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

## Local persistence and troubleshooting

Both local stacks use `deploy/db.sqlite3`; keep it when restarting containers.
The hot-reload stack mounts the backend and frontend source trees. Ordinary
source edits are picked up by Django/Vite; rebuild after dependency or Dockerfile
changes. Never replace an existing database with an empty file during setup.

Inspect the hot-reload stack from the repository root:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml ps
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml logs --tail 100 backend frontend
```

If a port is occupied, set the `MACROMAPPER_DEV_*_PORT` variables above and
recreate the local stack. For standalone HTTPS, use its `MACROMAPPER_*_PORT`
variables instead and verify that the ignored certificate files exist. If the
browser does not resolve `macromapper.localhost`, add a local hosts entry for
`127.0.0.1 macromapper.localhost`.

## 🔑 Local estimation key

Set `MACROMAPPER_OPENAI_API_KEY` in ignored `deploy/.env` to the
`Local · Application · AI Estimate` key from `MacroMapper Development`. Recreate
the backend container after changing it; a plain restart does not reload env-file
values:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml up -d --force-recreate backend
```

Never add a real key to the tracked
`deploy/backend.env` example. Production uses a separate key and the approved
release procedure; see the [credential migration guide](../.github/README-WORKFLOWS.md#-independent-estimation-credentials).
