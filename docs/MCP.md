# MacroMapper MCP

Issue [#284](https://github.com/VanillaIceCube/MacroMapper/issues/284) adds an
application-owned resource server. Production remains **disabled** by
`deploy/production/app.json`. Source readiness is not real ChatGPT/Codex acceptance.
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
   release bundle. Its disabled-profile default is empty. Enabled production
   startup/checks fail visibly without it. Do not use `deploy/backend.env`, add
   secret volumes, reuse another resource credential or change `app-release/v1`.
   Local values belong only in ignored `backend/.env` or `deploy/.env`.
4. Review `deploy/production/mcp-activation-policy.json` as an **unapplied** policy
   delta: patch `environment.fixed`, add the required secret and remove its empty
   default, append the readiness rules to existing probes. Review exact gateway
   peer IPs for `DJANGO_TRUSTED_PROXY_IPS` and add them to fixed app policy; never
   guess, use a subnet/wildcard, publish a backend port, or change networks here.
   Regenerate the workflow with `python deploy/check_parity.py --sync`. Keep
   `DJANGO_MCP_ENABLED=0` in committed active policy until the coordinator accepts
   app registry, identities, ingress and preceding live acceptance.
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
For app rollback, restore the reviewed disabled app policy/image through the
[app-only release/recovery guide](../deploy/production/README.md); remove MCP
readiness probes when disabling. Retain identity/confirmation tables and user
data. Do not reverse migrations, restore old grants/data casually or alter shared
networks. Rotate secrets via a new private release bundle, preserving approved
recovery credentials until retained releases are accounted for.

## Verification

Install `backend/requirements.txt` in an isolated Python 3.12 environment. From
`backend/`, run `python manage.py test`. The separate enabled app run is:

```powershell
$env:DJANGO_MCP_ENABLED='1'
$env:MACROMAPPER_MCP_INTROSPECTION_SECRET='synthetic-test-only'
python manage.py test app_mcp
python manage.py test mcp_framework --settings=app.framework_test_settings
```

Clear these synthetic environment values afterward. The framework settings/URL
module are test-only; production runs `app.settings`. CI runs disabled app/REST
regressions, isolated canonical-provider tests and enabled app transport/security
tests. Run ruff, immutable framework parity and release parity checks as usual.
