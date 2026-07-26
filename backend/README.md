# MacroMapper backend

The backend is a Django REST Framework application with JWT authentication and a custom user model whose email address is unique.

## Structure

- `app/`: Django settings, URL routing, ASGI, and WSGI
- `authentication/`: custom user, registration, login, refresh, password reset, and email delivery
- `environment.yml`: Conda environment definition
- `requirements.txt`: pip dependencies used locally, in CI, and in Docker
- `ruff.toml`: backend lint and formatting configuration

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
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,macromapper.localhost
DJANGO_CORS_ALLOWED_ORIGINS=http://macromapper.localhost:3000
DJANGO_CSRF_TRUSTED_ORIGINS=http://macromapper.localhost:3000
DJANGO_FRONTEND_BASE_URL=http://macromapper.localhost:3000
```

The default database is `backend/db.sqlite3`. Override it with `DJANGO_SQLITE_PATH`.
The `macromapper.localhost` host is accepted by default.

## Email

Local development defaults to Django's console email backend. Production can use the included Resend HTTPS backend:

```env
DJANGO_EMAIL_BACKEND=authentication.email_backends.ResendApiEmailBackend
DJANGO_EMAIL_HOST_KEY=<resend-api-key>
DJANGO_EMAIL_TIMEOUT=10
DJANGO_DEFAULT_FROM_EMAIL=macromapper.no-reply@example.com
```

SMTP-compatible backends can instead use the documented `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_USE_TLS`, and `DJANGO_EMAIL_HOST_USER` settings.

## Checks

```powershell
python backend/manage.py test
ruff check backend
ruff format backend --check
```
