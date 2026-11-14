# 🛠️ MacroMapper backend

The Django REST Framework backend owns application data, authentication,
permissions, notifications, and application integrations.

## 🧭 Structure

- `app/`: settings and server entry points.
- `foods/`, `estimates/`, `meals/`: catalog, proposals, and diary.
- `authentication/`, `notifications/`: accounts and notifications.
- `macromapper_mcp/`, `mcp_framework/`: application tools and shared MCP.

## 💻 Local development

Use Python 3.12 in an isolated environment. From the repository root:

```powershell
python -m pip install -r backend/requirements.txt
python backend/manage.py migrate
python backend/manage.py runserver 8000
```

Local settings can be supplied in ignored `backend/.env`. See the
[configuration and API reference](REFERENCE.md) for settings and endpoint details.
For Docker hot reload, follow the [deployment guide](../deploy/README.md).

Catalog and manual diary work can run without an AI key. AI estimates use
a separate application key; see [local estimation setup](../deploy/README.md#-local-estimation-key).

## 🧪 Checks

From the repository root:

```powershell
python backend/manage.py test backend
ruff check backend
ruff format backend --check
python backend/manage.py makemigrations --check --dry-run
```

## 🔌 MCP integration

The [MCP framework README](mcp_framework/README.md) explains shared transport,
OAuth, configuration, and verification.

Application tools, scopes, consent, and client setup live in the
[MacroMapper MCP README](macromapper_mcp/README.md).

[Plugin packages and client connections](../plugins/README.md) are documented
separately from backend deployment.

## 📚 Reference

Use the [backend reference](REFERENCE.md) for API contracts, configuration,
email delivery, and maintenance details. Live-server procedures belong to
the [production guide](../deploy/production/README.md).


<details>
<summary>API, configuration, and maintenance sections</summary>

<a id="food-identity-recipes-and-portions"></a>

- [Food identity, recipes and portions](REFERENCE.md#food-identity-recipes-and-portions)

<a id="estimates-test-organization"></a>

- [Estimates test organization](REFERENCE.md#estimates-test-organization)

- [🧭 Structure](REFERENCE.md#-structure)

<a id="-authentication-api"></a>

- [🔐 Authentication API](REFERENCE.md#-authentication-api)

<a id="food-catalog-api"></a>

- [Food Catalog API](REFERENCE.md#food-catalog-api)

<a id="meal-diary-api"></a>

- [Meal Diary API](REFERENCE.md#meal-diary-api)

<a id="gpt-meal-proposal-api"></a>

- [GPT Meal Proposal API](REFERENCE.md#gpt-meal-proposal-api)

<a id="-snapshot-and-adjustment-invariants"></a>

- [🧩 Snapshot and adjustment invariants](REFERENCE.md#-snapshot-and-adjustment-invariants)

<a id="-notification-api"></a>

- [🔔 Notification API](REFERENCE.md#-notification-api)

<a id="-local-setup"></a>

- [💻 Local Setup](REFERENCE.md#-local-setup)

<a id="docker-hot-reload"></a>

- [Docker Hot Reload](REFERENCE.md#docker-hot-reload)

<a id="-email"></a>

- [✉️ Email](REFERENCE.md#-email)

- [🧰 Checks](REFERENCE.md#-checks)

<a id="-shared-mcp-framework"></a>

- [🔌 Shared MCP framework](REFERENCE.md#-shared-mcp-framework)

<a id="authentication-and-notification-parity"></a>

- [Authentication and notification parity](REFERENCE.md#authentication-and-notification-parity)

<a id="development-dependency-reproducibility"></a>

- [Development dependency reproducibility](REFERENCE.md#development-dependency-reproducibility)

<a id="disposable-browser-test-backend"></a>

- [Disposable browser-test backend](REFERENCE.md#disposable-browser-test-backend)

<a id="transactional-email-failure-handling"></a>

- [Transactional email failure handling](REFERENCE.md#transactional-email-failure-handling)

<a id="persistence-regression-guidance"></a>

- [Persistence regression guidance](REFERENCE.md#persistence-regression-guidance)

<a id="nutrition-catalog-evidence"></a>

- [Nutrition catalog evidence](REFERENCE.md#nutrition-catalog-evidence)

</details>
