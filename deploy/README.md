# MacroMapper deployment

The production-style stack uses Docker Compose:

- `proxy`: Nginx on ports 80 and 443
- `backend`: Django and Gunicorn on port 8000
- `frontend`: Nginx serving the React build on port 3000

The Compose project name is fixed to `macromapper`, keeping its network and
service lifecycle separate from Notoli.

The expected public host is `macromapper.judeandrewalaba.com`.

Host ports default to `80`, `443`, `8000`, and `3000`. Local `.env` values
`MACROMAPPER_HTTP_PORT`, `MACROMAPPER_HTTPS_PORT`, `MACROMAPPER_BACKEND_PORT`,
and `MACROMAPPER_FRONTEND_PORT` can override them when another stack is already
using the defaults.

## Local Docker setup

1. Copy `deploy/backend.env` to `deploy/.env` and fill local values.
   To coexist with Notoli, a useful set of overrides is `8080`, `8443`, `8001`,
   and `3001`.
2. Create the SQLite bind-mount file:

   ```powershell
   New-Item -ItemType File -Path deploy/db.sqlite3 -Force
   ```

3. Put local TLS files at `certs/origin.pem` and `certs/origin.key`.
4. Build images from the current checkout:

   ```powershell
   docker build -t ghcr.io/vanillaicecube/macromapper-backend:latest ./backend
   docker build --build-arg REACT_APP_API_BASE_URL= -t ghcr.io/vanillaicecube/macromapper-frontend:latest ./frontend
   ```

5. Start and migrate:

   ```powershell
   Set-Location deploy
   docker compose up -d
   docker compose exec -T backend python manage.py migrate
   ```

## Routing

`deploy/nginx-proxy.conf` routes:

- `/` and SPA deep links to the frontend
- `/auth/*` to Django authentication
- `/admin/*` to Django admin
- `/api/*` to future Django REST endpoints
- Django admin and DRF static files to the backend

HTTP redirects to HTTPS. The origin certificate is mounted at `/etc/nginx/certs`.
The frontend container repeats the `/auth/`, `/api/`, and `/admin/` proxy routes
so its exposed host port can also be used for local HTTP testing.

## Production configuration

Recommended repository variables:

```text
DEPLOY_PATH=/root/apps/macromapper
DJANGO_ALLOWED_HOSTS=macromapper.judeandrewalaba.com
DJANGO_CORS_ALLOWED_ORIGINS=https://macromapper.judeandrewalaba.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://macromapper.judeandrewalaba.com
DJANGO_FORCE_SCRIPT_NAME=
DJANGO_FRONTEND_BASE_URL=https://macromapper.judeandrewalaba.com
DJANGO_SQLITE_PATH=/backend/db.sqlite3
```

Leave `REACT_APP_API_BASE_URL` blank for same-origin authentication calls.

Required deploy secrets:

- `DEPLOY_SSH_KEY`
- `DJANGO_SECRET_KEY`
- `DJANGO_EMAIL_HOST_KEY`
- `CLOUDFLARE_ORIGIN_CERT_PEM`
- `CLOUDFLARE_ORIGIN_KEY_PEM`

The deployment workflow builds and pushes both GHCR images, uploads the Compose/Nginx bundle and optional TLS material, writes the server `.env`, recreates containers, and runs migrations.

## Cloudflare

- Create DNS for `macromapper.judeandrewalaba.com`.
- Use SSL/TLS mode `Full (strict)`.
- Ensure the origin certificate covers the MacroMapper host.
- Avoid edge caching for `/auth/*`, `/api/*`, and `/admin/*`.
