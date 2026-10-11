# PR #239 audit for MacroMapper #240

Audit date: 2026-10-11. Status: **Agent 5 resumed the source audit;
refreshed VM report reconciled; v2 proposed, owner approval pending**.
[PR #239](https://github.com/VanillaIceCube/MacroMapper/pull/239) was merged
without owner authorization. Its contents are candidate implementation, not an
approved architecture or evidence of production deployment.

Shared decisions belong on [Infrastructure #4](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/issues/4).
App implementation belongs on [MacroMapper #240](https://github.com/VanillaIceCube/MacroMapper/issues/240).
Architecture approval, each PR merge, and each production action require
separate explicit owner authorization. Agent 3 is the sole production operator.

## Agent 5 continuation

The owner consolidated repository work into Agent 5; historical Agent 1/2
reviews below are retained as evidence, not active ownership assignments.
Infrastructure now has a selected source repository,
`VanillaIceCube/JudeAndrewAlabaInfrastructure`; the website stays independent.
Agent 3's [refreshed audit at 09:49–09:53 PDT](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/issues/4#issuecomment-6111383750)
confirms unchanged topology/images, Engine 28.2.2, Compose 2.40.3, linux/amd64
images and all four namespaced upstreams resolving from the current proxy.
External-network syntax passes; actual cutover/recovery is not tested.

[Proposed contract v2](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/issues/4#issuecomment-6111397179)
incorporates the staging clarification: unique private incoming directories,
stable per-app locks, a coordinated maintenance lock, complete prior
configuration/environment/image/DB recovery, and bounded read-only readiness
before writing the success record. It adopts existing route networks and
preserves both already-running apps. No image/schema changes accompany the
ingress transfer. Agent 5 agrees with the keep/simplify/replace recommendations
below; no wholesale revert is recommended.

Agent 3's [v2 feasibility review](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/issues/4#issuecomment-6111422055)
finds no required interface change. It requires final recovery capture under
the release hold, correct legacy bind paths, app-only rollback, protected
stable locks, digest consistency and disposable handoff/reversal tests.
Explicit owner architecture approval remains required before finalizing
shared-interface implementation. Port-3000 consumers, Cloudflare
policy, deployment identity/permissions, peak capacity, backup destination and
restore evidence remain production prerequisites. The advanced infrastructure
automation stack is deferred; no merge or production authorization is implied.

## Evidence and limits

- Reviewed the PR diff from `da7bc0fabd0475712251af154e46a5b6e5dfce31`
  to head `3ad839f2a4f9f2d63f2364b8ea292c9556d869cb`, merged into MacroMapper
  `main` at `a510a3a5ad9cc3f70304f451bbbac72f3cc7c139`.
- Read both issue bodies/comments and Notoli's checked-in Compose/deploy
  configuration at `main` `b4586362d5797e6da44f0a6dcaaaa37ada747113` and
  `env-prod` `230e80018e5270d28f6c2100d94e6cf528020caa` through the GitHub API.
  Repository configuration is not proof of live host configuration.
- Read Agent 3's complete [VM audit](https://github.com/VanillaIceCube/Notoli/issues/904#issuecomment-6107091928)
  and Agent 1's [VM reconciliation](https://github.com/VanillaIceCube/Notoli/issues/904#issuecomment-6107111199).
  The observations below are attributed to that inspection, not a separate
  live audit by Agent 2. Read the complete [proposed contract v1](https://github.com/VanillaIceCube/Notoli/issues/904#issuecomment-6107124549)
  and posted [conditional contract review](https://github.com/VanillaIceCube/Notoli/issues/904#issuecomment-6107138862).
  VM feasibility and release-lock clarification remain pending at this
  checkpoint; no contract endorsement is implied.
- No SSH, host changes, DNS/TLS changes, production dispatch, merge, or
  deployment was performed by Agent 2. Compose version was unverified at that
  checkpoint; the refreshed report above supplies it. Cloudflare
  mode/cache/firewall rules and production credential capabilities remain
  unverified.

## Component recommendations

These recommendations reflect source review, local checks and Agent 3's
observations. Shared implementation still requires the reviewed contract and
separate owner approvals.

| Component | Recommendation | Reason and follow-up |
| --- | --- | --- |
| `backend/app/settings.py` and `backend/app/tests.py` | Keep | Explicit production secret/hosts, development-only origins, real Host validation, and secure cookies are app-local safeguards. HTTPS header trust still depends on restricted backend reachability and ingress overwriting forwarded protocol. |
| `deploy/docker-compose.shared.yml` | Simplify after contract approval | Keep no published app ports, unique service names, explicit image references, app network and backend egress. Prefer an explicit production app Compose file over profile/extends/reset layers if the reviewed contract supports it. Network names/topology remain undecided. |
| `deploy/notoli.compose.override.yml` | Replace after verified ingress cutover | MacroMapper should not supply Notoli's permanent override. Preserve any installed bridge until the replacement is deployed and verified; early removal could break routing. |
| `deploy/nginx-shared.conf` | Transfer to host-owned infrastructure after approval | Keep hostname routing, runtime Docker DNS, overwritten protocol/host and `no-store`. Its mount comes from MacroMapper's release directory and app CI uploads it. The host owner must control the canonical vhost and TLS lifecycle. |
| `scripts/prepare-production-bundle.py` | Keep validation; simplify payload after approval | Raw environment files preserve literal credentials, missing values fail before staging, and refs use the full SHA. Staging is justified by secret handling. Remove ingress files from app uploads when the host-owned replacement is ready. |
| `scripts/deploy-production.sh` | Keep data checks; replace proxy operations after approval | Keep lock, legacy-stack rejection, missing-file initialization, SQLite backup and deployment-user ownership. Checks hard-code `notoli-proxy`, vhost mount and ingress network; `nginx -s reload` mutates shared ingress. These cannot remain in independent app releases. |
| `.github/workflows/ci-deploy.yml` | Keep safeguards; simplify after approval | Keep SHA image selection, same-origin frontend, isolated credentials, serialization and absence of pruning. Stop uploading shared vhost/invoking proxy operations once the approved replacement exists. |
| `deploy/tests` | Keep behavior coverage; replace obsolete bridge fixture after cutover | Compose/secret/routing/data tests cover distinct failures. The synthetic Notoli fixture verifies a merge shape, not live trust/configuration. No evidence justifies removing safeguard tests to meet a line-count target. |
| `deploy/docker-compose.yml`, `deploy/nginx-proxy.conf` | Keep for standalone local use | They publish ports and own a proxy; they are unsuitable for the shared production host without the overlay. |
| Deployment docs and launch handoff | Simplify now | Remove claims of approval/current host verification. Use one deployment guide and a short handoff; existing recovery procedures remain candidates subject to approval. |

A wholesale revert is not recommended from repository evidence: it would
restore destructive cleanup and lose production/data safeguards. The shared
bridge is not endorsed as a permanent design.

## Release and recovery gaps

1. **Shared ingress mutation:** CI uploads `nginx-shared.conf` before the remote
   script takes its lock, and the script reloads `notoli-proxy`. The lock does
   not protect uploads. GitHub concurrency serializes this workflow only.
   Recommend an app-only deploy interface and separately controlled ingress.
   Stage private bundles by revision outside active configuration and validate/
   promote them under the same app lock as backup/migration/service changes.
2. **Incomplete configuration rollback:** Recovery saves old `.env`,
   `.backend.env` and DB, but CI overwrites Compose/script/vhost files before
   backup. The guide asks the operator to retain old configuration without
   creating that recovery set. Identify matching old configuration/images as
   well as DB/environment in the final release contract.
3. **Success before health evidence:** `compose up -d` and `nginx -t` do not
   verify app readiness; `deployed-release.env` is written before HTTPS smoke
   tests. No Compose healthcheck or automated app health gate exists. Agree
   on bounded read-only readiness/HTTPS checks and failure/recovery behavior.
   These checks should not create accounts, send mail or call billable AI;
   mutating functional acceptance belongs in the approved operator plan.
4. **Manual recovery and maintenance window:** Backend writers stop before
   backup/migration. Failure leaves the backend stopped; automatic rollback is
   absent. A first release may have no previous DB/environment. Confirm
   downtime, recovery inputs and post-restore checks with the VM operator.
5. **Operational prerequisites:** Local backup creation does not provide
   recurring off-host backup, retention, restore evidence, resource headroom,
   or full certificate/cache verification. Track shared operational prerequisites
   on [Infrastructure #4](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/issues/4);
   retain app acceptance work in MacroMapper #240/#236/#238.
6. **Forwarded client addresses:** The candidate vhost appends client-supplied
   `X-Forwarded-For` with `$proxy_add_x_forwarded_for`. Agent 3 observed this
   mounted configuration; Notoli instead overwrites it with `$remote_addr`.
   No current MacroMapper authentication/authorization consumer was found by
   searching backend code for forwarded/client IP handling. Preserve the
   verified Host/HTTPS protections, but recommend overwriting client-address
   metadata to match Notoli unless a separately verified Cloudflare client-IP
   policy is approved. Do not represent the appended chain as authenticated.

## VM observations reconciled

Agent 3 checked the host on 2026-10-11 at 01:21–01:22 PDT. MacroMapper is
**already running** at SHA `a510a3a5ad9cc3f70304f451bbbac72f3cc7c139`, with no
published app ports. Notoli's app images use `latest`. Both public HTTPS roots
returned 200; this is route availability, not feature acceptance or approval.

The observed proxy is `notoli-proxy`, owning 80/443 and mounting MacroMapper's
vhost from `/opt/apps/macromapper/nginx-shared.conf`. It joins
`notoli_backend_private`, `notoli_default`, and `macromapper-ingress`.
MacroMapper's backend/frontend join `macromapper-ingress` and
`macromapper_default`; neither joins a Notoli network. These memberships match
the source upstream assumptions and Agent 1's reconciliation. The proxy does
not join `notoli_backend_egress` or `macromapper_default`.
Preserve the existing MacroMapper route during any ingress transfer.

Notoli's internal `172.30.88.0/29` retains proxy `.2`, backend `.3`, and exact
proxy trust `.2`. Stopping the old proxy must not be assumed to release its
network endpoint; Agent 3's approved plan must handle address/port release and
reverse handoff explicitly. No app migrations belong in an ingress-only cutover.

The origin certificate covers both hostnames and expires 2041-02-04; its key
mode is 0600. Public TLS success does not prove Full (strict), cache rules, or
origin firewall policy. At inspection the VM had 1 CPU, 1.9 GiB RAM, about
1.1 GiB available at idle, no swap, and 16 GiB disk available. Idle headroom
does not prove peak capacity; builds remain on CI and capacity gates need review.

MacroMapper's DB is `/opt/apps/macromapper/db.sqlite3` (0600), deployment
directory 0700 and backend environment 0600. Backup files exist, but consistency,
off-host retention and restore success remain unknown. Preserve matching DB,
environment, effective Compose/vhosts, network topology and exact image digests
before an authorized cutover. The VM checkout head differs from the running
image SHA; runtime/container evidence governs what is installed.

## Inputs for the proposed contract

Candidate upstreams: `macromapper-frontend:80` and `macromapper-backend:8000`.
Current external network: `macromapper-ingress`. Both services also join
MacroMapper's default network; only that network has the generic `backend`
alias used by the frontend image. Merged production services publish no ports.
The default network supplies backend outbound access for OpenAI/Resend.

The vhost sends `/` and SPA deep links to the frontend; `/auth/`, `/api/`,
`/admin/`, `/static/admin/` and `/static/rest_framework/` to the backend.
It sets canonical Host/HTTPS scheme, clears forwarded host, and returns
`no-store` for dynamic auth/API/admin responses. Preserve direct backend
routing: the frontend's HTTP proxy would replace the HTTPS scheme with HTTP.

Notoli's checked-in Compose reserves proxy `172.30.88.2` and backend
`172.30.88.3` on its private `/29`, with separate backend egress. Its frontend
publishes 3000; its workflow selects `latest`, prunes host-wide Docker resources
and recreates its proxy. These repository-only facts agree with Agent 1's
initial report and the VM observations above. MacroMapper's ingress must not
join Notoli's backend or weaken its trusted-peer boundary. One network shared
by all app backends would need explicit isolation review; the current network
is an app-specific candidate.

The v1 contract proposes host-owned ingress, preserving these upstreams and
route-facing networks in place, overwritten client-address headers, separate
release/rollback ownership and sequential cutover. Agent 2's conditional review
finds these compatible, with staging/lock scope and bounded health checks to
clarify. This is historical v1 review; the Agent 5 continuation above supersedes
its ownership and coordination status. Infrastructure repository ownership is
now selected. Maintenance window, backup destination, port-3000 consumers and
capacity policy still require owner decisions; v2 is not approved.

## Local verification on 2026-10-11

- `python backend/manage.py test app --verbosity=2`: 3 passed; no DB setup.
  A local collected-static-directory warning does not verify production assets.
- `python -m unittest discover -s deploy/tests -v`: 11 discovered, 5 passed,
  6 Linux shell tests skipped on Windows. Passed checks include real merged
  Compose, raw test credentials, fixture network preservation, and disposable
  HTTPS routing/header/cache/proxy restart tests.
- Local Compose `v2.39.2-desktop.1`; Django `5.2.10`. No production version
  is inferred. Linux shell recovery/ownership tests still need Linux CI.

No live launch, Notoli MCP/OAuth, actual email/AI, reboot, or production restore
acceptance is claimed by this audit.
