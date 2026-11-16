# 🐳 MacroMapper deployment

For shared-host deployment, use the [production release and recovery guide](production/README.md).
The commands below operate local development stacks.

API proxies in standalone HTTPS and the frontend image allow 120 seconds for
an upstream response. The backend's default 110-second total AI budget leaves
time to return a controlled error. Production uses the separately owned
Infrastructure gateway with the same 120-second API read timeout.

<a id="local-docker-with-macromapperlocalhost"></a>

## 💻 Local Docker with `macromapper.localhost`

The development Compose `environment` sets the frontend API origin. Production
uses the Docker build argument, which is compiled into the static assets; a blank
value selects same-origin requests. Backend settings remain in `deploy/.env`,
created from the committed `deploy/backend.env` example below.

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
./deploy/create-local-certificate.ps1
docker build --file backend/docker/Dockerfile -t ghcr.io/vanillaicecube/macromapper-backend:latest ./backend
docker build --file frontend/docker/Dockerfile -t ghcr.io/vanillaicecube/macromapper-frontend:latest ./frontend
Set-Location deploy
docker compose up -d
docker compose exec -T backend python manage.py migrate
```

The optional certificate helper writes `origin.pem`/`origin.key` to ignored
`certs/`. Open `https://macromapper.localhost`. This standalone project owns its
proxy and defaults to ports 80/443/8000/3000; override its `MACROMAPPER_*_PORT`
variables when another local app owns those ports. Do not use this standalone
command on the shared production host.

<a id="local-persistence-and-troubleshooting"></a>

## 🛟 Local persistence and troubleshooting

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
release procedure; see the [credential migration guide](../.github/README.md#application-credentials).


## 🔌 Shared MCP framework

The [app MCP guide](../backend/apps/mcp/README.md#application-tools) defines app-owned OAuth, exact proxy trust, readiness and first-enable recovery. Local MCP development uses a disposable database, `DJANGO_MCP_ENABLED=1`, the exact backend/frontend origins and `VITE_MCP_ENABLED=1`, with the production image command selecting ASGI. Ordinary hot reload remains disabled by default. Production enables both sides through its reviewed app policy and frontend Dockerfile; its existing shared Nginx routes belong to Infrastructure.

<a id="development-dependency-reproducibility"></a>

## 📦 Development dependency reproducibility

Both backend Dockerfiles install uv using isolated, binary-only pip with reviewed
SHA-256 hashes from [PyPI's uv 0.13.8 release](https://pypi.org/pypi/uv/0.13.8/json).
The allowlist covers every platform in the pinned Python image: Linux amd64,
arm/v7, arm64/v8, 386 and ppc64le. Unlisted artifacts, altered wheels and source
distributions fail installation. Requirements are passed through stdin; update
the version and all compatible wheel hashes together after artifact verification.

Backend production and development images use the same reviewed Python 3.12
multi-platform image digest, bootstrap pinned uv 0.13.8, and install the committed
`uv.lock` with `uv sync --locked`. Frontend builders use the same immutable Node 26 digest.
Refresh matching tags/digests together after registry verification and a disposable
build/configuration check. Conda and environment export files are no longer used.

The container environment lives at `/opt/venv`, outside the `/backend` source bind
mount. The ignored host `backend/.venv/` is excluded from image builds and never
replaces Linux container dependencies. The backend starts with `uv run --locked`,
which synchronizes that environment when the container starts. After a backend manifest/lockfile change, restart the
backend; ordinary Python edits still hot reload:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml restart backend
```

Backend production/development Dockerfiles live in `backend/docker/`; frontend
Dockerfiles and Nginx configuration live in `frontend/docker/`. Build contexts
remain `backend/` and `frontend/`; Compose and CI select each Dockerfile explicitly.
Each Dockerfile uses its adjacent `Dockerfile.dockerignore` or
`Dockerfile.dev.dockerignore`. Exclusion patterns are still relative to the build
context root. The frontend ignores do not exclude Nginx configuration or
development startup files under `docker/`.

The frontend starts Vite directly with `npm start`. Source hot reload and the
persistent `frontend_node_modules` volume remain. Dependency changes require a
manual install in the running frontend container, followed by a restart:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml exec -T frontend npm ci
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml restart frontend
```

If the frontend is stopped, use `run --rm --no-deps frontend npm ci` with the same
Compose options, then start it again. Keep one dependency volume per checkout.
Compose configuration
checks do not deploy or touch application data.

<a id="non-deploying-repository-validation"></a>

<a id="-repository-validation"></a>

## 🧪 Checks

See [workflow checks and validation](../.github/workflows/README.md#-checks-and-diagnostics).


<a id="-further-reading"></a>

## 📚 Reference

- [Live-server releases and recovery](production/README.md).
- [Backend configuration](../backend/README.md).
- [Frontend development](../frontend/README.md).
