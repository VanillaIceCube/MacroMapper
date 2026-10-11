# Codex handoff: minimum MacroMapper production launch

## Repository implementation status

Replacement [PR #239](https://github.com/VanillaIceCube/MacroMapper/pull/239)
implements the approved repository prerequisites below. See
[the deployment guide](README.md) for exact server commands, required variables
and secrets, configuration files, recovery, and live acceptance.

Implemented artifacts: `docker-compose.shared.yml`, `nginx-shared.conf`,
`notoli.compose.override.yml`, `../scripts/prepare-production-bundle.py`, and
`../scripts/deploy-production.sh`. The deployment workflow uses reviewed
SHA-tagged images, private environment files, and pre-migration SQLite recovery.
Django production settings and routing/recovery regression tests are included.

The instructions below retain the approved scope and recorded host facts.
They are not evidence of live deployment. Credentials, package access, installed
override/TLS, deployed revision, and application/Notoli smoke tests remain for
the deployment chat. Keep #238 and broader #236 open until their acceptance
criteria are verified. Do not deploy or merge from this repository handoff.

## Task and authorization

Prepare the minimum repository changes needed to launch the existing MacroMapper
application at https://macromapper.judeandrewalaba.com/ on the existing Droplet.
The user approved the requirements below. Explain any additional blocker and
proposed fix before implementing it. Do not add general hardening or product
changes to this work.

Do this repository preparation on the user's personal computer. Another Codex
chat is handling deployment preparation on the actual Droplet. Do not deploy,
merge, change DNS/TLS, or modify live Notoli services from this handoff.

Read the repository's AGENTS.md first. Follow its documentation and check
requirements in proportion to the changes. Inspect the current main branch;
do not assume the old PR's changes belong in this implementation.

## Create or confirm the ticket, then work on the replacement PR

1. Create the implementation ticket before coding if it does not already exist.
   Search the repository first to avoid a duplicate. The ticket has already
   been created as **#238: Deploy MacroMapper with only confirmed production
   launch prerequisites**:
   https://github.com/VanillaIceCube/MacroMapper/issues/238
2. Confirm #238 is accessible and use it to track this implementation. If it is
   genuinely absent, create a ticket with the approved requirements in this
   document. If access is unavailable, report the access problem rather than
   creating a duplicate elsewhere or claiming the ticket was created.
3. PR #237 was closed at the user's request because its implementation exceeded
   the minimum launch scope. Do not reopen or merge it:
   https://github.com/VanillaIceCube/MacroMapper/pull/237
4. Find the open draft PR from branch `fix/minimum-production-launch`. It starts
   from main and initially contains this handoff only. Continue that PR; do not
   create another replacement PR unless it is absent. Reference #238 without
   claiming a completed live deployment.
5. Keep the PR draft until the minimum changes are implemented and checked.
   Report the exact changes, validation, and remaining server setup to the user.

Original umbrella deployment ticket: #236. It has broader operational acceptance
criteria. Completing repository preparation or this narrower ticket does not
by itself complete #236.

## Confirmed environment and constraints

- Repository: https://github.com/VanillaIceCube/MacroMapper
- Target hostname: `macromapper.judeandrewalaba.com`.
- Existing Ubuntu Droplet: `jude-droplet`, public IPv4 `64.23.173.170`.
- Approximately 2 GiB RAM; it is a shared production host running Notoli.
- Docker Engine and Compose are already installed. Compose was v2.40.3 at inspection.
- Notoli's Compose directory is `/root/apps/notoli`.
- `notoli-proxy` already publishes host ports 80 and 443.
- `notoli-frontend` already publishes port 3000. Do not change Notoli's exposure
  as part of this MacroMapper implementation.
- Notoli's backend is on its own private network. Its proxy has a static address
  `172.30.88.2` and the backend `172.30.88.3`; these are part of Notoli's trusted
  proxy configuration and must be preserved.
- Notoli's main Compose and Nginx files are uploaded by its own deployment process.
  A MacroMapper route must survive subsequent Notoli deployments.
- MacroMapper's hostname currently falls through to the Notoli frontend.
- The user created the proxied Cloudflare DNS record and selected Full (strict).
  Notoli returned HTTP 200 after that change.
- Existing Origin CA files are `/root/apps/notoli/certs/origin.pem` and `origin.key`.
  The certificate covers `*.judeandrewalaba.com` and `judeandrewalaba.com` and was
  valid through 2041. Do not download or commit these files or private keys.
- MacroMapper production credentials, GitHub deployment variables/secrets, and
  package access still need confirmation by the deployment chat.

## Approved requirements

### 1. Resolve shared ingress

Give MacroMapper a dedicated hostname route through the existing public Nginx.
Keep its frontend and backend ports private, and preserve Notoli's current
routing and networks.

The proposed approach communicated to the user is a persistent Notoli Compose
**override**, adding an additional Nginx vhost mount and a dedicated shared
Docker ingress network. Supply the override template and setup instructions as
MacroMapper deployment artifacts; do not edit Notoli's source repository.

Provide a shared-ingress Compose overlay for MacroMapper that starts only its
frontend/backend and excludes its standalone proxy. Preserve the existing
standalone proxy for local HTTPS use. Use unique upstream DNS names on the shared
network, and preserve backend outbound access for OpenAI and Resend. Nginx
should be able to start even when MacroMapper containers are temporarily down;
use Docker DNS resolution at request time for the shared vhost if needed.

Do not add another listener on public 80/443, publish frontend/backend ports,
replace the existing public proxy, or put MacroMapper on Notoli's private
backend network. Document the one-time host setup and how overrides are retained.

### 2. Configure the existing application for production

- Set `DJANGO_DEBUG=0`, a generated Django secret, explicit production hosts,
  correct origin/base URLs, and an empty `VITE_API_BASE_URL` for same-origin use.
- Ensure Nginx sets the HTTPS protocol header correctly instead of trusting
  arbitrary client-supplied protocol/host headers.
- Enable secure Django session and CSRF cookies for production.
- Keep authenticated `/auth/`, `/api/`, and `/admin/` responses uncached.
- Run `manage.py check --deploy` with production settings and assess findings.
  Do not add HSTS coverage/preload policy or silence warnings merely to make
  the output clean. Document intentional, nonblocking findings.
- No arbitrary secret-length policy or new environment configuration system
  is needed; the deployment must provide a generated production secret.

### 3. Confirm credentials and existing release access

Document the existing required GitHub Actions variables/secrets and any genuinely
necessary shared-ingress values. The deployment chat will obtain OpenAI and
Resend credentials, verify the sender, and confirm SSH/GHCR access.

Never put API keys in frontend build variables or committed files. Do not reuse
Notoli credentials without explicit user agreement. Do not introduce new host
accounts or change SSH policy merely to satisfy this repository preparation.

### 4. Remove destructive deployment behavior

Remove or narrowly scope `docker system prune -af` so this shared host's unrelated
images/cache are not deleted. Restrict access to deployed `.env` and TLS private
key files. Initialize a missing SQLite file without truncating an existing file
or letting Docker create a directory at the database bind mount.

### 5. Deploy the reviewed revision and preserve data

Make the existing workflow use the shared-ingress stack and current migrations.
It must not attempt to start/recreate a competing standalone public proxy.
Use images corresponding to the chosen release revision, retain the existing
SQLite mount, and document a recovery/redeployment procedure. Protect existing
data before migration or replacement. Do not add a new database migration,
backup framework, or scheduled monitoring system to implement this requirement.

### 6. Verify the current experience

Repository checks should validate the actual changed deployment/settings paths.
Include a meaningful shared-ingress configuration/routing check if practical,
including preservation of Notoli's existing proxy network configuration.

The deployment chat will run live smoke tests: HTTPS and correct routing,
registration/login/logout, password reset, catalog search, meal CRUD/totals,
unmatched AI estimation, private-record isolation, data persistence after repeat
deployment/restart, and Notoli health. Record the deployed revision and manual
setup steps. Do not mark the ticket's live acceptance complete using only local
unit tests or Nginx syntax checks.

## Explicitly excluded

Do not carry over the following choices from PR #237:

- New AI quota model/table/database migration or a 200/day request policy.
- New authentication rate-limit policy.
- Changes to AI output/tool limits, retries, model choice, or provider behavior.
- Unrelated body-size or timeout adjustments without a reproduced launch blocker.
- HSTS preload, subdomain coverage, or forced HSTS policy.
- New product features, database replacement, Kubernetes, or architecture redesign.
- Automatic backup/monitoring infrastructure or host-wide SSH/account changes.

If live testing reveals a functional blocker, explain its evidence and proposed
minimal fix to the user before expanding the scope.

## Handoff back to the deployment chat

Return the ticket URL, replacement PR URL, tested commit SHA, exact one-time
server commands/templates, required variables/secrets, and checks performed.
List unresolved facts clearly. Leave production credentials, live ingress
installation/reload, deployment and live smoke testing to the Droplet chat.
