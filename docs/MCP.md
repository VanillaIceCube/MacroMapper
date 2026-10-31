# 🔌 MacroMapper MCP

MacroMapper owns its MCP tools and OAuth in [#284](https://github.com/VanillaIceCube/MacroMapper/issues/284).
The existing [canonical framework](MCP-FRAMEWORK.md) supplies transport, discovery,
PKCE, consent and revocation unchanged. Infrastructure routes the application's
own endpoints; no shared issuer, new service, network or YNAB dependency is needed.
Website login, REST JWTs and existing AI estimation remain independent.

## 🔐 Access and permissions

The resource is `https://macromapper.judeandrewalaba.com/mcp`; the issuer is the
same origin. The app registry is `macromapper_mcp.server.create_server`.
OAuth uses existing MacroMapper accounts and separate MCP tokens. Every operation
rechecks the active token, scopes and current user's ownership; caller-supplied
user IDs cannot select another account. REST JWTs cannot call MCP.

- `macromapper:read` is required and the only default grant. It reads accessible
  foods and the account's meals, totals, proposals and notifications.
- `macromapper:write` permits explicitly confirmed business mutations, with the
  same validation and ownership rules as the application.
- `macromapper:estimate` separately permits paid AI estimates. It also requires
  read/write access and explicit confirmation; read access alone cannot spend
  provider credits. Tests mock providers and do not make paid requests.

Writes use an app-owned preview/confirmation record. Review the exact operation
and payload before confirmation; do not automatically confirm or retry an
uncertain result. Catalog access follows existing visibility and creator rules;
MCP is not administrative access. Planned goals/activity and account credential
management are outside the registry.

## 🧰 Available capabilities

The registry exposes 18 tools covering 19 closed mutation actions. Call
`operation_schema(action)` before preparing a change: it returns the allowed
fields, required values, bounds and scopes for that action.

| Area | Read tools | Confirmed actions |
| --- | --- | --- |
| Food catalog | `search_foods`, `get_food` | Create or update your personal foods; archive them. Shared catalog visibility follows the existing app policy. |
| Diary and nutrition | `meal_diary`, `get_meal`, `nutrition_totals` | Create, edit or delete meals; save or update reviewed drafts. Drafts require explicit name and notes, with an empty notes string allowed. |
| Proposals | `list_proposals` returns summaries/IDs; `get_proposal` pages current review items | Review/edit, delete draft proposals, or separately accept a proposal into the diary. |
| Paid estimation | Read proposals before accepting them | Estimate a new proposal, request a proposal follow-up, or adjust a proposal/meal draft. These four actions additionally require `macromapper:estimate`; they do not directly accept a diary meal. |
| Notifications | `list_notifications`, `get_notification` | Mark one read/unread, delete one, mark all current notifications read, or clear the current set. Later arrivals are excluded from an existing preview. |

`preview_change` and `confirm_change` handle the 15 nonpaid actions and advertise
read/write access. `preview_paid_change` and `confirm_paid_change` handle the four
paid actions and advertise read/write/estimate access. Their action enums are
disjoint; using the wrong confirmation pair rejects the request without consuming
the approval. Four additional
typed notification preview tools cover update, delete, mark-all-read and clear-all.
Every preview expires after five minutes, is bound to the same OAuth token/client/
user, and becomes unusable after confirmation. Refreshing or revoking the token,
changing the target or its catalog definitions, or changing ownership requires a
new preview. Paid approval is consumed before the provider wait, even if that
request fails; inspect the outcome and never retry it automatically. At most ten
pending previews are kept per account.

Pages contain at most 20 records. Nutrition totals cover at most 31 days, 500 meals
and 2,000 meal items; bulk notification previews cover at most 200 existing entries.
Large or deeply nested data is rejected or explicitly marked truncated. Narrow the
request rather than treating truncated output or missing nutrients as complete.

Proposal lists do not duplicate current items or historical revision snapshots.
`get_proposal(proposal_id, item_limit=5, item_offset=0)` returns current items and
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
OAuth verification. Requests beyond that capacity fail before consuming an
approval; cancellation retains a worker slot until the operation finishes.
An oversized paid result returns a successful, explicitly truncated receipt
with retained proposal IDs or a bounded temporary-adjustment summary. Temporary
adjustments do not modify the diary. Never repeat a paid call to recover detail.

## 🖥️ Consent and client setup

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
python manage.py register_mcp_client --client-id macromapper-chatgpt \
  --name 'MacroMapper for ChatGPT' \
  --redirect-uri 'https://chatgpt.com/connector_platform_oauth_redirect'
```

If the client's management page supplies a different exact URI, review it before
changing the allowlist; do not guess older callback paths or add wildcards. The
owner signs in using their ordinary MacroMapper account and reviews consent.
Keep distinct client IDs when appropriate, S256 PKCE, one exact resource parameter
and `token_endpoint_auth_method=none`. The command refuses to overwrite an
existing registration. No dynamic client registration or loopback callback support
is claimed. Live sign-in/tool acceptance remains separate from offline tests;
registering a client does not install a plugin or issue a user grant.

## 📦 Release and recovery

Production app policy enables `DJANGO_MCP_ENABLED=1`, fixes the issuer origin and
trusts only the existing gateway peer `172.20.0.3`. The backend runs one Uvicorn
worker with proxy-header auto-trust disabled; the canonical ASGI wrapper alone
accepts that exact peer. The production frontend Docker build defaults
`VITE_MCP_ENABLED=1`; a disabled local build can explicitly pass `0`.
The ordinary frontend/API probes remain, with exact issuer/resource JSON and an
unauthenticated MCP 401 resource-metadata challenge added to release readiness.

Coordinate the existing Infrastructure vhost before enabling the app. Run normal
private SQLite capture/integrity checks before the additive OAuth and confirmation
migrations. Retain the prior disabled release directory, its checksummed policy,
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
authorization. See [the production guide](../deploy/production/README.md).

## 🧪 Local verification

Backend development remains off by default. Use an isolated database, then set
`DJANGO_MCP_ENABLED=1`, an exact `DJANGO_MCP_BASE_URL` and the real frontend origin
before `python manage.py migrate` and `python serve.py`. Set `VITE_MCP_ENABLED=1`
for Vite. Do not reuse a production database or token in tests.

Run `python manage.py test` in `backend`, then separately
`DJANGO_MCP_ENABLED=1 DJANGO_MCP_BASE_URL=http://localhost:8000 python manage.py test mcp_framework macromapper_mcp`.
Run frontend tests/lint/build, the canonical framework/parity checks and the
production deployment suite on disposable Docker. Tests exercise synthetic OAuth,
real app services and mocked AI; deployment checks do not establish live client
consent or permission to create business data.
