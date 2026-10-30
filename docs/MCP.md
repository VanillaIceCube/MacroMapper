# MacroMapper MCP

Issue [#284](https://github.com/VanillaIceCube/MacroMapper/issues/284) adds an
application-owned resource server. Source defaults remain **off**. The prepared
`deploy/production/app.json` policy enables production MCP with required credentials,
exact proxy trust and readiness; only the coordinating owner may promote/release
that policy to `env-prod` after preceding acceptance. Source readiness is not real
ChatGPT/Codex acceptance.
Infrastructure [#71](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/issues/71)
owns the issuer, accounts, PKCE/consent, client registration, refresh/revocation
and signing keys. Activate after shared OAuth and YNAB [#62](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/issues/62)
acceptance, under the coordinating owner's reviewed app-only release plan.

## Resource and authorization

| Setting | Fixed contract |
| --- | --- |
| Issuer | `https://auth.judeandrewalaba.com` |
| Resource | `https://macromapper.judeandrewalaba.com/mcp` (no trailing slash) |
| Clients | `macromapper-chatgpt`, `macromapper-codex` |
| Read scope | `macromapper:read` |
| Write scopes | `macromapper:read macromapper:write` |
| Introspection | `https://auth.judeandrewalaba.com/o/introspect/` |
| Introspector | Dedicated Basic-only `macromapper-introspection` |

The verifier accepts literal JSON `active: true`, the exact `iss`, a canonical
UUID `sub`, exact scalar or singleton-array `aud`, a listed `client_id`, and only
the listed scopes with read included. Integer timestamps must satisfy
`0 <= iat <= now < exp <= iat + 900`. Missing/malformed claims, unknown links,
disabled local users, wrong clients/resources and revoked tokens fail closed.
REST JWTs and other apps' tokens do not authorize MCP. MCP tokens do not
authorize REST. Normal website login, email/password reset and AI estimates retain
their existing routes, authentication and credentials.

Introspection is a fixed HTTPS POST with verified TLS, Basic credentials, no
redirects, no proxy/CA environment inheritance, no token cache, no compression,
a three-second total deadline and a 16 KiB JSON response bound. Failures expose
static messages. Never log request/response bodies, Authorization headers, raw
tokens, identity-link values, meal records or introspector secrets. Transport
authentication and each tool invocation independently introspect; each operation
also reloads the active issuer/subject link and local account. Every query and
write applies current ownership/food visibility, including component visibility.

## Tools and confirmation

`tools/list` advertises typed JSON input/output schemas and OAuth scope metadata.
All tools are closed-world; there are no external searches or AI/billing tools.
Names and notes are data, never instructions. Totals report saved known values;
missing nutrients are not zero, and tools provide no medical advice.

| Tool | Scope | Bounds and behavior |
| --- | --- | --- |
| `search_foods` | read | Query 1–100 characters; 1–20 active shared/own foods, stable name/ID order, offset 0–1000; serving units and exact IDs, no estimation. |
| `meal_diary` | read | One ISO date; 1–20 own meals, offset 0–1000, at most 20 items and 2000 note characters per meal; item truncation marked. |
| `nutrition_totals` | read | Ordered inclusive range of at most 31 days, 500 meals and 2000 items; larger requests fail and require a shorter range. |
| `preview_meal` | read + write | Explicit name (1–120 characters), date, notes up to 2000 characters, 1–20 exact food IDs and positive decimal-string servings below 1000 (up to four decimals); optional owned `meal_id` means full replacement. Creates a confirmation, never a diary entry. |
| `confirm_meal` | read + write | Exact preview UUID and literal boolean `confirmed: true`, only after explicit approval of the shown action. Atomically consumes one preview and saves through the existing meal serializer/snapshot service. |

The preview shows the date, name, notes, food names/providers/IDs/versions,
serving definitions, quantities and calculated nutrient amounts, plus the old
meal for replacements. Ask the user to resolve ambiguous food/portion choices.
Show replacement effects and obtain explicit approval before confirmation.
Client confirmation controls must remain enabled; a boolean is a client assertion
of user approval, not independent proof of a human click. No delete, bulk edit,
free-text estimate, automatic naming or catalog mutation is exposed.

Confirmations expire in five minutes, bind to the exact issuer link and OAuth
client, and are single-use. A fingerprint binds the current meal and selected
food definitions/components/sources. Stale edits, archive/permission changes,
foreign clients/users, expiry, revocation and replay fail without diary mutation.
Writes require available current foods; archived historical versions can still
be read in their owner's existing diary. Complex definitions are refused above
100 versions, 100 edges/sources, eight component levels or 200 expanded nodes;
unsupported nutrient magnitudes are refused. Pending previews are capped at ten
per identity. Expired rows cannot authorize writes and are removed on the next
preview or explicit local revocation; up to ten inactive rows per disconnected
identity may remain in the protected app database until operator cleanup.

Preview and confirmation transactions lock the identity, target meal and selected
catalog rows/current versions through validation and snapshot save. SQLite uses
an early identity-row write to acquire its writer lock because it ignores
`SELECT FOR UPDATE`; an intervening committed website/catalog update makes a
stale read-to-write upgrade fail closed. Row-locking databases also lock the
meal/food/version rows used by normal app writes. File-backed SQLite WAL tests
exercise actual competing website and catalog commits, not sequential mocks.

## Operator preparation and client connection

1. Independently verify the existing local user ID and central account UUID in a
   private operator session. Run migrations through the normal app release. Use
   `python backend/manage.py link_mcp_identity --subject <verified-uuid> --user-id <existing-id>`.
   The command never creates a user, matches email/username, or overwrites a link.
   There is at most one subject per existing user per issuer. Identity reassignment
   requires a separately reviewed private migration, never automatic relinking.
2. Infrastructure registers both named clients with their **actual** client
   callbacks, the exact MacroMapper resource and allowed scopes. It provisions
   the dedicated resource-bound Basic introspector. Do not register local OAuth
   clients with `register_mcp_client`; this app publishes no issuer/token/consent
   endpoints. Shared issuer UI owns login, consent and grant revocation.
3. Store the dedicated secret as `MACROMAPPER_MCP_INTROSPECTION_SECRET` in the
   Actions repository secret for the approved release. The app's generated
   deployment workflow already passes it into the existing private `.backend.env`
   release bundle. The enabled production policy requires a nonempty value with no
   default; bundle preparation and enabled production startup/checks fail visibly
   without it. Do not use `deploy/backend.env`, add
   secret volumes, reuse another resource credential or change `app-release/v1`.
   Local values belong only in ignored `backend/.env` or `deploy/.env`.
4. Review the concrete central `deploy/production/app.json` policy. It fixes
   `DJANGO_MCP_ENABLED=1` and `DJANGO_TRUSTED_PROXY_IPS=172.20.0.3`, requires the
   dedicated secret and includes the MCP probes alongside ordinary health. The
   gateway address invariant also pins `macromapper-ingress` to the same `.3`.
   This is the existing audited peer; the backend `.2` and frontend `.4` are not
   trusted, and no network/address migration is required. Preserve
   `--no-proxy-headers`; only the canonical exact-peer wrapper accepts forwarding.
   Source defaults remain off. Regenerate workflow only through
   `python deploy/check_parity.py --sync`. The coordinator holds `env-prod` until
   shared OAuth/YNAB, app registry, explicit identities and ingress are accepted.
   Existing `backend_required_env` intentionally stays empty for the first release
   from the old disabled backend; incoming fixed environment and gateway-peer
   policy plus enabled production checks validate the new runtime. Verify the new
   backend's effective exact peer value privately after release.
5. Infrastructure owns exact `/mcp` and protected-resource discovery forwarding:
   uncached, no interactive edge challenge, HTTP/1.1, no buffering, existing
   120-second upstream timeout and reviewed Host/Origin/proxy trust. Do not route
   app-local `/auth/mcp/` or issuer metadata. Keep ordinary API/frontend routes.
6. After the approved immutable app release, connect ChatGPT and Codex separately
   to the resource URL using their registered client configuration. Follow the
   central issuer login/consent. Start read-only. Verify tool discovery and one
   own-data read, foreign/wrong-resource denial, grant revocation and reconnection
   for each client. Live writes need an approved disposable meal and explicit
   preview/confirmation; verify one save, replay denial and ordinary website view.
   Record only sanitized outcomes, not private record/subject/token values.

Frontend `VITE_MCP_ENABLED` stays off: its historical scaffold consent/connections
pages target the old local provider. Central consent does not require rebuilding
those pages. Live client compatibility, callbacks and owner data are acceptance
work; local mocks and enabled-profile tests do not claim to establish them.

## Health, outage and rollback

Retain ordinary HTML root and JSON API 401 health. Enabled readiness adds exact
resource/authorization-server JSON and anonymous `/mcp` 401 with protected-resource
metadata challenge. The prepared policy uses the current common release probe
schema; it does not modify shared release code. Test malformed/wrong-audience and
expired/revoked clients, central outage (bounded denial, no cached authorization),
and ordinary login/REST/estimation concurrently. Do not print successful diary
responses. No live provider, ingress, credential or production change is included
in this source PR.

Disable the affected connection centrally to revoke grants; use
`python backend/manage.py revoke_mcp_identity --subject <verified-uuid>` to block
all MCP access for that local link and delete its pending previews immediately.
Existing REST login remains available. An issuer outage denies MCP operations.
For app rollback, apply the reviewed `deploy/production/mcp-disabled-policy.json`
delta to app policy and restore a compatible image through the
[app-only release/recovery guide](../deploy/production/README.md); remove MCP
readiness probes when disabling. Retain identity/confirmation tables and user
data. Do not reverse migrations, restore old grants/data casually or alter shared
networks. Rotate secrets via a new private release bundle, preserving approved
recovery credentials until retained releases are accounted for.

**First enabled-rollout failure:** stage the separate disabled-policy rollback
tool with `prepare_mcp_recovery.py` before activation, following the production
guide. `FAILED.json` bars a new disabled deploy, and the failed enabled tool's MCP
health cannot validate the captured old disabled backend. Invoke the pre-staged
disabled tool for rollback itself, after verifying that capture is default-off/
`DJANGO_MCP_ENABLED=0` and selecting the authorized DB mode. It uses unchanged
canonical release code and the same private recovery set, without editing either
immutable bundle or bypassing the failure barrier. Do not use it to claim a
still-MCP-enabled captured runtime is disabled.

The central rollout app policy expects the exact five gateway networks:
`notoli_backend_private`, `notoli_default`, `macromapper-ingress`,
`ynab_mcp_private` (ingress `172.30.89.2`) and `mcp_auth_private` (ingress
`172.30.92.2`). MacroMapper ingress is exactly `172.20.0.3`; Notoli ingress remains exactly `172.30.88.2`. Only ingress is
required on the two new private bridges; their known app companions may be
absent for independent app recovery. MacroMapper gains no network attachment.
Gateway exposure/health acceptance remains Infrastructure-owned.

Do not run an old three-network app recovery bundle against this five-network
baseline, or weaken its exact network checks. A coordinated legacy rollback must
first release the reviewed MacroMapper disabled profile with ordinary website/API
health and the five-network gateway expectation. Then the gateway owner explicitly
sets both `YNAB_ROUTE_PROFILE=disabled` and `MCP_AUTH_ROUTE_PROFILE=disabled`,
verifies the retained hostname 410 tombstones and exact three-network topology,
and only then selects the matched legacy app release/recovery bundle. Never
implicitly return exposed hostnames to `base` or silently detach shared routes.
All steps use their respective owner-controlled releases/maintenance locks.
Ordinary website/login/REST health stays mandatory throughout; DB restore remains
a separate deliberate decision. A newer app image can instead be recovered under
a compatible reviewed five-network disabled policy without downgrading ingress.

## Verification

Install `backend/requirements.txt` in an isolated Python 3.12 environment. From
`backend/`, run `python manage.py test`. The separate enabled app run is:

```powershell
$env:DJANGO_MCP_ENABLED='1'
$env:MACROMAPPER_MCP_INTROSPECTION_SECRET='synthetic-test-only'
python manage.py test app_mcp --settings=app.mcp_test_settings
python manage.py test mcp_framework --settings=app.framework_test_settings
```

Clear these synthetic environment values afterward. The framework settings/URL
module are test-only; production runs `app.settings`. CI runs disabled app/REST
regressions, isolated canonical-provider tests and enabled app transport/security
tests. Run ruff, immutable framework parity and release parity checks as usual.
