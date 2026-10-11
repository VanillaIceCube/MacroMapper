# Deployment guide

Production uses Cloudflare → **Notoli's existing Nginx** → MacroMapper's private
frontend/backend containers at `https://macromapper.judeandrewalaba.com`.
[#238](https://github.com/VanillaIceCube/MacroMapper/issues/238) covers the minimum
launch prerequisites. Repository preparation and live acceptance are separate.

## Files and Compose commands

| File | Purpose |
| --- | --- |
| `docker-compose.dev.yml` | Local source mounts, Django autoreload, Vite hot reload; HTTP on localhost ports. |
| `docker-compose.yml` + `nginx-proxy.conf` | Standalone, production-shaped local HTTPS stack with its own proxy. |
| `docker-compose.shared.yml` | Production overlay: disables MacroMapper's proxy, removes published app ports, uses revision-tagged images and the external ingress network. |
| `nginx-shared.conf` | Additional hostname vhost mounted in Notoli's public proxy; routes MacroMapper only. |
| `notoli.compose.override.yml` | One-time template installed as Notoli's `docker-compose.override.yml`; preserves Notoli's original networks and adds the vhost/network. |
| `../scripts/prepare-production-bundle.py` | Validates production values and stages configuration plus private environment files in CI. |
| `../scripts/deploy-production.sh` | Pulls the selected images, saves recovery files, migrates, and starts only MacroMapper's app services. |

Shared production commands always include both MacroMapper Compose files:

```bash
cd /opt/apps/macromapper
docker compose -f docker-compose.yml -f docker-compose.shared.yml ps
docker compose -f docker-compose.yml -f docker-compose.shared.yml logs --tail=100 macromapper-backend macromapper-frontend
```

Use Compose **2.30 or newer**, including `!reset`/`!override` merge support and
[`env_file.format: raw`](https://docs.docker.com/reference/compose-file/services/#env_file).
The recorded Droplet version is 2.40.3. Raw environment files preserve literal
`$` and quotes in credentials. Do not source `.backend.env` in a shell.

## GitHub deployment settings

The **Deploy** workflow runs on `env-prod` pushes, or manual dispatch selecting
`env-prod`. Update that branch only from reviewed `main`; do not dispatch this
PR's draft branch. It builds both images for that workflow's full commit SHA
and deploys `:sha-<commit>` references. Published `latest` tags are not selected
by the deployment script.

Required Actions secrets:

```text
DEPLOY_SSH_KEY
DJANGO_SECRET_KEY
DJANGO_EMAIL_HOST_KEY
MACROMAPPER_OPENAI_API_KEY
```

Use MacroMapper's credentials, not Notoli's application secrets or the AI
reviewers' `OPENAI_API_KEY`. Generate the Django key locally with
`python -c "import secrets; print(secrets.token_urlsafe(64))"` and store it
privately. Confirm that the existing deployment user/key can access the Droplet
and application directory. No new account or SSH policy is required by this PR.

Required Actions variables:

```text
DEPLOY_HOST=64.23.173.170
DEPLOY_USER=<confirmed existing deployment user>
DEPLOY_PATH=/opt/apps/macromapper
DJANGO_ALLOWED_HOSTS=macromapper.judeandrewalaba.com
DJANGO_CORS_ALLOWED_ORIGINS=https://macromapper.judeandrewalaba.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://macromapper.judeandrewalaba.com
DJANGO_FRONTEND_BASE_URL=https://macromapper.judeandrewalaba.com
DJANGO_EMAIL_BACKEND=authentication.email_backends.ResendApiEmailBackend
DJANGO_DEFAULT_FROM_EMAIL=MacroMapper <sender@verified-sending-domain>
```

Optional variables and their defaults:

```text
DEPLOY_PORT=22
DJANGO_FORCE_SCRIPT_NAME=
DJANGO_EMAIL_HOST=smtp.resend.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_USE_TLS=1
DJANGO_EMAIL_HOST_USER=resend
DJANGO_EMAIL_TIMEOUT=10
OPENAI_MEAL_ESTIMATION_MODEL=gpt-5.6-luna
OPENAI_MEAL_ESTIMATION_TIMEOUT=45
VITE_API_BASE_URL=
```

The bundle fixes `DJANGO_DEBUG=0` and `DJANGO_SQLITE_PATH=/backend/db.sqlite3`.
The host and origin variables must contain only the production application.
`DJANGO_FORCE_SCRIPT_NAME` and `VITE_API_BASE_URL` must remain blank for subdomain
root, same-origin routing. Missing credentials and invalid routing fail before
uploading or starting services. The frontend contains no application secrets.

The Droplet needs permission to pull both GHCR images. If packages are private,
confirm its existing Docker login with a package-read credential under the
actual deployment user; CI's `GITHUB_TOKEN` authenticates image publication only.
Do not print credentials or reuse Notoli's application credentials.

## One-time setup on the existing Droplet

These commands are for the deployment chat/operator after reviewing this PR.
Repository preparation does not execute them or change live Notoli.

1. Confirm the existing Docker/Compose versions, deployment user, GHCR access,
   MacroMapper database location, and Origin CA files. Preserve any existing
   MacroMapper database before moving it; stop its writers or use SQLite's
   backup API. Never initialize over existing data. If an older standalone
   MacroMapper stack exists, stop its writers, save a consistent recovery copy,
   and retire only its containers before the first shared-stack deployment.
   Production service names are now `macromapper-backend`/`macromapper-frontend`;
   the old generic service labels cannot be reused under those names. Preserve
   the database file and leave Notoli's containers running.
2. Prepare the agreed application directory and network as the deployment user:

   ```bash
   umask 077
   mkdir -p /opt/apps/macromapper
   chmod 700 /opt/apps/macromapper
   docker network inspect macromapper-ingress >/dev/null 2>&1 || docker network create macromapper-ingress
   ```

3. Copy the reviewed `nginx-shared.conf` into that directory **before** mounting
   it. Install `notoli.compose.override.yml` as
   `/root/apps/notoli/docker-compose.override.yml`. If an override already
   exists, merge these additions into it instead of overwriting it. If the
   application directory differs, update the absolute vhost source path in
   the override to match `DEPLOY_PATH`.

   For a reviewed checkout available on the server, the file installation is:

   ```bash
   reviewed_checkout=/path/to/reviewed/MacroMapper
   install -m 644 "$reviewed_checkout/deploy/nginx-shared.conf" /opt/apps/macromapper/nginx-shared.conf
   if [ -e /root/apps/notoli/docker-compose.override.yml ]; then
     echo 'Merge the template into the existing override manually.'
   else
     install -m 644 "$reviewed_checkout/deploy/notoli.compose.override.yml" /root/apps/notoli/docker-compose.override.yml
   fi
   ```

4. In `/root/apps/notoli`, validate the combined config with `docker compose
   config --quiet` and inspect its non-secret ports/network fields. Retain
   public ports 80/443, the existing default network and private network,
   proxy address `172.30.88.2`, backend address `172.30.88.3`, and existing
   backend trust settings. Notoli's backend must not join MacroMapper's ingress
   network. Save the previous override/config for recovery.
5. Apply the override to **only** Notoli's proxy, with the deployment chat's
   authorization for the brief proxy restart:

   ```bash
   cd /root/apps/notoli
   docker compose up -d --no-deps proxy
   docker exec notoli-proxy nginx -t
   docker inspect notoli-proxy --format '{{json .NetworkSettings.Networks}}'
   ```

   Check Notoli over HTTPS immediately. On failure, restore the previous
   override and recreate only that proxy. MacroMapper's vhost uses Docker's
   runtime DNS resolver so Notoli's proxy can start while MacroMapper is absent.

Notoli's normal deployment uses plain `docker compose` in its directory. Compose
loads the override automatically; normal uploads of the base Compose/Nginx
files do not replace it. An invocation with explicit `-f` files must include
this override. Confirm this behavior after a normal Notoli redeployment during
live acceptance. Do not edit Notoli's source files or private-network setup.

## Cloudflare and TLS

The proxied MacroMapper DNS record and **Full (strict)** were reported configured.
The existing Origin CA certificate at `/root/apps/notoli/certs/origin.pem` and
key at `origin.key` cover the application hostname. Confirm validity and mount
before launch; keep the key owner-readable only (`0600`) and retain the existing
Notoli TLS mount. MacroMapper CI does not upload TLS files, require Cloudflare
TLS secrets, or replace Notoli's certificate.

The vhost redirects HTTP to HTTPS and sets the upstream protocol to `https`,
ignoring a client-supplied forwarded protocol/host. Django uses its real Host
header and secure session/CSRF cookies in production. Nginx returns `no-store`
for `/auth/`, `/api/`, and `/admin/`; confirm Cloudflare does not override that
with a broader cache rule. See Cloudflare's
[Full (strict) requirements](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/).

## Resend password-reset delivery

The existing `ResendApiEmailBackend` uses HTTPS with no new Python dependency.
Confirm the sending domain is verified in Resend, the sender belongs to it, and
`DJANGO_EMAIL_HOST_KEY` is MacroMapper's usable sending key. Confirm a real
password-reset email arrives and points back to the production frontend.
Console email is rejected by deployment validation.

SMTP remains supported with `DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`;
the documented defaults are `smtp.resend.com`, port 587, STARTTLS, user `resend`,
and the API key as password. See the official
[Resend Django SMTP guide](https://resend.com/docs/send-with-django-smtp).

## Deployment and recovery

CI uploads reviewed files and private `.env.next`/`.backend.env.next` files into
the application directory. `deploy-production.sh` checks the network/vhost
mount and proxy network membership, validates Nginx/Compose, and pulls both revision-tagged images before
stopping the MacroMapper backend. It initializes `db.sqlite3` only when missing,
refuses a directory/symlink at that path, and saves the previous release,
credentials, and a consistent SQLite backup under `backups/<timestamp>-<pid>/`
before migrations. Application directories/backups are `0700`; environment and
database files are `0600`. There is no host-wide Docker pruning or Notoli
container recreation in MacroMapper's deployment workflow.

The backup container runs as the deployment user's UID/GID so that the recovery
file remains owned by that user, including when deployment uses a non-root
Docker-group account. No server account or SSH policy changes are required.

The script rejects a running/existing backend container with the old generic
Compose service label before touching the database or stopping services. Complete
the one-time legacy-stack preservation/retirement step first if this check fails.

Django's deployment check runs before migration. Assess its warnings: `W004`
reflects the deferred HSTS policy; `W008` reflects HTTPS redirection at Nginx
rather than Django. No warning is silenced. Missing secure cookies, weak keys,
or unexpected warnings need investigation before launch. This work does not
add HSTS coverage/preload policy or change model, quota, or rate-limit behavior.

After successful migration the script starts MacroMapper's two app services, validates
and reloads the existing public proxy, and records image references in
`deployed-release.env`. A failed migration leaves the backend stopped and the
recovery files intact; investigate or restore before reopening traffic.

For a redeployment of the same revision, dispatch **Deploy** on the unchanged
`env-prod` revision. For a later release, move `env-prod` to its reviewed commit.
To recover after a failed migration, choose the recorded recovery directory:

```bash
cd /opt/apps/macromapper
recovery=backups/<recorded-timestamp-pid>
docker compose -f docker-compose.yml -f docker-compose.shared.yml stop macromapper-backend
# With all MacroMapper SQLite writers stopped:
cp "$recovery/.env" .env
cp "$recovery/.backend.env" .backend.env
cp "$recovery/db.sqlite3" db.sqlite3
chmod 600 .env .backend.env db.sqlite3
docker compose -f docker-compose.yml -f docker-compose.shared.yml up -d --force-recreate macromapper-backend macromapper-frontend
```

Confirm the saved files exist before recovery. On a first deployment there may
be no previous release or database; investigate the failed migration and retry
instead. A backup restore discards writes made after that recovery point, so
choose it deliberately. Restoring only old images after a schema migration is
not sufficient; use the matching database and environment. Retain reviewed
configuration from the previous revision if its deployment layout differs.
Notoli, its database, ingress override, and TLS are outside this recovery path.

## Validation and remaining live acceptance

Repository checks:

```powershell
python -m unittest discover -s deploy/tests -v
python backend/manage.py test
ruff check backend
ruff format backend --check
```

The deployment tests need Docker Compose and OpenSSL. They use disposable,
uniquely named containers/networks and a generated test certificate, validate
routing and untrusted forwarded headers, and start/restart the proxy without
MacroMapper. Linux additionally tests the deployment shell with a fake Docker
executable, including database preservation and failed migrations. CI runs all
of these in the Automation Tests job.

The deployment chat must still confirm credentials/package access, final
revision, installed override/TLS, and host configuration; then check HTTPS for
both apps, registration/login/refresh/logout, password-reset delivery, catalog
search, meal create/edit/delete and totals, an unmatched AI estimate with its
sources, user isolation, and database persistence across a MacroMapper-only
restart/redeployment. Confirm the route survives a normal Notoli redeployment.
Record results and the deployed SHA in #238. Repository checks alone do not
complete #238 or the broader #236.

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

Nginx routes `/` and SPA deep links to the frontend; `/auth/`, `/api/`, `/admin/`,
and Django admin/REST Framework static files to the backend. In shared production,
MacroMapper's published backend/frontend ports and standalone proxy are removed
by the overlay. The backend retains outbound access for Resend/OpenAI.

Production service names are unique so Compose's automatic DNS aliases cannot
collide with Notoli's `backend`/`frontend`. The frontend image's internal
`backend` alias exists only on MacroMapper's own default network, which Notoli's
proxy does not join.

SQLite remains a single bind-mounted file at `deploy/db.sqlite3` locally and
`/opt/apps/macromapper/db.sqlite3` on the server. Keep one backend replica and
use the documented pre-migration recovery files.
