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

See [canonical identities and safe duplicate cleanup](README.md#-canonical-food-identity)
and [meal interpretation semantics](README.md#-meal-interpretation-and-portions). Shared food
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

The shared-framework checker lives at `backend/check_app_mcp.py`, beside the backend
and outside the hash-verified package. Run `python backend/check_app_mcp.py` from
the repository root; use `--source-root <canonical-checkout>` for local offline
verification. See the [framework guide](app_mcp/README.md) for source ownership.

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

## 📚 Domain contracts

- [Catalog identity and duplicate cleanup](README.md#-canonical-food-identity).
- [Meal interpretation and portion semantics](README.md#-meal-interpretation-and-portions).
- [Nutrition evidence and publication rules](README.md#-nutrition-evidence).

## 🚀 Production

Use the [production release and recovery guide](../deploy/production/README.md)
for private configuration, exact proxy trust, migrations, static files and readiness.
Production sessions/CSRF cookies require HTTPS with debug disabled; backend ports
remain private. Local Docker files are development tools, not production release inputs.

## 🥗 Canonical food identity

Shared food identity is separate from an estimate's serving, nutrients,
confidence and meal quantity. `canonical_identity` hashes normalized food/provider
names, market and product identifiers. Known food plurals and punctuation are
normalized; provider foods do not split merely because their classification is
`branded` rather than `restaurant`. Generic leading portion-size wording is
removed, while branded size/SKU names remain distinct.

An explicit product identifier is scoped to its provider and market. Otherwise
an explicitly supplied identity URL, or a source whose hostname starts with the
normalized provider name,
also constrains identity. URL fragments and tracking parameters are ignored;
country paths and meaningful query parameters are preserved. This hostname
heuristic is an identity hint, not proof of domain ownership or official
nutrition provenance. Unmatched third-party source URLs do not define identity.
Unknown versus known identity URLs/markets are
conservatively distinct: adding evidence must not silently merge potentially
different regional products. Unrecognized synonyms and cross-domain provider
aliases need explicit review rather than fuzzy automatic merging.

Within a canonical food, `content_fingerprint` covers the serving definition,
food-specific natural servings, all supported nutrients, pinned component
content/identity/quantities, and research/verification coverage.
Component identity uses the registered canonical key when available; legacy
components derive their identity from the exact pinned version's source URLs,
so a later current version or a same-named regional product cannot replace it.
Source-level official flags and verification evidence are part of content
integrity: a newly verified publication cannot be swallowed by an older unsourced version with the
same nutrients. Meal servings and consumed recipe fractions are instance
quantities and do not create versions. Evidence-equivalent definitions reuse a
version, retain additional source URLs, and append distinct estimation metadata
to `FoodVersionEvidence`. Confidence-only differences and retrieval response IDs
do not split equivalent versions; their complete incoming evidence/source
metadata is retained in that append-only record.
Ordinary citations with `is_official=false` and empty evidence also merge into
the same version rather than changing its content identity; adding a first-party
claim or trust/research evidence remains an immutable version distinction.
Existing version nutrients, provenance, confidence, source evidence and response
metadata remain unchanged.
A materially changed definition or verification coverage creates a new version.
Personal definitions remain owner-specific and are never merged by the
consolidation command.

Current version selection is deterministic: categorical verified parent coverage
wins first (fully verified and source-backed with inferred components, then
partially verified, AI estimate, then legacy/unknown), followed by the count of
verified nutrient fields. Provenance then ranks official, community estimate, AI
estimate, user entered, then user modified; source count, confidence, earliest
version number and primary key break later ties. A legacy official label cannot
displace a newly verified definition. Recency alone cannot displace better
evidence. Exact source/product/region/serving verification follows the nutrition evidence contract below; this selection policy
does not independently validate an AI assertion that a source is official.


## 🧮 Meal interpretation and portions

One draft tree is the calculation basis for AI estimates, manual review and saved
meals. Each node has a unique stable key, immutable catalog identity/version
references, a base serving definition and an instance `servings` multiplier.
Composite nutrients ordinarily sum children multiplied by each child's local
servings. Direct fields with matching official source verification retain their
verified parent values; inferred component totals do not replace those fields.
Consumed nutrients multiply that result by the parent's servings once.

## Recipes and corrections

Recipe descriptions are interpreted as a whole, including when some ingredients
already exist in the catalog. Full recipe ingredient quantities remain children
of the prepared food. The provider's optional `recipe_fraction` becomes the
top-level recipe's servings; it requires a composite with one full recipe as its
basis. For 75% of chilaquiles plus two chicken breasts and yogurt, the recipe is
0.75, chicken is 2 and yogurt keeps its separately described quantity. The
provider must not pre-scale recipe children. Nutrition normalization and rollup
remain deterministic after interpretation.

Follow-ups support targeted operations on exact existing keys:

- `reparentings`: move a node to an existing composite (`parent_key`) or meal
  level (`null`). Local ingredient quantities, IDs and nutrition are retained.
- `fraction_updates`: set an absolute recipe fraction, not a multiplier of its
  previous fraction. `excluded_keys` protects separate foods from quantity and
  size operations in that response. Excluded children must first be moved out.
- `serving_updates`: change an existing node's absolute quantity.
- `portion_updates`: select an existing portion option. Natural size changes
  preserve count; measurement conversions preserve consumed weight/nutrition.
- `remove_keys`: remove an existing subtree. New foods still require the
  existing catalog/publication validation path.

Moves do not recreate ingredients. Ingredient-tree changes invalidate parent
verification before recalculation; consumed-fraction-only changes preserve
per-serving evidence and official values. Cycles, unknown keys, duplicate node keys,
leaf destinations, excessive depth/cardinality and conflicting fraction/child
quantity edits fail atomically with actionable validation. Removing the final
child clears the former composite's nutrition rather than retaining stale
totals. A local recipe quantity stays local when moved beneath a partially
consumed recipe; its consumed contribution then follows that recipe's fraction.

The AI remains responsible for resolving natural-language references and
choosing the correct keys. The existing best-effort conversational policy is
retained; ambiguous natural language is not a guarantee of a clarification
dialog. Unsupported operations fail visibly. No paid meal-model call is required
for the synthetic regression suite.

## Canonical names and food-specific portions

Generic leading size wording is removed from food identity; variety/color stays
in the name. Branded product names and marketed size/SKU distinctions are kept.
`natural_servings` is an optional list of `{key, label, weight_grams}` definitions
for that particular food version. Choices appear as `size:<key>` portion options
with multipliers derived from each gram weight divided by the base serving's
gram weight. No universal Small/Medium/Large gram weights are assumed. A requested size is
reused from the catalog only when a food-specific choice or the declared base
serving represents that size. Otherwise the request remains unmatched for
estimation; an unsupported Large request cannot silently reuse a Small base.
Serialized size choices survive follow-up catalog lookup without requiring size
words in the canonical food name or base label.

For two Small apples, selecting Large keeps the count at two and changes the
base-serving multiplier. Selecting grams converts the displayed quantity while
preserving consumed nutrition. When food-specific sizes are unavailable, the
existing natural base serving and grams/ounces options remain the fallback.
Natural portion definitions are estimated unless their source/provenance says
otherwise; this change does not introduce a verified food-weight database.

Serving changes affect draft instances, never shared catalog versions. New component
snapshots retain selected portion keys; old snapshots keep their original display
and historical quantities/nutrients.

## 🔎 Nutrition evidence

## Publication and research

`foods.evidence.usable_nutrition` accepts any finite nonnegative known nutrient,
including zero. Nulls mean unknown. Empty leaves fail publication with a visible
unresolved error before any shared food is written. Usable partial records and
containers with populated components remain valid. The shared creation service
also guards non-provider publication. Failed provider validation does not replace
the user's existing draft or diary.

The existing Responses web tool is required for initial estimation. Each branded
parent without matching retrieved evidence gets a separate focused research pass
under the **same existing deadline and worker limit**. There is no new service,
credential, or unbounded retry. These research passes add potential provider/tool
cost to an already-authorized estimate; tests never make live paid requests.
Follow-up additions use the same evidence processing. Quantity-only follow-ups
do not force online research.

Search telemetry supplies the actually consulted URLs. A structured source alone
cannot claim retrieval. Evidence retains document title, publisher, URL, first-party
status, publication date when available, retrieval response ID, product, brand,
region, serving quantity/unit/label/weight, and explicitly published nutrients.
The backend never directly fetches model-supplied URLs. Existing public URL,
text/privacy, decimal, depth and size publication gates remain in force.

Verification requires retrieved evidence matching the exact product, brand,
region and serving, plus equality for each displayed nutrient. Unknown or mismatched
context remains an estimate. Search/extraction is still provider-mediated; these
checks are not an independent human audit of a nutrition document. Provider-mediated checks do not establish independent human verification.

`research_status` distinguishes `found`, `no_source_found`, `failed`,
`not_attempted`, and legacy `not_recorded`. An unrelated frozen pizza, different
market, whole pizza or another serving cannot verify a food-court slice. A source
is attached only to its own food; parents do not supply evidence for components.
Existing catalog hits remain reusable without new paid calls. Legacy unsourced
records require separately reviewed re-research/replacement; reuse does not
retroactively manufacture verification.

## Compatible evidence contract

Existing `provenance` and `source_kind` enums remain unchanged. Additive `evidence`
on versions, proposal items and diary responses has these canonical statuses:

| Status | Meaning |
| --- | --- |
| `official_verified` | All populated parent fields directly supported |
| `source_backed_ai_components` | Verified parent values with inferred components |
| `partially_source_backed` | Only some displayed parent fields directly supported |
| `ai_estimate` | No verified parent fields |
| `user_modified_estimate` | Reviewed definition changed; original sources retained as lineage |
| `legacy_unverified` | Historical coverage was not recorded |

`evidence.nutrients[field]` supplies verification status and supporting source URLs.
Partial calorie evidence does not verify sugar, fiber or any other inferred field.
Parent and component evidence remain separate. Direct verified parent fields take
precedence over component sums; ordinary composites continue using component totals.
Changing components removes the parent's verification and recalculates the result.
Changing only the parent's consumed count preserves its per-serving evidence.

Confidence metadata explicitly separates `model`, `evidence`, and `combined`.
No independent numeric source confidence is available, so `evidence` is null,
never a fabricated score. `combined` is the minimum available model dependency
score, or null if a dependency is unscored. Categorical verification is independent
of every confidence score. The UI explains this and exposes source coverage and
the mixed parent/component state.

SourceReference stores its own nullable `is_official` and evidence JSON. Legacy
null official flags serialize conservatively as false/unknown; they are never
inferred from the parent's label. The additive migration does not rewrite old
versions, proposals, revisions, snapshots or source claims. Legacy component
snapshots may omit evidence and remain readable. Source URLs can remain as lineage
on adjusted foods, while no adjusted value is presented as verified. Review input
cannot override server-owned evidence, even when returned metadata is round-tripped.

Canonical food identity is separate from version content fingerprints . Trust-bearing evidence and source classifications participate in version
content identity, so old unsourced content cannot swallow a verified publication.
Retrieval IDs and confidence remain additional estimate evidence rather than
splitting otherwise equivalent content. Identity still preserves explicit market,
product identifiers and product URLs. Canonical `market` and evidence `region`
share the supplied regional context; contradictory nonblank values are rejected
before publication. Both remain blank when no regional context is supplied.
Nutrition or serving changes create versions under the same canonical food. See canonical food identity above.
Additive schema changes do not repair historical production data.
