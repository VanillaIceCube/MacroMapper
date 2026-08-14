# FullStackTemplate backend
The backend is a Django REST Framework application with JWT authentication, a
custom user model whose email address is unique, password-reset email delivery,
and a generic recipient-scoped notification API.

## Structure
- `app/`: Django settings, URL routing, ASGI, and WSGI
- `authentication/`: custom user, registration, login, refresh, password reset,
  and email delivery
- `notifications/`: generic persisted notifications for the authenticated app
  header
- `environment.yml`: Conda environment definition
- `requirements.txt`: pip dependencies used locally, in CI, and in Docker
- `ruff.toml`: backend lint and formatting configuration

Application-specific models and APIs intentionally do not ship with the
template. Add new Django apps beside `authentication` and `notifications`.

## Authentication API
- `POST /auth/register/`
  - Body: `email`, `password`, and optional `username`
  - Returns: `access`, `refresh`, `username`, `email`, and a success message
- `POST /auth/login/`
  - Body: `email`, `password`
  - Returns: `access`, `refresh`, `username`, and `email`
- `POST /auth/refresh/`
  - Body: `refresh`
  - Returns a new access token
- `POST /auth/forgot-password/`
  - Body: `email`
  - Always returns a generic success response for valid email-shaped input
- `POST /auth/reset-password/`
  - Body: `uid`, `token`, `password`

## Notification API
All `/api/` endpoints require a JWT access token. Notification querysets are
always scoped to the authenticated recipient.

- `GET /api/notifications/`
- `PATCH /api/notifications/{id}/` with `{"is_read": true}` or
  `{"is_read": false}`
- `DELETE /api/notifications/{id}/`
- `PATCH /api/notifications/mark-all-read/`
- `DELETE /api/notifications/clear-all/`

Notifications retain a generic event type, title, message, optional actor, and
optional frontend `target_path`. Future application apps can create them
without depending on a template-owned domain model.

## Local setup
From the repository root:

```powershell
python -m pip install -r backend/requirements.txt
python backend/manage.py migrate
python backend/manage.py runserver 8000
```

Optional `backend/.env` values are loaded automatically:

```env
DJANGO_SECRET_KEY=local-only-key
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,fullstacktemplate.localhost
DJANGO_CORS_ALLOWED_ORIGINS=http://fullstacktemplate.localhost:3000
DJANGO_CSRF_TRUSTED_ORIGINS=http://fullstacktemplate.localhost:3000
DJANGO_FRONTEND_BASE_URL=http://fullstacktemplate.localhost:3000
```

The default database is `backend/db.sqlite3`. Override it with
`DJANGO_SQLITE_PATH`. The `fullstacktemplate.localhost` host is accepted by
default.

## Docker hot reload
The development Compose workflow builds `backend/Dockerfile.dev`, mounts the
backend source, and runs Django's autoreloading development server:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml up --build -d backend
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml exec -T backend python manage.py migrate
```

The development backend listens on `http://fullstacktemplate.localhost:8000`.
Use the production Dockerfile and Compose file when testing Gunicorn, Nginx,
HTTPS, or deployment-shaped behavior.

## Email
Local development defaults to Django's console email backend. Production can
use the included Resend HTTPS backend:

```env
DJANGO_EMAIL_BACKEND=authentication.email_backends.ResendApiEmailBackend
DJANGO_EMAIL_HOST_KEY=<resend-api-key>
DJANGO_EMAIL_TIMEOUT=10
DJANGO_DEFAULT_FROM_EMAIL=fullstacktemplate.no-reply@example.com
```

SMTP-compatible backends can instead use the documented `DJANGO_EMAIL_HOST`,
`DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_USE_TLS`, and
`DJANGO_EMAIL_HOST_USER` settings.

## Checks
```powershell
python backend/manage.py test
ruff check backend
ruff format backend --check
```
