# Deployment guide
The production path is Cloudflare DNS/TLS → DigitalOcean Droplet → Nginx →
React/Django containers. The public application is always a subdomain, and
Nginx serves the frontend and API from one origin.

## GitHub deployment settings
Add these Actions secrets:

```text
DEPLOY_SSH_KEY
DJANGO_SECRET_KEY
DJANGO_EMAIL_HOST_KEY
CLOUDFLARE_ORIGIN_CERT_PEM
CLOUDFLARE_ORIGIN_KEY_PEM
```

- `DEPLOY_SSH_KEY` is the complete private SSH key whose public half is
  authorized for the Droplet deployment user.
- Generate `DJANGO_SECRET_KEY` with:
  `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
- `DJANGO_EMAIL_HOST_KEY` is the Resend API key.
- The Cloudflare values are the complete Origin CA certificate and private-key
  PEM blocks, including their BEGIN/END lines.

Add these Actions variables, replacing the examples:

```text
DEPLOY_HOST=203.0.113.10
DEPLOY_USER=deploy
DEPLOY_PATH=/opt/apps/example-application
DEPLOY_PORT=22

DJANGO_DEBUG=0
DJANGO_SQLITE_PATH=/backend/db.sqlite3
DJANGO_ALLOWED_HOSTS=example-application.example.com
DJANGO_CORS_ALLOWED_ORIGINS=https://example-application.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://example-application.example.com
DJANGO_FORCE_SCRIPT_NAME=
DJANGO_FRONTEND_BASE_URL=https://example-application.example.com

DJANGO_EMAIL_BACKEND=authentication.email_backends.ResendApiEmailBackend
DJANGO_EMAIL_HOST=smtp.resend.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_USE_TLS=1
DJANGO_EMAIL_HOST_USER=resend
DJANGO_EMAIL_TIMEOUT=10
DJANGO_DEFAULT_FROM_EMAIL=Example Application <no-reply@updates.example.com>

REACT_APP_API_BASE_URL=
```

Keep `REACT_APP_API_BASE_URL` blank for same-origin requests. The email host,
port, TLS, and username values are only used if you switch to Django’s SMTP
backend; retaining them makes that change straightforward.

## DigitalOcean
1. Create an Ubuntu 24.04 Droplet with an SSH key, monitoring, backups, and a
   stable public IP.
2. Create a non-root `deploy` user with sudo access and key-only SSH. Disable
   password and direct root SSH after verifying the new login.
3. Apply a DigitalOcean Cloud Firewall allowing inbound TCP 22, 80, and 443.
   Restrict port 22 to trusted administrator IPs when practical. Allow outbound
   DNS, HTTPS, and SMTP/API traffic.
4. Install Docker Engine and the Compose plugin from Docker’s official Ubuntu
   repository.
5. Add `deploy` to the Docker group, reconnect, and verify:

   ```bash
   docker version
   docker compose version
   ```

6. Create the application directory:

   ```bash
   sudo mkdir -p /opt/apps/example-application/certs
   sudo chown -R deploy:deploy /opt/apps/example-application
   touch /opt/apps/example-application/db.sqlite3
   ```

7. If GHCR packages are private, authenticate the Droplet once with a classic
   PAT or fine-grained credential that can read packages:

   ```bash
   echo "$GHCR_READ_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USER --password-stdin
   ```

The deployment workflow uploads Compose, Nginx, and TLS files; writes `.env`;
pulls the latest GHCR images; recreates containers; and runs migrations.
DigitalOcean’s current production guidance recommends SSH key authentication,
a non-root sudo user, cloud firewalls, monitoring, and backups:
[production-ready Droplet setup](https://docs.digitalocean.com/products/droplets/getting-started/recommended-droplet-setup/).

## Cloudflare subdomain and TLS
Assume the app slug is `example-application` and the base domain is
`example.com`.

1. Add or onboard `example.com` in Cloudflare.
2. Add a proxied `A` record:

   ```text
   Type: A
   Name: example-application
   Content: DIGITALOCEAN_DROPLET_IP
   Proxy status: Proxied
   TTL: Auto
   ```

3. Under **SSL/TLS → Origin Server**, create an Origin CA certificate covering
   `example-application.example.com` (or an intentionally chosen wildcard).
4. Store its certificate and private key as
   `CLOUDFLARE_ORIGIN_CERT_PEM` and `CLOUDFLARE_ORIGIN_KEY_PEM`.
5. Set Cloudflare SSL/TLS encryption mode to **Full (strict)**.
6. Do not cache authenticated endpoints. Add cache-bypass rules for
   `/auth/*`, `/api/*`, and `/admin/*` if broader cache rules exist.
7. Keep the Droplet firewall limited to 80/443 and SSH. For tighter origin
   protection, restrict web ports to Cloudflare’s published IP ranges and keep
   those ranges updated.

Cloudflare documents the required hostname-valid origin certificate for
[Full (strict)](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/)
and the dashboard flow for
[Origin CA certificates](https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/).

## Resend password-reset delivery
The included `ResendApiEmailBackend` sends Django email through Resend’s HTTPS
API and needs no extra Python package.

1. Add a sending subdomain such as `updates.example.com` in Resend.
2. Copy every generated SPF, DKIM, and MX record into Cloudflare DNS exactly as
   shown. Email-verification records should be DNS-only unless Resend explicitly
   says otherwise.
3. Wait for Resend to mark the domain verified.
4. Create a sending-only API key and store it as `DJANGO_EMAIL_HOST_KEY`.
5. Set `DJANGO_DEFAULT_FROM_EMAIL` to a sender on the verified domain.
6. Deploy, request a password reset, and confirm the message links back to the
   production application subdomain.

Resend recommends a sending subdomain to isolate reputation and requires SPF
and DKIM verification:
[managing domains](https://resend.com/docs/dashboard/domains/introduction).
If you choose SMTP instead, set
`DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`; Resend’s
documented credentials are host `smtp.resend.com`, username `resend`, API key
as password, and STARTTLS port 587:
[Django SMTP guide](https://resend.com/docs/send-with-django-smtp).

## Run the first deployment
The workflow automatically deploys pushes to `env-prod`. To stage the first
deployment:

```powershell
git switch -c env-prod
git push -u origin env-prod
```

Alternatively, dispatch **Deploy** from GitHub Actions. After it succeeds:

```bash
cd /opt/apps/example-application
docker compose ps
docker compose logs --tail=100 proxy backend frontend
curl -I https://example-application.example.com
```

Keep `env-prod` protected and update it only from reviewed `main`.

## Local Docker with `[application].localhost`
The template itself uses `fullstacktemplate.localhost`. A generated repository
uses the slug passed to `initialize-template.ps1`.

For fast source iteration, use the development Compose file instead of the
production-shaped stack:

```powershell
Copy-Item deploy/backend.env deploy/.env
New-Item -ItemType File -Path deploy/db.sqlite3 -Force
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml up --build -d
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml exec -T backend python manage.py migrate
```

This mounts both source trees, runs React's hot-reload server and Django's
autoreloading `runserver`, and uses direct HTTP ports 3000 and 8000 bound to
localhost only. Set `FULLSTACKTEMPLATE_DEV_FRONTEND_PORT` or
`FULLSTACKTEMPLATE_DEV_BACKEND_PORT` in `deploy/.env` to override the host
ports. It does not require a certificate, Nginx proxy, or shared local
ingress. Open `http://fullstacktemplate.localhost:3000`.

Use the production-shaped commands below when testing HTTPS, Nginx, or the
deployment image path.

```powershell
Copy-Item deploy/backend.env deploy/.env
New-Item -ItemType File -Path deploy/db.sqlite3 -Force
./deploy/create-local-certificate.ps1
docker build -t ghcr.io/vanillaicecube/fullstacktemplate-backend:latest ./backend
docker build -t ghcr.io/vanillaicecube/fullstacktemplate-frontend:latest ./frontend
Set-Location deploy
docker compose up -d
docker compose exec -T backend python manage.py migrate
```

Open `https://fullstacktemplate.localhost`.

The Compose project is named `fullstacktemplate`. Defaults are ports
80/443/8000/3000. FullStackTemplate owns its own proxy and can be run
independently of other application repositories.

Open `https://fullstacktemplate.localhost` after starting the stack. If another
application already owns ports 80/443, override this application's proxy,
backend, and frontend host ports in `deploy/.env` and use that application's
direct host ports instead.

## Routing and persistence
Nginx routes:

- `/` and SPA deep links to the frontend;
- `/auth/*`, `/api/*`, and `/admin/*` to Django;
- Django static files to the backend.

SQLite persists at `deploy/db.sqlite3` locally and in the deployment directory
on the server. Back up that file before destructive server maintenance. For
larger applications, replace SQLite with a managed database before scaling to
multiple backend replicas.
