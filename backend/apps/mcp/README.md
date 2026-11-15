# 🔌 MacroMapper MCP

This guide owns MCP setup, application tools, permissions and ChatGPT connection
metadata. The public registry factory is `apps.mcp.tools.server.create_server`.
The installed `mcp` SDK remains a separate third-party package.

## 🧭 Structure

| Folder | Responsibility |
| --- | --- |
| `framework/` | Canonical OAuth, transport and ASGI lifecycle; shared runtime files match across consumers. |
| `tools/` | This application's registry, domain operations, permissions and validation. |
| `chatgpt/` | Connection manifests, branding and artwork; no local package/listing builders. |

- [Shared framework](#framework)
- [Application tools](#application-tools)
- [ChatGPT connection and branding](#chatgpt)

<a id="framework"></a>

## 🔌 Shared framework

`backend/apps/mcp/framework` provides shared OAuth consent, discovery, token verification,
Streamable HTTP transport and ASGI lifecycle. Application registries own their
models, permissions and tools. FullStackTemplate is the canonical source.
Shared framework changes are reviewed there first, then synchronized to each
consumer. Keep the shared runtime implementation aligned while preserving each
application's own tools, branding and permissions. Record reviewed source commits
and adoption evidence in the coordinated change's tracking issue.

Infrastructure routes requests through nginx to each application's own MCP
endpoint and OAuth provider. The framework is shared source, deployed inside each
application; it does not introduce a shared authorization service or another
account registry. `create_server(instructions=...)` uses that application's
`MCP_BASE_URL` as its issuer and `MCP_RESOURCE_URL` as its protected resource.
Accounts, client registrations, grants and tool permissions remain application
owned. Ordinary website login/REST JWTs retain their existing local behavior.
The previous external-issuer extension and centralized rollout are withdrawn;
template scaffolding remains disabled until an app implements its own tools.

Client setup and branding live in [chatgpt/](#chatgpt).

### 🧭 Framework files

- `server.py`, `asgi.py`, `routing.py`: server factory, transport, and ASGI lifecycle.
- `oauth.py`, `views.py`, `urls.py`: OAuth consent and connection management.
- `errors.py`: reconnectable connection failures and sanitized MCP auth challenges.
- `apps.py`: the canonical origin, HTTPS and registry configuration checks.
- `config.py`, `proxy.py`: application settings and exact proxy trust.
- `tests/`: profile, OAuth consent, and transport regressions grouped by behavior.


Connection failures discovered during a tool invocation return a sanitized MCP
error with `_meta["mcp/www_authenticate"]`, the local protected-resource metadata
URL, `invalid_token` or `insufficient_scope`, and the operation's required scopes.
Expired/revoked connections can reconnect; object ownership or membership denials
do not request a new grant. HTTP authentication still rejects invalid credentials
before tool dispatch. Exception bodies, tokens and record identifiers never enter
these challenges. App-owned `permissions.py` defines scopes and live principal
checks; `framework/oauth.py` retains the OAuth lifecycle.

### ⚙️ Enabling a derived application

MCP is off by default in FullStackTemplate. Derived applications own their
enablement and tool registries; see the [backend guide](../../README.md#-mcp-integration)
for this application's profile. Disabled applications keep
their existing Gunicorn/REST behavior, install no OAuth Django app, and expose no
backend MCP/discovery/OAuth routes. Dependencies are installed so enabling the
profile does not require changing the image's Python packages.

For an isolated development database:

```sh
export DJANGO_MCP_ENABLED=1
export DJANGO_MCP_BASE_URL=http://localhost:8000
uv run --locked --project backend python backend/manage.py migrate
uv run --locked --project backend python backend/manage.py createapplication public authorization-code \
  --client-id macromapper-chatgpt --name 'MacroMapper for ChatGPT' \
  --redirect-uris 'https://client.example/callback'
cd backend
uv run --locked uvicorn config.asgi:application --port 8000 --no-proxy-headers
```

Use the exact HTTPS callback supplied by the client, without credentials,
fragments or wildcards. Multiple reviewed callbacks are space-separated inside
`--redirect-uris`. Registration uses Django OAuth Toolkit's built-in
[`createapplication`](https://django-oauth-toolkit.readthedocs.io/en/latest/management_commands.html);
there is no repository-owned registration script. Enable the MCP profile and
apply migrations first: disabled profiles do not install the OAuth app or expose
its command. Use the explicit application-specific client ID and name above.

The public authorization-code client uses S256 PKCE and authentication method
`none`; do not pass `--skip-authorization`. The toolkit may print a generated
`client_secret`, but public clients do not use it: leave the client secret blank
in ChatGPT. Dynamic registration remains disabled. Duplicate client IDs and
callbacks rejected by model validation produce messages without changing existing rows;
the toolkit can still exit successfully, so verify its success message and the
application in Django admin rather than relying on exit status alone. Review
existing registration edits explicitly in Django admin. HTTPS schemes and
`ALLOW_URI_WILDCARDS=False` retain callback restrictions. Toolkit's generic
registration may store a URI containing credentials or a literal asterisk;
the shared OAuth validator refuses to use these callbacks for authorization
(including default callbacks) or code exchange. Onboarding must still use the
exact HTTPS callback supplied, without credentials, fragments or asterisks.
Configure
`DJANGO_FRONTEND_BASE_URL` for the actual React origin; build/start React with
`VITE_MCP_ENABLED=1` (Docker: `--build-arg VITE_MCP_ENABLED=1`). Enable backend and
frontend together. The template production build leaves this flag off; enabled applications
configure their own reviewed build and runtime profiles. No template instance is provisioned by merging this framework.

The template defaults to `apps.mcp.tools.server.create_server`: its sole tool,
`connection_status`, returns `{"connected": true}` after authentication and
reads no application data. Derived applications select their own registry with
`DJANGO_MCP_SERVER_FACTORY`; the sample is a transport test, not a domain tool
implementation. Notoli and MacroMapper supply their own application tools.

For real adoption, configure an application-owned factory returning
`create_server(instructions=...)`, explicitly declare OAuth scopes and required
scopes, and register tools with typed inputs/outputs, bounded results, accurate
read/write/destructive/idempotent annotations and OAuth scope metadata. Resolve
the current OAuth token's user and check scope, ownership and current membership
for every operation. Never trust a user ID supplied by a caller. Transport
authentication alone does not establish object permissions. Validate consequential
writes and application-specific mutation controls in the application service; keep REST behavior aligned.

### 🔐 Browser consent and credentials

Browser GET `/auth/mcp/authorize/` redirects to React `/connections/authorize`
with the original OAuth query. Login preserves only validated local connection
destinations. Consent shows the client, signed-in identity and every requested
permission; Allow/Cancel submits a signed, account-bound request valid for ten
minutes. JWTs stay in sessionStorage/header, never URLs. `/connections` lists
current-account access/refresh grants, including pending authorization codes,
and revokes them transactionally. Cookie authentication and posted user IDs cannot
grant access. Revocation is rechecked against the database on every MCP request.

OAuth tokens are distinct from REST JWTs. The provider requires the exact `/mcp`
resource, S256 PKCE and state; authorization codes expire in 120 seconds, access
tokens in one hour, and refresh tokens in 30 days. Refresh rotates with reuse
protection and cannot escalate scope. Stored access tokens are hashed. Keep
tokens, codes, tickets, private configuration and credentials out of logs/results.
An operator may schedule toolkit token cleanup separately; this change schedules
no production maintenance. No OIDC login or automatic account linking is added.

### 🌐 Hosting, readiness and rollback

Production requires an HTTPS origin in `DJANGO_MCP_BASE_URL`, correct frontend,
host/CORS/CSRF origins, a strong independent Django secret and
`uv run --locked --project backend python backend/manage.py check --deploy`. MCP uses ASGI, one worker for SQLite,
stateless JSON Streamable HTTP, a 64 KiB request limit and lifespan-managed SDK
sessions. Preserve the exact `/mcp` path; `/mcp/` is a different URL. The transport
validates Host/Origin and rejects REST JWTs as MCP credentials.

Only the dedicated trusted gateway may forward scheme/client metadata. Set
`DJANGO_TRUSTED_PROXY_IPS` to individually reviewed peer IPs on a private backend
network, never a wildcard or subnet. Do not publish the backend. The ASGI wrapper
strips untrusted forwarded headers and Django ignores forwarded host/proto headers.
The generic framework supplies no production subnet or ingress attachment.
Each application retains its reviewed exact proxy addresses and network policy;
consult its deployment guide rather than inferring addresses from the framework.

Infrastructure owns gateway routing and the optional
`nginx/snippets/mcp-locations.conf` contract. Coordinate exact `/mcp`, discovery,
`/auth/mcp/` forwarding, no caching or interactive edge challenges, HTTP/1.1,
buffering off and the 120-second upstream idle timeout. JSON mode does not require
WebSockets. Test REST/frontend routes and cross-app isolation as well as MCP.
An ordinary app must not advertise OAuth metadata or an MCP challenge; a SPA
fallback may return HTML at unknown paths and is not MCP discovery.

Enabled release readiness must assert the issuer and exact resource JSON,
unauthenticated `/mcp` status 401 and resource-metadata challenge, alongside
ordinary HTML/API health. Use existing app-specific `app.json` readiness fields;
no shared release engine change is required. Disabled apps retain ordinary
readiness. Do not add a live vhost, network or production client before reviewed
onboarding and operator authorization. Review Cloudflare route/cache/challenge
policy when activating a new app; this extraction changes no domain or edge rule.

Use the existing app-only immutable release/recovery guide and maintenance lock.
Retain previous images and private recovery evidence. Roll back the affected
component explicitly; never recreate shared networks, restore a historical
database casually, prune images globally or replay the initial cutover. Disabling
a newly adopted profile hides routes/UI; retain OAuth tables/data for deliberate
operator cleanup rather than reversing migrations or silently revoking grants.
Moving framework documentation changes no application issuer, scopes, consent
salt, client IDs, database tables, credentials, domain tools or readiness policy.

<a id="-verification"></a>

### 🧪 Framework checks

Run the ordinary backend suite from `backend/`, then run a separate enabled
profile against an isolated test database:

```sh
uv run --locked python manage.py test
DJANGO_MCP_ENABLED=1 DJANGO_MCP_SERVER_FACTORY=apps.mcp.tools.server.create_server uv run --locked python manage.py test apps.mcp.framework
```

The framework tests cover discovery/initialization/sample calls, absent/invalid
credentials, REST-JWT rejection, token expiry/resource/scope/revocation, S256 code
exchange and refresh rotation, account-bound consent, foreign-account revocation,
pending grants, exact client registration and sanitized reconnect challenges.
Keep all framework runtime files and test-package files identical across the three
applications (line-ending normalization is allowed). Frontend tests cover displayed
permissions, login return paths, Allow/Cancel, expired consent and revocation.
Run frontend tests/lint/build in both default and enabled builds. Notoli also runs
its application tool/permission/transport/proxy regressions. Live ChatGPT writes
and new production test accounts/grants remain separate acceptance work; framework
rollout verification must not alter the owner's connection or business records.

<a id="application-tools"></a>

## 🧰 Application tools

MacroMapper owns its MCP tools and OAuth in [#284](https://github.com/VanillaIceCube/MacroMapper/issues/284).
The existing [canonical framework](#framework) supplies transport, discovery,
PKCE, consent and revocation unchanged. Infrastructure routes the application's
own endpoints; no shared issuer, new service, network or YNAB dependency is needed.
Website login, REST JWTs and existing AI estimation remain independent.

The REST API and these tools call the same actor-scoped catalog, diary, proposal
and notification operations directly. The MCP boundary validates serializer
inputs with an actor context, keeps OAuth, automatic duplicate protection and live state checks, and formats
bounded results; it does not construct REST requests or invoke viewsets.

### 🧭 Tool files

- `server.py`: a fresh registry, typed tool signatures, execution workers and sanitized transport errors.
- `permissions.py`: local scopes, live OAuth principal checks and actor locking.
- `operations.py`: closed mutation catalog, strict validation, writable-field discovery and domain dispatch.
- `queries.py`: actor-scoped reads, catalog snapshots and adaptive detail pages.
- `services.py`: authenticated read/mutation boundary, automatic request reservation, duplicate recovery and atomic outcome persistence.
- `results.py`: bounded JSON formatting and truthful success receipts.
- `schemas.py`, `models.py`, `migrations/`: typed wire contracts and MacroMapper-only execution receipts and actor locks.
- `tests/`: domain access, discovery/errors, direct execution/replay, paid operations, result limits and HTTP contracts.

The domain APIs live consistently in `foods/services.py`, `meals/services.py`,
`estimates/services.py` and `notifications/services.py`; proposal recipe-tree
helpers live in `estimates/recipe_edits.py`. MCP `operations.py` owns tool validation
and metadata, while those domain services own business changes for both transports.
The services boundary performs real invocation work; no compatibility dispatch modules or re-export facade are retained.

### 🔐 Access and permissions

The resource is `https://macromapper.judeandrewalaba.com/mcp`; the issuer is the
same origin. The app registry is `apps.mcp.tools.server.create_server`.
OAuth uses existing MacroMapper accounts and separate MCP tokens. Every operation
rechecks the active token, scopes and current user's ownership; caller-supplied
user IDs cannot select another account. REST JWTs cannot call MCP.

- `macromapper:read` is required and the only default grant. It reads accessible
  foods and the account's meals, totals, proposals and notifications.
- `macromapper:write` permits user-requested business mutations, with the
  same validation and ownership rules as the application.
- `macromapper:estimate` separately permits paid AI estimates. It also requires
  read/write access and a user-requested paid action; read access alone cannot spend
  provider credits. Tests mock providers and do not make paid requests.

A requested mutation runs directly with the required OAuth permissions. There is
no application preview/confirmation round-trip, including for paid actions.
The client may still display its own permission UI; this backend does not control
those prompts. Catalog access follows existing visibility and ownership rules;
MCP is not administrative access. Planned goals/activity and account credential
management are outside the registry.

### 🧰 Available capabilities

The registry exposes 12 tools covering 19 closed mutation actions. Call
`operation_schema(action)` before preparing a change: it returns the allowed
fields, required values, bounds and scopes for that action.
Meal-item descriptors separate string product identity metadata from the bounded
`natural_servings` array (at most 12 food-specific gram definitions) and
`portion_options` array (at most 20 selectable conversions), matching the
application's writable serializers.

| Area | Read tools | Direct actions |
| --- | --- | --- |
| Food catalog | `search_foods`, `get_food` | Create or update your personal foods; archive them. Shared catalog visibility follows the existing app policy. |
| Diary and nutrition | `meal_diary`, `get_meal`, `nutrition_totals` | Create, edit or delete meals; save or update reviewed drafts. Drafts require explicit name and notes, with an empty notes string allowed. |
| Proposals | `list_proposals` returns summaries/IDs; `get_proposal` pages current review items | Review/edit, delete draft proposals, or separately accept a proposal into the diary. |
| Paid estimation | Read proposals before accepting them | Estimate a new proposal, request a proposal follow-up, or adjust a proposal/meal draft. These four actions additionally require `macromapper:estimate`; they do not directly accept a diary meal. |
| Notifications | `list_notifications`, `get_notification` | Mark one read/unread, delete one, mark all current notifications read, or clear the current set. Arrivals after the invocation selects its bounded set are excluded. |

`execute_change(request_id, action, changes, target_id?)` handles the 15 nonpaid
actions with read/write access. `execute_paid_change` handles the four paid actions
with read/write/estimate access. Their action enums are disjoint. Both advertise
mutating/destructive behavior; the paid tool also advertises external interaction.
Exact repeats are idempotent because the automatic request receipt prevents
executing the same request twice.

The tool caller generates a UUID automatically for each intended operation. It
must not ask the user for an ID or an extra approval. Preserve that UUID and the
exact arguments if a response is interrupted: the same call retrieves the stored
outcome instead of repeating the action. JSON-RPC IDs are not idempotency keys;
they can reset between sessions. A reused UUID with changed arguments is rejected.
Receipts belong to the original account and OAuth client. Every replay rechecks
current token validity/resource/scopes; refreshed credentials for that same
account/client can recover an outcome. A completed deletion remains recoverable
after its target is gone.

The response carries `request_id`, `action`, `status`, `applied`, `replayed` and
the bounded `result`. `status: completed` means execution finished; paid no-op
outcomes explicitly have `applied: false`. `in_progress` or `uncertain` has
`applied: null` and must not be interpreted as successful application. Inspect
existing records and reuse the same UUID to recover status. Never automatically
submit paid work under a new UUID to bypass an uncertain outcome.

Paid requests persist their reservation before calling a provider. No database
writer lock spans that wait. Fresh token, owner and catalog/target checks run
before publication; business changes and the successful receipt commit together.
A provider/guard/receipt failure leaves a durable uncertain reservation, and any
publication transaction rolls back. A process interrupted without a recorded
outcome may leave an in-progress reservation; it is never restarted automatically.
Receipts are retained without automatic expiry so old UUIDs cannot silently run
again. They store bounded outcomes/digests, not raw tokens or request payloads;
account deletion removes its receipts. Nonpaid business failures roll back both
the change and reservation.

Meal drafts validate the same catalog authorization and component rules as
saving. Every draft item must reference a visible catalog food/version pair. For
a manual food, first execute `food.create`, then use its returned food/version
IDs in `meal.draft_create` or `meal.draft_update`. This preserves personal-food
ownership and provenance; a source URL or `user_entered` label alone does not
create a catalog food. Draft creation saves the diary directly without an AI call.
Invalid drafts fail before a request receipt or business change is stored.

Pages contain at most 20 records. Nutrition totals cover at most 31 days, 500 meals
and 2,000 meal items; bulk notification operations cover at most 200 existing entries.
Large or deeply nested data is rejected or explicitly marked truncated. Narrow the
request rather than treating truncated output or missing nutrients as complete.

Successful nonpaid mutations return the ordinary result when it fits. An expanded
result exceeding the existing 2,000-node/64-KiB budget, or requiring trimming,
returns an explicitly truncated success receipt with the saved record ID and
readback guidance. The mutation and automatic execution receipt commit together; business
failures still roll back both. Reusing the same request UUID recovers the cached
receipt; use the read tools or website for expanded details.

`meal_diary` can reduce the requested page size to fit the output budget; follow
the returned `next_offset`, rather than adding the requested limit. An oversized
individual meal becomes a marked summary with an accurate item count and no
partial item array. `get_meal(meal_id, item_limit=20, item_offset=0)` preserves
ordinary small-meal reads and pages complete saved items adaptively; follow
`next_offset` as `item_offset` until `has_more` is false before editing. If even
one item or the meal metadata cannot fit without trimming, the response contains
only an explicit summary directing complete review to the saved meal in
MacroMapper. An oversized-item summary preserves `next_offset` for later items;
review the omitted item in MacroMapper before editing the whole meal. Summary
data is never a complete editable meal. At the existing offset ceiling, a
terminal summary explicitly sets `pagination_limit_reached`; use MacroMapper for
the remaining records. No read calls AI or writes to the diary.

Proposal lists do not duplicate current items or historical revision snapshots.
`get_proposal(proposal_id, item_limit=20, item_offset=0)` returns current items and
provider provenance; follow `next_offset` as `item_offset` until `has_more` is false
before editing or accepting. The server can reduce a page to keep complete items
within its existing output budget. Historical snapshots remain available in the
website. A single oversized item returns an explicitly truncated summary directing
review to the existing proposal in MacroMapper. Never use that summary as complete
editable data or repeat the paid estimate to recover detail. This read path also
recovers proposals created before the fix for [#339](https://github.com/VanillaIceCube/MacroMapper/issues/339).
Sanitized tool failures include a reference correlated with the operation name and
exception category in server logs; meal text, tokens and provider errors are omitted.

Four bounded application tool workers keep paid provider waits separate from
OAuth verification. Requests beyond that capacity fail before reserving an
execution; cancellation retains a worker slot until the operation finishes.
An oversized paid result returns a successful, explicitly truncated receipt
with retained proposal IDs or a bounded temporary-adjustment summary. Temporary
adjustments do not modify the diary. Never repeat a paid call to recover detail.

### 🖥️ Consent and client setup

The existing `/connections/authorize` page displays each requested permission;
`/connections`, also in the profile menu, lists and revokes the signed-in user's
connections. Consent uses the normal REST login, an account-bound signed ticket
and explicit Allow/Cancel. OAuth credentials do not replace the website session.

Deployment does not itself register clients, add a plugin or grant access.
For separately authorized ChatGPT registration, the current
[OpenAI redirect contract](https://developers.openai.com/plugins/build/auth#redirect-url)
uses `https://chatgpt.com/connector_platform_oauth_redirect` when issuer
identification is supported. This framework advertises
`authorization_response_iss_parameter_supported=true` and includes the matching
issuer in OAuth responses. The operator can register the public client explicitly:

```sh
python manage.py createapplication public authorization-code --client-id macromapper-chatgpt \
  --name 'MacroMapper for ChatGPT' \
  --redirect-uris 'https://chatgpt.com/connector_platform_oauth_redirect'
```

If the client's management page supplies a different exact URI, review it before
changing the allowlist; do not guess older callback paths or add wildcards. The
owner signs in using their ordinary MacroMapper account and reviews consent.
Keep distinct client IDs when appropriate, S256 PKCE, one exact resource parameter
and `token_endpoint_auth_method=none`. Follow the built-in command validation and
Django admin review guidance in the [framework setup](#framework). No dynamic client registration or loopback callback support
is claimed. Live sign-in/tool acceptance remains separate from offline tests;
registering a client does not install a plugin or issue a user grant.

### 📦 Release and recovery

Production app policy enables `DJANGO_MCP_ENABLED=1`, fixes the issuer origin and
trusts only the existing gateway peer `172.20.0.3`. The backend runs one Uvicorn
worker with proxy-header auto-trust disabled; the canonical ASGI wrapper alone
accepts that exact peer. The production frontend Docker build defaults
`VITE_MCP_ENABLED=1`; a disabled local build can explicitly pass `0`.
The ordinary frontend/API probes remain, with exact issuer/resource JSON and an
unauthenticated MCP 401 resource-metadata challenge added to release readiness.

Coordinate the existing Infrastructure vhost before enabling the app. Run normal
private SQLite capture/integrity checks before application migrations.
Migration `0002_direct_execution_receipts` creates the automatic receipt model and
removes obsolete pending Confirmation records; historical `0001_initial` remains
unchanged. Old preview/confirm tool calls are intentionally unsupported. Refresh
client tool discovery to use the 12-tool registry and automatically generated
request UUIDs. Existing OAuth grants remain valid; reconnect only when a broader
scope grant is needed. Retain the prior disabled release directory, its checksummed policy,
controller, images and recovery evidence. First activation cannot require the
old disabled backend to already have the new trust environment; `app.json` instead
pins the gateway address and fixes trust in the new bundle. Verify the resulting
backend environment and ordinary app health at acceptance.

For a failed first enable, invoke the **retained previous disabled release's**
`release.py rollback`, selecting the failed candidate's recovery ID. Its own
readiness policy correctly accepts the restored disabled app. The enabled
candidate's controller would incorrectly require MCP from that old image. Keep
all immutable bundles unchanged. Before migrations, `--keep-database` is eligible
only at the controller's recorded safe stages; after migrations, explicit
`--restore-database` restores the verified pre-migration snapshot and may discard
later writes. Preserve current journals first and obtain the appropriate recovery
authorization. See [the production guide](../../../deploy/production/README.md).

<a id="-local-verification"></a>

### 🧪 Tool checks

Backend development remains off by default. Use an isolated database, then set
`DJANGO_MCP_ENABLED=1`, an exact `DJANGO_MCP_BASE_URL` and the real frontend origin
before `uv run --locked python manage.py migrate` and
`uv run --locked uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 1 --no-proxy-headers`. Set `VITE_MCP_ENABLED=1`
for Vite. Do not reuse a production database or token in tests.

Run `uv run --locked python manage.py test` in `backend`, then separately
`DJANGO_MCP_ENABLED=1 DJANGO_MCP_BASE_URL=http://localhost:8000 uv run --locked python manage.py test apps.mcp.framework apps.mcp.tools`.
Run frontend tests/lint/build, the shared release parity checks and the
production deployment suite on disposable Docker. Tests exercise synthetic OAuth,
real app services and mocked AI; deployment checks do not establish live client
consent or permission to create business data.

<a id="chatgpt"></a>

## 💬 ChatGPT connection and branding

This package connects to the app-owned MCP server at
`https://macromapper.judeandrewalaba.com/mcp`. It uses existing MacroMapper
accounts, a predefined public OAuth client, and explicit consent.

### 🔗 Connect and choose permissions

The client ID is `macromapper-chatgpt`, with token authentication method `none`
and S256 PKCE. This package requests `macromapper:read` only and advertises read
access. It cannot perform writes or paid estimates with that grant.

To intentionally build a broader variant, add `macromapper:write` to
`baseScopes` in `mcp.json` for requested ordinary mutations. Paid estimates also
require `macromapper:estimate`; neither path adds an app-level confirmation. Review and
update the listing capabilities and descriptions to match that variant before
building, then obtain a new consent grant for its requested scopes. Existing
grants cannot silently gain new scopes.

Follow the [app MCP guide](#-consent-and-client-setup)
for client registration, the exact callback, consent, tool coverage, and
verification. Deployment does not register the client or install a plugin.
No existing installed plugin or registered app identity is assumed here.

<a id="-files"></a>

### 🧭 Connection files

- `plugin.json`: MacroMapper listing metadata and presentation.
- `mcp.json`: HTTPS endpoint, public OAuth settings, and least-privilege scopes.
- `assets/`: a square PNG export of the existing frontend MacroMapper mark.

The folder contains source metadata and artwork only. There are no local package
or listing builders. Its `.gitignore` excludes ZIP exports and account-specific
`.app.json` files.
