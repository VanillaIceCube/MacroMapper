# 🛠️ MacroMapper backend

The Django REST Framework backend owns application data, authentication,
permissions, notifications, and application integrations.

## 🧭 Structure

- `app/`: settings and server entry points.
- `foods/`, `estimates/`, `meals/`: catalog, proposals, and diary.
- `authentication/`, `notifications/`: accounts and notifications.
- `macromapper_mcp/`, `app_mcp/`: application tools and shared MCP.

## 💻 Local development

Use Python 3.12 in an isolated environment. From the repository root:

```powershell
python -m pip install -r backend/requirements.txt
python backend/manage.py migrate
python backend/manage.py runserver 8000
```

Local settings can be supplied in ignored `backend/.env`.
For Docker hot reload, follow the [deployment guide](../deploy/README.md).

Catalog and manual diary work can run without an AI key. AI estimates use
a separate application key; see [local estimation setup](../deploy/README.md#-local-estimation-key).

## ⚙️ Configuration

Local runs load ignored `backend/.env`. The database defaults to
`backend/db.sqlite3`; set `DJANGO_SQLITE_PATH` to use another local database.
Use `app/settings.py` for current defaults.

| Setting | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` | Stable local signing key and debug mode; use a private key and disable debug in production. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated accepted hosts. |
| `DJANGO_CORS_ALLOWED_ORIGINS`, `DJANGO_CSRF_TRUSTED_ORIGINS` | Explicit frontend origins, including the port during development. |
| `DJANGO_FRONTEND_BASE_URL` | Browser redirects and password-reset links. |
| `DJANGO_EMAIL_BACKEND`, `DJANGO_DEFAULT_FROM_EMAIL` | Delivery backend and sender. |
| `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_USE_TLS` | SMTP configuration when using an SMTP backend. |
| `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_KEY`, `DJANGO_EMAIL_TIMEOUT` | Delivery credentials and timeout; keep credentials out of source control. |

For Docker hot reload and dependency volumes, use the
[deployment README](../deploy/README.md).

Catalog and manual diary workflows need no AI key. Local estimates use a separate
`MACROMAPPER_OPENAI_API_KEY` from the `MacroMapper Development` project; never
reuse reviewer or production credentials. `OPENAI_MEAL_ESTIMATION_MODEL` selects
the model. See [local estimation setup](../deploy/README.md#-local-estimation-key).

`OPENAI_MEAL_ESTIMATION_TIMEOUT` is a shared wall-clock budget for intent
extraction and estimation, default/max 110 seconds. SDK retries are disabled;
two bounded worker slots prevent timed-out calls from creating an unbounded queue.
Late results cannot publish records. Provider waits occur outside database
transactions; publication, proposal and revision writes commit together afterward.
A missing/unavailable provider returns a safe 503 while preserving the draft.
Blank-name meal saves fall back to a sequential name if generation fails.

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

## 🥗 Food catalog API

All food and nutrient endpoints require a JWT access token.

- `GET /api/foods/`
  - Returns active shared foods plus personal foods owned by the current user.
  - Accepts `?search=` for case-insensitive name, provider, and source lookup.
  - Filters combine with search: `scope=personal|shared`, a partial `provider`,
    one or more comma-separated `provenance` values, and
    `origin_type=generic|branded|restaurant`.
  - Accepts bounded `limit` and supported `ordering` parameters so catalog
    browsing does not require loading the full visible catalog.
- `GET /api/foods/{id}/`
  - Returns the current serving quantity/unit and human-readable serving label,
    provenance, confidence, nutrients, sources,
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

## 🍽️ Meal diary API

All meal endpoints require a JWT access token and expose only the authenticated
user's entries.

- `GET /api/meals/?date=YYYY-MM-DD`
- `GET /api/meals/{id}/`
- `POST /api/meals/`
- `PATCH /api/meals/{id}/`
- `DELETE /api/meals/{id}/`
- `POST /api/meals/drafts/` with the complete reviewed meal item tree
  - Creates a meal from the same editable draft used by manual mapping and AI
    review, materializing private food versions only where nutrition or
    components changed.
- `PUT /api/meals/{id}/draft/` with the complete reviewed meal item tree
  - Updates the existing meal in place through the same validation and
    materialization path; unchanged items retain their pinned food versions.
- `POST /api/meals/{id}/adjustments/` with an `adjustment`, the current meal
  details, and editable items
  - Applies the existing constrained AI-adjustment flow to a temporary draft
    and returns it for review without changing the saved meal. The edited meal
    is persisted only when the client subsequently saves it.
- `GET /api/meals/daily/?date=YYYY-MM-DD`
  - Returns the day's meals and summed saved nutrient values.

Create requests provide `entry_date`, `name`, optional `notes`, and
`item_inputs`. Each item contains a visible `food_item`, positive `servings`,
and a unique `order`. Saved items pin and copy the selected Food Item version,
including its nested composite components and nullable nutrient columns.
Editing an existing item submits its returned `food_version_id` as
`food_version` so quantity changes continue to use the original saved values even
if the catalog has since changed.

The draft endpoints accept `entry_date`, `name`, optional `notes`, and `items`
in the meal-proposal review shape. This full tree supports quantity, portion,
nutrition, source, and nested-component edits consistently for manual meals,
AI-reviewed meals, and existing diary entries. Existing archived food versions
remain valid only when they were already pinned by the meal being updated.

## 🤖 Meal proposal API

All proposal endpoints require a JWT access token and expose only the current
user's proposals.

- `GET /api/meal-proposals/`
- `GET /api/meal-proposals/{id}/`
- `POST /api/meal-proposals/` with `description` and `entry_date`
  - Returns descriptions fully resolved by the fast deterministic catalog path
    without calling the model. When that path leaves anything unresolved,
    OpenAI first extracts separate structured food intents containing provider,
    quantity, aliases, and product-defining terms without web search.
  - Resolves each extracted intent independently against visible shared and
    personal catalog foods. Provider constraints and product-defining terms
    prevent a generic or partial match from selecting a different menu item.
    Only intents still unmatched are sent to OpenAI with web search for a full
    nutrition estimate.
  - Materializes the normalized AI result and its components as deduplicated,
    immediately active, read-only shared Food Items only after a server-side
    publication boundary reconstructs allowlisted fields, validates numeric and
    source data, normalizes catalog text, and rejects control, markup, URL-like,
    instruction-like, or personal-metadata payloads. The private proposal
    references those exact versions; its description, date, owner, and review
    state are never copied into the shared catalog.
- `PATCH /api/meal-proposals/{id}/` with edited `name`, `entry_date`, and/or
  `items`
- `POST /api/meal-proposals/{id}/follow-up/` with `follow_up`, the current
  `name`, `notes`, `entry_date`, and current `items`
  - Sends the original description and current reviewed draft to the estimation
    provider, then applies only constrained top-level additions, explicit
    removals, or absolute serving corrections.
  - Preserves existing foods and local review edits, rejects duplicate
    additions, and requires the provider to make a disclosed best-effort
    assumption when a target or portion is ambiguous.
  - Resolves AI-extracted additions against the visible catalog before
    materializing genuinely new shared foods with their sources and provenance,
    then records a separate immutable `ai_follow_up` proposal revision.
- `POST /api/meal-proposals/adjustments/` with an `adjustment`, the current
  builder `name`, `entry_date`, optional `notes`, and editable `items`
  - Creates a draft from manually assembled foods, then applies the requested
    constrained AI adjustment when possible.
- `DELETE /api/meal-proposals/{id}/` for unaccepted drafts
- `POST /api/meal-proposals/{id}/accept/`
  - Reuses unchanged shared definitions. Nutrient or component edits create a
    private `user_modified_estimate` definition linked to the shared base,
    then create a dated meal snapshot and lock the proposal.

Nutrients remain anchored to one declared serving quantity, unit, and label.
GPT supplies a concise natural base such as `1 burger`, `1 plate`, or
`1 medium carrot`, plus the edible gram weight of that serving. The backend
uses that weight to generate validated `portion_options` with a deterministic
Grams conversion for every estimated item and component.
Structured estimates also declare whether nutrient values describe one base
serving or the full consumed amount. Full-amount values are normalized to the
base serving before catalog materialization, and a serving-weight plausibility
check catches obvious mislabeled totals. The diary therefore applies the
proposal's serving count exactly once.

Proposal labels distinguish `official_verified`, `catalog_estimate`,
`ai_estimate`, and `user_modified_estimate`. Generated, user-reviewed, and
accepted proposal revisions preserve immutable item snapshots and parent
lineage. Shared AI food versions retain provider/model/response metadata,
confidence, serving conversions, and source URLs; personal adjustments point
back to the base version without changing it. Exact normalized AI definitions
are fingerprinted so equivalent results reuse one shared Food Item. OpenAI
requests use structured outputs, enable web
search for source discovery, and set `store=false`. They return nutrition data
only and explicitly exclude dietary, medical, clinical, and treatment advice.
Follow-up requests use the same non-stored provider flow and retain the current
draft when the provider is unavailable or cannot produce an applicable change.

## 🧩 Food identity and portions

See [canonical identities and safe duplicate cleanup](../docs/CANONICAL-FOODS.md)
and [meal interpretation semantics](../docs/MEAL-INTERPRETATION.md). Shared food
identity is independent of consumed quantity and nutritional definition. Recipes
retain full-recipe ingredient quantities; their parent servings carry the eaten
fraction. Natural size choices use food-specific weights and remain editable
without creating personal food copies or rewriting older meal snapshots.

## 🗄️ Snapshot and adjustment invariants

Food responses, catalog estimates and meal snapshots share the complete reachable
component graph, loaded in batches by tree level. Reuse the graph and nutrient
caches across meal items instead of issuing separate queries for each child.
Visible catalog-version lookups are also batched during validation/materialization.

`MealItemSerializer` reuses a nonempty persisted component snapshot only after
recursive validation of required fields, identifiers, decimal values, portions,
nutrients, sources and nested components. Missing or malformed legacy snapshots
are rebuilt from the saved food-version graph, preserving pinned history rather
than using the latest catalog definition. Source access dates are ISO strings.

Meal-entry and builder adjustment endpoints share `process_meal_adjustment`.
Provider resolution, follow-up processing and response serialization stay inside
its cleanup boundary: failures delete the created proposal, and successful
temporary meal-entry proposals are deleted after serialization. Missing/null
optional follow-up fields retain existing confidence and provider metadata when
no replacement is supplied. Views inject the response serializer and provider
getter to avoid a service/serializer import cycle and keep provider calls patchable.

## ✉️ Email

Local development uses Django's console email backend. The included
Resend HTTPS backend is configured with:

```env
DJANGO_EMAIL_BACKEND=authentication.email_backends.ResendApiEmailBackend
DJANGO_EMAIL_HOST_KEY=<resend-api-key>
DJANGO_EMAIL_TIMEOUT=10
DJANGO_DEFAULT_FROM_EMAIL=<sender-on-a-verified-domain>
```

Keep `.localhost` senders with console delivery. Live delivery uses an approved
sender domain and private credentials configured through the production guide.
Plain text, HTML, multipart alternatives, `cc`, `bcc`, and `reply_to` are supported.

The socket-operation timeout defaults to 10 seconds and supports `0 < seconds <= 30`.
The environment value is parsed as an integer. Invalid runtime timeout values fall
back safely; malformed startup configuration fails visibly. A successful provider
response means acceptance, not confirmed inbox delivery.

Failures preserve `fail_silently`: false re-raises, while true skips failures and
returns the number sent. Password reset returns a generic response for known and
unknown accounts, including delivery failures. Logger `authentication.email_backends`
records safe category/status fields: `configuration`, `request`, `rate_limit`,
`provider`, `timeout`, `network`, or `unexpected`. Never log provider response
bodies, recipient details, reset tokens, message contents, or credentials.

Diagnose failures using those categories and the existing provider dashboard.
There is no automatic retry or resend: a timeout may occur after acceptance.
Use mocked delivery tests; production email receipt requires separate verification.

## 🔌 MCP integration

The [MCP README](app_mcp/README.md) explains shared transport,
OAuth, configuration, and verification.

Application tools, scopes, consent, and client setup live in the
[MacroMapper MCP README](macromapper_mcp/README.md).

Connection manifests, artwork, and package builders live in
[chatgpt/](app_mcp/chatgpt/README.md).

## 🧪 Checks

From the repository root:

```powershell
python backend/manage.py test backend
ruff check backend
ruff format backend --check
python backend/manage.py makemigrations --check --dry-run
```

## 🧪 Estimates test organization

`estimates/tests/` is a discoverable Python package. Keep its `__init__.py` and
name new modules `test_*.py`; do not recreate a competing `estimates/tests.py`.
Use `test_proposals.py` for proposal API behavior, `test_adjustments.py` for
adjustment lifecycle/rollback, `test_admin.py` for admin immutability, and
`test_provider.py` for provider requests and normalization. Shared data builders
belong in `helpers.py`, which does not define discoverable test classes.

Import helpers with `from .helpers import ...` and app modules with `from
..models import ...` (or their absolute app paths). Patch dependencies where the
code under test looks them up, such as `estimates.services.get_estimation_provider`,
not where test helpers live. Keep provider calls mocked; no API key is needed.

From the repository root, run `python backend/manage.py test estimates` for all
estimate modules, or append a module/class/method such as
`estimates.tests.test_provider.OpenAIProviderTests`. Also run
`python backend/manage.py test backend` to verify full Django discovery. The
explicit directory matters at the repository root: without a label, discovery
starts in the current directory and can report zero tests. CI instead runs
`python manage.py test` with `backend` as its working directory. Compare test
inventories and assertions before/after moving tests, including class decorators,
setup/teardown, helpers and subtests; a green reduced suite is insufficient.

## 🛠️ Maintenance

Keep registration and reset validation against the prospective/existing user,
preserve password whitespace, and retain generic account-recovery responses.
Notification operations remain recipient-scoped; bulk mutations are atomic.
Preserve pending/error handling through response parsing in the frontend.

Maintain the Python version in `environment.yml` and pip dependencies in
`requirements.txt` together with CI and Docker. The test runner's fast password
hasher applies only during tests; normal settings retain secure hashing.
See [Docker dependency maintenance](../deploy/README.md#development-dependency-reproducibility).

The browser-test backend uses disposable SQLite, synthetic users, local file mail,
and loopback binding. It does not load developer dotenv files or use the developer
database. Install backend requirements before running the frontend browser suite.

## 📚 Domain contracts

- [Catalog identity and duplicate cleanup](../docs/CANONICAL-FOODS.md).
- [Meal interpretation and portion semantics](../docs/MEAL-INTERPRETATION.md).
- [Nutrition evidence and publication rules](../docs/NUTRITION-INTEGRITY.md).

## 🚀 Production

Use the [production release and recovery guide](../deploy/production/README.md)
for private configuration, exact proxy trust, migrations, static files and readiness.
Production sessions/CSRF cookies require HTTPS with debug disabled; backend ports
remain private. Local Docker files are development tools, not production release inputs.
