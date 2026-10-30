# 🔌 Optional MCP framework

> MacroMapper uses this canonical package unchanged for its app-owned OAuth
> and [domain registry](MCP.md). Its reviewed production profile is enabled;
> local development remains opt-in. Infrastructure supplies ordinary Nginx
> routing. There is no shared authorization server or YNAB dependency.

`backend/mcp_framework` provides shared OAuth consent, discovery, token verification,
Streamable HTTP transport and ASGI lifecycle. Application registries own their
models, permissions and tools. FullStackTemplate is the canonical source;
`mcp-framework-source.json` pins its immutable source and
`backend/mcp-framework-manifest.json` hashes every Python source file. Edit the
canonical package, regenerate its manifest with
`python scripts/check_mcp_framework.py --write-manifest`, commit it, then copy
the package/manifest/checker and pin the same commit in every consumer. Never
brand or independently patch the shared package. CI checks the remote pin;
`--source-root ../FullStackTemplate` is a local development override only.

## ⚙️ Enabling a derived application

MCP is off by default in the template and MacroMapper local settings. MacroMapper's
production app policy enables it explicitly. Disabled applications keep
their existing Gunicorn/REST behavior, install no OAuth Django app, and expose no
backend MCP/discovery/OAuth routes. Dependencies are installed so enabling the
profile does not require changing the image's Python packages.

For an isolated development database:

```sh
export DJANGO_MCP_ENABLED=1
export DJANGO_MCP_BASE_URL=http://localhost:8000
python backend/manage.py migrate
python backend/manage.py register_mcp_client --redirect-uri 'https://client.example/callback'
cd backend
python -m uvicorn app.asgi:application --port 8000 --no-proxy-headers
```

Use the exact HTTPS callback supplied by the client. Registration is predefined,
public, authorization-code/S256 PKCE only, with no client secret or dynamic client
registration. The command refuses to overwrite an existing registration. Configure
`DJANGO_FRONTEND_BASE_URL` for the actual React origin; build/start React with
`VITE_MCP_ENABLED=1` (Docker: `--build-arg VITE_MCP_ENABLED=1`). Enable backend and
frontend together. MacroMapper's app-owned production Dockerfile defaults this
flag to `1`, without changing the common release workflow. A disabled image must
explicitly pass `--build-arg VITE_MCP_ENABLED=0`. No template instance is provisioned
by adopting this framework.

The template defaults to `mcp_framework.server.sample_server`: its sole tool,
`connection_status`, returns `{"connected": true}` after authentication and
reads no application data. MacroMapper defaults to its own
`macromapper_mcp.server.create_server` factory with read/write/estimate scopes.
The sample remains only a shared transport fixture; MacroMapper's separate
[domain suite and guide](MCP.md) cover business operations and confirmation.

For real adoption, configure an application-owned factory returning
`create_server(instructions=...)`, explicitly declare OAuth scopes and required
scopes, and register tools with typed inputs/outputs, bounded results, accurate
read/write/destructive/idempotent annotations and OAuth scope metadata. Resolve
the current OAuth token's user and check scope, ownership and current membership
for every operation. Never trust a user ID supplied by a caller. Transport
authentication alone does not establish object permissions. Validate consequential
writes and confirmation in the application service; keep REST behavior aligned.

## 🔐 Browser consent and credentials

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

## 🌐 Hosting, readiness and rollback

Production requires an HTTPS origin in `DJANGO_MCP_BASE_URL`, correct frontend,
host/CORS/CSRF origins, a strong independent Django secret and
`python backend/manage.py check --deploy`. MCP uses ASGI, one worker for SQLite,
stateless JSON Streamable HTTP, a 64 KiB request limit and lifespan-managed SDK
sessions. Preserve the exact `/mcp` path; `/mcp/` is a different URL. The transport
validates Host/Origin and rejects REST JWTs as MCP credentials.

Only the dedicated trusted gateway may forward scheme/client metadata. Set
`DJANGO_TRUSTED_PROXY_IPS` to individually reviewed peer IPs on a private backend
network, never a wildcard or subnet. Do not publish the backend. The ASGI wrapper
strips untrusted forwarded headers and Django ignores forwarded host/proto headers.
The generic framework supplies no production subnet or ingress attachment.
Notoli retains its existing exact gateway `.2` and backend `.3` addresses.

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
Notoli's extraction preserves its issuer, scopes, consent salt, client IDs,
database tables, existing credentials, 31 domain tools and readiness policy.

## 🧪 Verification

Run the ordinary backend suite from `backend/`, then run a separate enabled
profile against an isolated test database:

```sh
python manage.py test
DJANGO_MCP_ENABLED=1 DJANGO_MCP_BASE_URL=http://localhost:8000 python manage.py test mcp_framework macromapper_mcp
```

The framework tests cover discovery/initialization/sample calls, absent/invalid
credentials, REST-JWT rejection, token expiry/resource/scope/revocation, S256 code
exchange and refresh rotation, account-bound consent, foreign-account revocation,
pending grants and exact client registration. Frontend tests cover displayed
permissions, login return paths, Allow/Cancel, expired consent and revocation.
Run frontend tests/lint/build in both default and enabled builds. MacroMapper and
Notoli also run their application tool/permission/transport regressions. Live client writes
and new production test accounts/grants remain separate acceptance work; framework
rollout verification must not alter the owner's connection or business records.
