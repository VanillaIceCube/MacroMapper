# 🚀 Production releases and recovery

This guide covers MacroMapper's app-only release and explicit recovery process.
For local development, use the [deployment README](../README.md). Infrastructure
owns the shared release engine and host ingress; each app owns its configuration,
credentials and operational acceptance.

| Task | Section |
| --- | --- |
| Release an already prepared app | [Release sequence](#-release-sequence) |
| Resolve a failed release | [Failure and recovery](#-failure-and-explicit-recovery) |
| Prepare a host or change settings | [Host preparation](#-host-preparation-and-activation) and [configuration](#-configuration) |
| Review detailed behavior | [Transaction and data capture](#transaction-and-data-capture) |

For an existing deployment, confirm required CI/review on `main`, the exact
reviewed source tree, applicable owner/operator authorization and accepted host
prerequisites before promotion through the existing `env-prod` process. Merging
`main` does not deploy. Initial adoption and migrations retain their specific
procedures below; this guide does not establish their live completion.

**Before the first MCP-enabled release, verify the saved disabled controller
and read the [first-enable recovery guidance](#-first-enable-recovery).**

## 🚀 Release sequence

1. CI verifies parity before destination credentials or image publication, builds
   full-SHA-tagged backend/frontend images and records their actual immutable
   digests. Every pull, migration and startup uses those digests, never `latest`.
2. CI builds a private bundle identified by `<source-sha>-<run-id>-<attempt>`.
   It contains only app Compose, `app.json`, `release.py`, environment,
   release identity and checksums; never ingress files or certificates.
3. CI reserves a fresh `incoming/<release-id>` directory and uploads only that
   bundle. It never overwrites active files before locking or reuses an attempt.
4. The common transaction validates the candidate, captures matched recovery
   data and verifies backup/restore before migrating. It starts only the two app
   services and records success only after bounded readiness checks.

The staged bundle checksums `app.json`. Release and rollback run offline without
an Infrastructure checkout or code downloads. One transaction file keeps failure
ordering and crash barriers reviewable; app policy is separate from that state
machine.

### Authorized deploy command

Set `app_root=/opt/apps/macromapper` and resolve `release_id` from the exact reviewed private
release/recovery record. Use a retained, reviewed copy of this release tool,
never a legacy proxy-owning deploy script.

CI invokes the equivalent of:

```bash
python3 "$app_root/incoming/$release_id/release.py" deploy \
  --root "$app_root" --bundle "$app_root/incoming/$release_id"
```

## 🛟 Failure and explicit recovery

The release tool writes plain progress steps to stderr, such as
`Release: Applying database migrations`. Errors name the current step; failed commands
include their exit code, while command output and credentials stay private.
Readiness timeouts distinguish the direct backend API from public routes.
On failure, inspect the app's `FAILED.json` if present and `recovery/` privately;
early failures may leave no complete recovery set. Preserve existing records
before retrying or choosing recovery below.

`FAILED.json` is written **before stopping writers**, so process death also
blocks the next deploy. The success record `current.json` is replaced only
after readiness. On migration/startup/readiness failure the backend is stopped,
recovery is preserved, and the operator must select recovery explicitly.
No automatic DB restore can silently discard later writes.
A SIGKILL/host crash still requires the operator to inspect containers and stop
writers before recovery; the persistent marker does not itself stop a process.

The private recovery set contains captured effective runtime (including Env),
app-only Compose, raw old environment, immutable old local image IDs, original
config/script/env evidence, previous release files/record, and verified DB backup.
Retain these plus cached images. The tool never prunes them. Keep recovery files
private and out of logs/tickets. Retained management containers also contain raw
environment and possible DB journals; treat them as private recovery evidence.
Command errors intentionally withhold captured output; diagnose privately using the saved configuration.

<a id="operator-commands-after-separate-authorization"></a>

<a id="-operator-commands-after-separate-authorization"></a>

### Authorized recovery commands

Use the same `app_root` and selected `release_id` from the private record.
Run the failed attempt's retained, reviewed `incoming/$release_id/release.py`.
It automatically selects the checksummed `release.py` and `app.json` saved under
`recovery/$release_id/previous-release/`, while holding the existing deployment
locks. The recovered app uses its own readiness policy, including a previously
disabled MCP profile. You still choose the recovery ID and database mode.

Missing, changed, foreign or unrecorded controller/policy data stops recovery
before Docker or database changes; no latest-script or candidate-policy fallback
is guessed. Legacy recovery without an accepted saved release still requires
its separately reviewed procedure. Retain incoming bundles and recovery records.
Older tools that predate automatic selection retain their documented manual
controller choice; do not overwrite those immutable bundles.

For an approved rollback that can lose post-snapshot writes:

```bash
python3 "$app_root/incoming/$release_id/release.py" rollback \
  --root "$app_root" --recovery "$release_id" --restore-database
```

Recovery verifies cached images before stopping the backend, saves the current
DB/journals from the stopped writer too, restores the selected DB with its
original ownership/mode, and recreates **only app services**, no pull. It runs
the saved release's readiness gates and records success only afterward. Failed rollback
stops backend writers and leaves the failure marker/recovery data intact.

If backup/check failed **before migration started**, the operator may instead
restart the captured previous app configuration with all current data (no older
snapshot selection). Current journals are consolidated before container recreation:

```bash
python3 "$app_root/incoming/$release_id/release.py" rollback \
  --root "$app_root" --recovery "$release_id" --keep-database
```

That mode is rejected after the recorded migration-started stage. Its safe-data
flag persists through rollback failure, allowing a retry after transient readiness
failure without editing markers or choosing an unnecessary old snapshot. If a crash
occurred before the marker/recovery set was complete, inspect privately and use
a specifically approved recovery plan; do not fabricate a success record.
Rollback is not a substitute for off-host backups and a full functional restore
drill. Both remain deployment acceptance gates.

<a id="-main-first-source-and-intentional-release-lag"></a>

<a id="main-first-source-and-intentional-release-lag"></a>

## 🧭 Ownership and promotion

Follow the [main-first release policy](https://github.com/VanillaIceCube/FullStackTemplate/blob/main/.github/README.md#main-first-releases).
Develop and review ordinary changes through PRs targeting `main`, then promote
only the exact reviewed source tree through the existing protected `env-prod`
process. A promotion merge may have a different commit ID, but its source tree
must match the reviewed main commit. Preserve required CI, reviews and explicit
owner/operator authorization. The workflow accepts `env-prod` pushes and manual
dispatch selecting that branch; its branch check does not enforce main ancestry.
Merging main does not deploy, and source review does not authorize host operations.

An explicitly owner-authorized deployment experiment must return promptly to
main through review before the next ordinary promotion. Preserve both histories
and newer main work; never reset or force-push to manufacture parity. Intentional
release lag is allowed while prerequisites or acceptance remain unfinished.
History reconciliation does not authorize deployment or require matching live
and main trees. An absent production branch is not a reason to create one.
Use the owner-designated operator and its scoped plan; an explicitly authorized
mission may cover both source and promotion stages. Agent 3's historical ingress
migration assignment is not a permanent operator identity.

The [#329 audit](https://github.com/VanillaIceCube/MacroMapper/issues/329) on
2026-10-30 compared `main` at `fe8820bf2a390354fe3b2d5e046f6212ee7bd502`
with `env-prod` at `fc5ff4245fd0e241839f1f58df317f1a16aacf5d`. The five commits
unique to production were merges, and its full tree exactly matched main
ancestor `52e9e845bddc58ab173a69584242c24c7af56840`. Reconcile that ancestry
without reverting newer main source or deploying unrelated changes. The later
central-MCP withdrawal preserves this history and does not require a MacroMapper
production deployment: the withdrawn central-issuer policy was recorded as unreleased. Recheck current
release evidence rather than inferring live state from this historical audit.

<a id="-shared-implementation-and-app-configuration"></a>

<a id="shared-implementation-and-app-configuration"></a>

## ⚙️ Configuration

[app.json](app.json) owns the app's services, container names, domain,
environment, networks, database and readiness policy; [compose.yml](compose.yml)
defines its two services. Common release and bundle code has no app-name branches.
The gateway section describes only this app's route networks and trusted peers.
Infrastructure's `nginx/check_host.py` owns full-host topology checks, including
other apps' networks. `workflow.extra_env` adds only app-specific Actions inputs;
all frontend builds use `VITE_API_BASE_URL=` for same-origin API requests.
Infrastructure owns `app-release/v1`, its manifest, tests and workflow template.
`shared_source` in `app.json` pins that source to immutable commit
`07420531a79f14cb1ba3914c2865e5d4847d1bf4` across all three consumers. CI verifies
the common files and generated workflow, failing on drift or unavailable source.
Change the Infrastructure source, regenerate its manifest, then synchronize all
consumers; never edit only a vendored common file. See the
[release standard](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/blob/07420531a79f14cb1ba3914c2865e5d4847d1bf4/app-release/README.md)
for the parity matrix and coordinated update procedure.

Required Actions access variables: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH`,
`DEPLOY_HOST_FINGERPRINT` (independently verified SSH host key fingerprint).
Optional `DEPLOY_PORT` defaults to 22. Required access secret: `DEPLOY_SSH_KEY`.
Required app secrets: `DJANGO_SECRET_KEY`, `DJANGO_EMAIL_HOST_KEY`.
Required app variables: `DJANGO_EMAIL_BACKEND`, `DJANGO_DEFAULT_FROM_EMAIL`.
Use `anymail.backends.resend.EmailBackend` or
`django.core.mail.backends.smtp.EmailBackend`. The builder normalizes known
legacy Resend class paths to the current Anymail backend for new bundles only.
Optional mail settings: `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`,
`DJANGO_EMAIL_USE_TLS`, `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_TIMEOUT`.
Defaults are `smtp.resend.com`, port 587, TLS enabled, user `resend`, timeout 10
seconds. Host/port/TLS/user settings apply to SMTP; the timeout also bounds
Resend API calls.

The bundle builder applies required, default and fixed settings from `app.json`;
incompatible explicit overrides of fixed production settings fail. Debug is off,
hosts/origins are explicit and the database target is `/backend/db.sqlite3`.
The frontend build uses blank `VITE_API_BASE_URL` for same-origin requests.
Both apps and the template use domain-root routes, without a configurable Django
path prefix: frontend `/`, authentication `/auth/`, admin `/admin/`, APIs `/api/`.
Environment values use single-line raw env files, preserving literal dollar
signs, hashes and quotes. Keep credentials out of Git, public artifacts, Vite
variables and logs. Release bundles and captured recovery evidence stay private.

MacroMapper domain: `macromapper.judeandrewalaba.com`; Compose service, container
and image names: `macromapper-backend` / `macromapper-frontend`. Both services
join `macromapper-ingress` and `macromapper_default`; the exact trusted gateway
peer is `172.20.0.3`. Notoli's separate networks and trusted peer remain under
Infrastructure's host topology checks rather than this app's release policy.

Required additional Actions app secret: `MACROMAPPER_OPENAI_API_KEY`.
Optional `OPENAI_MEAL_ESTIMATION_MODEL` and `OPENAI_MEAL_ESTIMATION_TIMEOUT`
default to `gpt-5.6-luna` and a 110-second total AI budget in app policy. The timeout must
be greater than zero and at most 110 seconds; it covers sequential provider calls,
with SDK retries disabled. The production Docker image selects one Uvicorn ASGI worker when MCP is enabled;
its disabled branch uses one Gunicorn worker with four request threads and a
120-second liveness timeout. Local development Compose uses Uvicorn reload.
These server choices preserve the same application AI budget. At most two SDK calls run at once;
timed-out calls retain their slots until they finish, and excess AI requests
return a safe JSON 503. See [backend behavior](../../backend/README.md).

The Infrastructure MacroMapper backend vhost must have `proxy_read_timeout 120s`
to avoid its former 60-second default terminating estimates. This gateway change
belongs to the separately authorized Infrastructure release; deploy it before
the app change. The local frontend/standalone proxies use the same 120-second
API read limit. The 110-second AI budget leaves response headroom within the gateway limit.
Confirm the zone's effective [Cloudflare proxy read timeout](https://developers.cloudflare.com/fundamentals/reference/connection-limits/)
during rollout. Verify a delayed estimate
and an ordinary authenticated API read concurrently, then a controlled timeout
returning JSON 503 without a worker restart or late proposal write.

<a id="-boundary-and-activation-order"></a>

<a id="-ci-inputs-and-private-host-preparation"></a>

<a id="boundary-and-activation-order"></a>

<a id="ci-inputs-and-private-host-preparation"></a>

## 🧱 Host preparation and activation

Infrastructure owns shared Nginx, TLS certificates, ports 80/443, route-network
lifecycle and host capacity. Application releases own only their backend,
frontend, database, immutable images and private release/recovery records.
The gateway must already own ingress and pass its cutover acceptance before
activation. App Compose references existing networks externally. The controller
rejects unexpected route-network members, required app/gateway absence,
app-policy trust/address drift and DB-mount drift. A missing companion app is
allowed so its outage does not prevent this app's release or recovery; gateway
cutover acceptance still requires both apps.

Releases never create/delete networks, publish a backend port, upload TLS/vhosts,
reload the gateway, run whole-project `down`/`remove-orphans` or prune host images.
Local `deploy/compose.yml` and `deploy/nginx.conf` are local/legacy
inputs, never production release inputs. The retired shared-proxy deployment
must not be restored. Preserve installed legacy evidence until the separately
approved transfer/recovery is verified.

The recorded gateway-transfer sequence is Infrastructure cutover, Notoli release
and independent repeat verification, then MacroMapper release and repeat
verification. Check current acceptance evidence before using that migration
plan; this guide does not establish live completion. Shared decisions and host
provisioning belong to
[Infrastructure #4](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/issues/4).

The release controller verifies running frontend bindings against the accepted
app policy, then checks rendered Compose and Docker against the candidate policy.
Change both Compose and app.json when changing a publication. The current
candidate policies publish no frontend or backend host ports.

MacroMapper no longer supplies a Notoli override or shared vhost. Its frontend
and backend use the shared HTTPS gateway without host port publication.

### Private host preparation

The approved operator provisions the app root and its `incoming`, `releases`
and `recovery` children before activation, owned by the deployment identity with
mode 0700. `/opt/apps/macromapper` is the app root in policy; the existing nonempty, valid SQLite file
must remain at `db.sqlite3`. Staging and releases must share the app filesystem.
The release engine performs no first-install or empty-database bootstrap and
never silently creates or truncates the database.

The host needs working GHCR pull credentials, Docker Engine/Compose with raw
env-file support (the recorded audit used Compose 2.40.3), Python 3 and POSIX
flock support. CI installs no host packages. Shared maintenance and per-app lock
files live outside replaceable releases under `/var/lib/jude-deploy-locks`.
Provision that directory privately and existing regular mode-0600
`maintenance.lock` and `macromapper.lock` files with reviewed ownership. Existing
Notoli and MacroMapper releases also retain their respective app locks. Locks
must be protected stable inodes; never replace them, and reject symlinks.

Existing production paths require operator-reviewed access; do not infer that
a non-root uploader works or change database/key ownership blindly. Review
permission changes in the production plan. Initially serialize different-app
releases operationally until peak/concurrent capacity is verified.

<a id="-shared-mcp-framework"></a>

## 🔌 MCP integration

Enabled-app readiness requires `application/json` discovery responses with the
exact app-origin issuer and `/mcp` resource, plus MCP status 401 containing
`resource_metadata="https://macromapper.judeandrewalaba.com/.well-known/oauth-protected-resource/mcp"`
in `WWW-Authenticate`. These are bounded unauthenticated release probes;
authenticated consent and product actions remain separate acceptance work.

The app policy fixes `DJANGO_MCP_ENABLED=1`; frontend Docker builds default
`VITE_MCP_ENABLED=1`. Local examples default MCP off. Changing the reviewed
production profile requires its matching readiness policy. Registration, owner
consent and plugin installation are separately authorized actions, never release
probes.

MacroMapper uses the unchanged [canonical framework](../../backend/apps/mcp/README.md#framework)
and its own [domain/OAuth contract](../../backend/apps/mcp/README.md#application-tools). Its fixed production
settings enable MCP at the app origin and trust only gateway peer `172.20.0.3`.
The release checks that exact gateway address while preserving all existing
networks and Notoli's `.2` trust. The frontend Docker build enables connection
routes without extending the shared release workflow. No new credential or
shared authorization service is required. OAuth and app confirmation migrations
run only after the normal private SQLite capture and integrity checks.

<a id="-first-enable-recovery"></a>

### First-enable recovery

Before the first enabled promotion, record the previous accepted disabled release directory and
verify its private `manifest.json`, `app.json`, controller and cached images.
`backend_required_env` stays empty for this transition because preflight inspects
the OLD backend, which has no new MCP trust setting. The NEW bundle fixes that
setting to `172.20.0.3`; verify it and the MCP flag in final runtime acceptance.
Do not alter the shared controller or retained immutable bundles to pass checks.

If the first enabled release fails, use the normal rollback command above with
the failed candidate's recovery ID. Automatic selection runs the verified saved
disabled controller and its ordinary readiness, so restored disabled images do
not have to satisfy the enabled candidate's MCP metadata checks.

Resolve the ID from verified private records. With older retained tools that
predate automatic selection, invoke the verified previous disabled controller
explicitly using that same failed recovery ID. Keep
`--keep-database` only for the documented pre-migration safe stages; after
migration, explicit database restore can discard later writes and needs the
appropriate recovery authorization. Capture the current writer/journals before
restoring; never reverse OAuth migrations manually. Shared gateway routing can
remain pointed at the disabled app (no connector is advertised by that backend).
Client registrations, grants and plugin installation are separate from deployment.
Ordinary Notoli, Notoli MCP and MacroMapper REST/frontend checks remain acceptance
requirements.

## 🛠️ Application maintenance

<a id="-estimation-credential-rotation"></a>

### Estimation credential rotation

The Actions repository secret `MACROMAPPER_OPENAI_API_KEY` must contain only
`Prod · Application · AI Estimate` from the `MacroMapper Production` OpenAI
project. The deployment job has no GitHub environment binding. Updating the
secret takes effect in a new private release bundle during the separately
authorized app release; it does not change the running container. Keep the old
key valid for rollback until all consumers and retained recovery bundles are
accounted for. See the [migration and validation steps](../../.github/README.md#application-credentials).

<a id="-catalog-maintenance"></a>

### Catalog maintenance

The repository no longer includes catalog audit or consolidation management
commands. Catalog corrections require a separately reviewed operational procedure
with explicit food IDs, SQLite capture/recovery and source evidence. Preserve
immutable versions, evidence, component references, diary snapshots and proposal
history; do not infer missing nutrition or replace nulls with zero.

Retain prior images, private environment/configuration, recovery sets and stopped
management containers until the host operator reviews disk use and explicitly
selects unused app resources. Never use host-wide Docker pruning.

<a id="-validation-and-remaining-acceptance"></a>

<a id="validation-and-remaining-acceptance"></a>

## 🧪 Checks

Run from the repository root:

```powershell
python deploy/production/build_bundle.py --check-parity
python -m unittest discover -s deploy/tests -v
```

Parity checks the immutable Infrastructure pin, common runtime/tests and generated
workflow. For local source development only, add
`--source-root <infrastructure-checkout>` to `--check-parity` to verify local
common hashes offline; that does not verify the remote pin. Use `--sync` only
after reviewing a coordinated source/pin update across all three consumers.
Synchronization replaces only the verified common files and rendered workflow;
other local files remain untouched. A linked `deploy/` directory is rejected
before writes.
CI always checks the immutable pin.

The full release suite needs Linux and a disposable local/CI Docker daemon,
never production. Windows skips POSIX transaction tests. Fixtures use synthetic
credentials and derive additional required backend values from `app.json`;
production bundling still requires explicit credentials.

Tests use synthetic credentials, real Compose/container env parsing, real SQLite
backup/restore, and Linux locks with injected migration/backup/readiness failures.
Real Docker recovery rehearsals recreate captured image IDs, commands, raw
environment and DB binds without changing another container; stop a real writer
after a short CLI timeout and a simulated interrupted invocation; and recover a
committed WAL-only row after an unclean exit with the actual single-file bind.
A real recovery retry then replaces the host inode, fails before new startup,
removes the canonical backend, fails during a temporary-name replacement, and
retries successfully without replaying a retired journal or touching a companion.
Infrastructure's root routing and proxy-reversal suites were retired;
current repository checks do not establish gateway runtime acceptance.

## Transaction details

<a id="transaction-and-failure-states"></a>

<a id="-transaction-and-failure-states"></a>

### Transaction and data capture

`release.py deploy` acquires shared maintenance then exclusive app lock,
rejecting conflicts rather than waiting indefinitely. The host operator uses
the maintenance lock exclusively for cutover. Initially serialize different-app
releases operationally until peak/concurrent capacity is verified.

Before stopping writers the script checks the payload manifest, immutable app
image identities, topology, fixed trust, existing DB bind, 512 MiB available
memory and 20% disk headroom after allowance for recovery copies. These floors
do not certify representative peak capacity. It resolves/pulls images, captures
private runtime state and produces an **app-only recovery Compose model** pinned
to cached previous image IDs. Original legacy files are retained as private
evidence; they are never executed as rollback scripts.

The backend and any surviving app-labelled management containers stop before
SQLite backup. Private `data-state.json` records the exact writer ID or a unique
generation label plus a checksummed complete checkpoint. Capture never guesses by container
start time. It discovers all backend/management writers by labels, including
temporary Compose names, stops them, and copies the selected generation's
DB plus WAL/rollback journal from the stopped container into a private isolated
directory, and recovers that copy. This matters because only the main DB file is
bind-mounted; sidecars can be in the container filesystem. A backup and isolated
restore copy must both pass integrity checks before production checks/migrations. SQLite
copy/restore operations have a 60-second progress deadline. Management
containers carry app/release identity labels and unique names. They are stopped
and verified after Docker CLI timeout; rollback quiesces surviving labelled
containers too. Stopped containers are retained because their journals can be
recovery evidence. Cleanup needs explicit operator review, like image retention.
Management containers join only the app's backend egress network; they do not
contend with reserved backend addresses. Before migration and again before app
startup, verified data is consolidated into the main host DB with its original owner/mode. Before an inode swap, the
complete checkpoint and consumed writer IDs are persisted; their old journals
are retired from future selection. A missing/unstarted replacement uses that
checkpoint, while a started temporary-name container is captured by its generation.
Unknown or multiple current writers fail closed. Copies use DELETE journal
mode; this does not enable WAL or relocate storage. Migration/startup use the
selected digest, no pull at startup.

Readiness includes direct Django `/api/notifications/` returning 401, HTTPS HTML
root returning 200 and public JSON API returning 401. Enabled app policies add
issuer/resource discovery and an unauthenticated MCP challenge; see
[MCP integration](#-mcp-integration) for each app's exact contract. Public probes
use `JudeAppRelease/1.0` and request uncached responses; Cloudflare protections
and policy response checks remain enabled. Attempts use a 90-second retry window
plus at most one in-flight round of bounded requests. Docker exec times out at
10 seconds and HTTP at 5 seconds; ordinary Docker commands default to 300 seconds
with shorter explicit stop/management limits. These readiness checks do not
establish full functional or operator acceptance.

## 🔎 Independent production verification

Use this checklist for each application. Record source revision, deployed image
identity, observation time and result. A local production-settings check verifies
the selected settings; it cannot establish the settings of a running container.

1. In the accepted backend container, run `python manage.py check --deploy`.
   Record check IDs and assess each warning. Verify DEBUG is false, the allowed
   hosts are explicit, and session and CSRF cookies use Secure. Run the ordinary
   and enabled MCP profiles independently when both are supported.
2. Confirm HTTP redirects to HTTPS at the real edge. Review the accepted HSTS
   policy with the domain owner before enabling it. W004 requires that decision;
   W008 may be satisfied by an independently verified gateway redirect.
   For ASGI, verify that only the application's exact trusted proxy can supply
   forwarded scheme/client information.
3. With a nonprivileged test session, inspect auth, protected API and admin
   responses, including redirects and errors, through the public CDN and origin
   gateway. Record status, Cache-Control, Age and cache-hit headers. Check that
   personalized responses cannot be served from cache. Exercise a SPA deep link
   and an unknown API path. Retain only sanitized summaries.
4. List GitHub secret and variable **names** with `gh secret list` and
   `gh variable list`. Reconcile them with the application deploy workflow and
   runbook. Verify actual host key/env/TLS ownership and permissions through an
   authorized read-only host session. Record modes and identities, never values.
5. Inventory signup, login and reset abuse controls. Record any missing rate
   limits explicitly. AI request timeouts and concurrency limits do not establish
   per-user quotas. Track MacroMapper quota and credential rollout through
   [#298](https://github.com/VanillaIceCube/FullStackTemplate/issues/298) and
   [MacroMapper #289](https://github.com/VanillaIceCube/MacroMapper/issues/289).
6. Cite existing sender/domain and reset return-URL evidence. Inbox/Spam delivery
   requires an actual receipt. Reuse historical evidence with its original date.
   New mail and paid AI requests require authorization for those operations.
   Review provenance and unmatched-food behavior in MacroMapper's existing
   tests and acceptance records.
7. Mark each capability passed, failed or blocked, with the evidence type.
   Link independent app receipts. Keep the parent open while required runtime
   checks remain unverified.

After an authorized release, compare the gateway and companion app's container
IDs, start times, images and network IDs before/after; verify both sites and a
repeat app release. Full sign-in, password-reset delivery, catalog/meal/user isolation and explicitly approved AI calls,
persistence, reboot, off-host restores, monitoring and resource evidence remain
operator acceptance work. Keep implementation issues open until the required
evidence exists. Local tests and source review cannot establish current
production status.

## 📚 Reference

- [Local Docker and deployment guide](../README.md)
- [Backend configuration and behavior](../../backend/README.md)
- [Frontend build and routing](../../frontend/README.md)
- [MCP framework and app contract](../../backend/apps/mcp/README.md#framework)
- [GitHub setup and release policy](../../.github/README.md)
- [Workflow guide](../../.github/workflows/README.md)
- [App policy](app.json), [Compose](compose.yml), [bundle builder](build_bundle.py),
  [release controller](release.py) and [deployment workflow](../../.github/workflows/ci-deploy.yml)
- [Infrastructure release standard](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/blob/07420531a79f14cb1ba3914c2865e5d4847d1bf4/app-release/README.md)
