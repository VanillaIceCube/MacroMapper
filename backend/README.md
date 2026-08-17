# 🛠️ MacroMapper Backend (Django)
MacroMapper is a personal nutrition and activity tracker. Its backend will
support individual meal/activity histories, reusable Food Items and composite
ingredient breakdowns, source-aware GPT estimates, and factual nutrition
reporting. It does not provide medical, clinical, or prescriptive dietary
advice.

The current Django REST Framework implementation supplies JWT authentication,
a custom email-first user model, password-reset email delivery, and a
recipient-scoped notification API. It also supplies a source-aware Food Item
catalog with versioned definitions, components, nutrients, and private personal
foods, plus an owner-scoped meal diary with durable food, component, and
nutrient snapshots. See the [product vision](../docs/PRODUCT_VISION.md) for the
remaining roadmap.

## 🧭 Structure
- `app/`: Django settings, URL routing, ASGI, and WSGI
- `authentication/`: custom user, registration, login, refresh, password reset,
  and email delivery
- `foods/`: reusable Food Items, immutable versions, components, nullable
  nutrient columns, source references, and authenticated catalog APIs
- `meals/`: private dated meal entries, immutable saved component/nutrient
  snapshots, owner-scoped CRUD, and daily totals
- `notifications/`: persisted notifications for the authenticated app
  header
- `environment.yml`: Conda environment definition
- `requirements.txt`: pip dependencies used locally, in CI, and in Docker
- `ruff.toml`: backend lint and formatting configuration

Goals, activity, and GPT-estimation domains remain separate planned apps. The
`foods` app provides their shared catalog foundation without taking ownership
of diary history.

## 🔐 Authentication API
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

## Food Catalog API
All food and nutrient endpoints require a JWT access token.

- `GET /api/foods/`
  - Returns active shared foods plus personal foods owned by the current user.
  - Accepts `?search=` for case-insensitive name and provider lookup.
- `GET /api/foods/{id}/`
  - Returns the current serving, provenance, confidence, nutrients, sources,
    and exact component-version references.
- `POST /api/foods/`
  - Creates a private personal Food Item and its first definition.
- `PATCH /api/foods/{id}/`
  - Updates owned identity fields and creates a new immutable definition when
    `definition` is supplied.
- `DELETE /api/foods/{id}/`
  - Archives an owned personal food without erasing its definitions.
Shared foods are read-only through the user API. Other users' personal foods
resolve as not found. Composite definitions store quantities as a decimal count
of each child's serving and pin the exact child version, so later catalog edits
do not rewrite a composite.

Nutrient columns use canonical units and apply to the definition's declared
serving: calories (`kcal`); protein, carbohydrates, fat, fiber, and sugar (`g`);
and sodium and cholesterol (`mg`). A null column means unavailable, while an
explicit zero means a known zero. Additional nutrients can be introduced with
nullable schema migrations so existing catalog versions remain unknown rather
than being rewritten as zero.

Create and update requests supply a nested `definition` object:

```json
{
  "name": "Example toast",
  "origin_type": "branded",
  "provider_name": "Example Bakery",
  "definition": {
    "serving_quantity": "1",
    "serving_unit": "item",
    "serving_label": "one slice",
    "provenance": "user_entered",
    "confidence_score": null,
    "nutrients": {
      "calories": "80",
      "fiber": "0"
    },
    "sources": [],
    "components": []
  }
}
```

## Meal Diary API
All meal endpoints require a JWT access token and expose only the authenticated
user's entries.

- `GET /api/meals/?date=YYYY-MM-DD`
- `GET /api/meals/{id}/`
- `POST /api/meals/`
- `PATCH /api/meals/{id}/`
- `DELETE /api/meals/{id}/`
- `GET /api/meals/daily/?date=YYYY-MM-DD`
  - Returns the day's meals and summed nutrient snapshots.

Create requests provide `entry_date`, `name`, optional `notes`, and
`item_inputs`. Each item contains a visible `food_item`, positive `servings`,
and a unique `order`. Saved items pin and copy the selected Food Item version,
including its nested composite components and nullable nutrient columns.
Editing an existing item submits its returned `food_version_id` as
`food_version` so quantity changes continue to use the original snapshot even
if the catalog has since changed.

## 🔔 Notification API
All `/api/` endpoints require a JWT access token. Notification querysets are
always scoped to the authenticated recipient.

- `GET /api/notifications/`
- `PATCH /api/notifications/{id}/` with `{"is_read": true}` or
  `{"is_read": false}`
- `DELETE /api/notifications/{id}/`
- `PATCH /api/notifications/mark-all-read/`
- `DELETE /api/notifications/clear-all/`

Notifications retain an event type, title, message, optional actor, and
optional frontend `target_path`. MacroMapper's nutrition and activity apps can
create them without coupling notification delivery to a specific domain model.

## 💻 Local Setup
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

The default database is `backend/db.sqlite3`. Override it with
`DJANGO_SQLITE_PATH`. The `macromapper.localhost` host is accepted by
default.

## Docker Hot Reload
The development Compose workflow builds `backend/Dockerfile.dev`, mounts the
backend source, and runs Django's autoreloading development server:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml up --build -d backend
docker compose --env-file deploy/.env -f deploy/docker-compose.dev.yml exec -T backend python manage.py migrate
```

The development backend listens on `http://macromapper.localhost:8000`.
Use the production Dockerfile and Compose file when testing Gunicorn, Nginx,
HTTPS, or deployment-shaped behavior.

## ✉️ Email
Local development defaults to Django's console email backend. A local-only
sender can be configured while messages remain in the console:

```env
DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DJANGO_DEFAULT_FROM_EMAIL=MacroMapper <no-reply@macromapper.localhost>
```

Production can use the included Resend HTTPS backend with a sender on the
verified production sending domain:

```env
DJANGO_EMAIL_BACKEND=authentication.email_backends.ResendApiEmailBackend
DJANGO_EMAIL_HOST_KEY=<resend-api-key>
DJANGO_EMAIL_TIMEOUT=10
DJANGO_DEFAULT_FROM_EMAIL=MacroMapper <no-reply@updates.judeandrewalaba.com>
```

Resend requires `DJANGO_DEFAULT_FROM_EMAIL` to use a domain verified in the
Resend account. The `.localhost` sender is only for console-email development
and must not be used with `ResendApiEmailBackend`. See the
[deployment guide](../deploy/README.md#resend-password-reset-delivery) for the
production DNS and credential setup.

SMTP-compatible backends can instead use the documented `DJANGO_EMAIL_HOST`,
`DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_USE_TLS`, and
`DJANGO_EMAIL_HOST_USER` settings.

## 🧰 Checks
```powershell
python backend/manage.py test
ruff check backend
ruff format backend --check
```
