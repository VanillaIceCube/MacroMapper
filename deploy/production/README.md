# App-only production release and recovery

This is the implementation of approved architecture v2. Every PR merge and
every production release still requires separate explicit owner authorization.
Only the operator designated in coordination #4 may perform production actions
under its separately approved plan. For the coordinated ingress migration, the
owner designated Agent 3 as the sole production operator; source approval does
not authorize any agent to operate the host. Shared decisions:
[Infrastructure #4](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/issues/4).

## Shared implementation and app configuration

Both apps use [release contract v1](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/blob/b56d8a9f88088122555e275549afa8b86fc10be5/docs/app-release-standard.md).
`app.json` contains this app's service/container/domain/environment/network/DB
and readiness policy; `compose.yml` defines its services. Common release and
bundle code has no application-name branches. `deploy/shared-source.json` pins
the versioned source; CI verifies exact common code/test copies and the generated
workflow, failing on drift or unavailable source. The parity matrix and update
procedure live in the standard. Run `python deploy/check_parity.py` locally;
use `--sync` only after reviewing a coordinated pin update in both applications.

Public readiness requests use the honest `JudeAppRelease/1.0` User-Agent and
request uncached responses. Cloudflare protections and all expected status,
content and authentication-challenge checks remain enabled.

The staged bundle includes `app.json` in its private checksum manifest. Release
and rollback never download code or depend on an Infrastructure checkout.
One transaction file keeps failure ordering and crash barriers reviewable;
application policy and declarative readiness are separated from that state machine.

## Boundary and activation order

The infrastructure gateway must already own ingress and pass its cutover
acceptance before this pipeline is activated. Production Compose contains only
this app's frontend/backend. All existing networks are referenced externally;
the script rejects unexpected route-network members, current-app/gateway absence,
exact proxy-trust drift and DB-mount drift. A missing companion app is allowed
so its outage does not prevent this app from being released or recovered. Both
apps must still pass the gateway cutover acceptance before activation. It never
creates/deletes networks, publishes a backend port, uploads TLS/vhosts, reloads
Nginx, runs a whole-project down/remove-orphans, or prunes host images.

The owner-approved sequence is gateway transfer, Notoli release and independent
repeat verification, then MacroMapper release and repeat verification.
MacroMapper no longer supplies a Notoli override or shared vhost. The retired
bridge remains in Git history; preserve installed live copies until approved
transfer/recovery is verified.

The retired `scripts/deploy-production.sh` and
`scripts/prepare-production-bundle.py` remain fail-closed compatibility stubs.
No workflow on this implementation branch invokes them. Legacy `env-prod`
workflow history still invokes the bundle builder and deployment script;
external automation or operator commands may also do so. Remove them only after the
host operator inventories those callers, disables or migrates every legacy
caller, verifies the new release and recovery path, and confirms retained
rollback procedures do not invoke them. Record that evidence in the deployment
issue before removal; never restore the old shared-proxy behavior.

## CI inputs and private host preparation

The workflow runs only on reviewed `env-prod` pushes or a manually authorized
dispatch selecting that branch. Pushing `main` or this feature branch does not
deploy. CI builds full SHA tags, then selects the build's **immutable digests**
for every pull/migration/startup; no `latest` selector is used.

Required access variables: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH`,
`DEPLOY_HOST_FINGERPRINT` (independently verified SSH host key fingerprint);
optional `DEPLOY_PORT` defaults to 22. Secret: `DEPLOY_SSH_KEY`.
The host must have working GHCR pull credentials, Docker Engine/Compose with
raw env-file support (audited Compose 2.40.3), Python 3 and util-linux flock
semantics through Python's POSIX flock. No packages are installed on the host by CI.

Required app secrets: `DJANGO_SECRET_KEY`, `DJANGO_EMAIL_HOST_KEY`, `MACROMAPPER_OPENAI_API_KEY`.
Required variables: `DJANGO_EMAIL_BACKEND`, `DJANGO_DEFAULT_FROM_EMAIL`.
Optional SMTP settings: `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`,
`DJANGO_EMAIL_USE_TLS`, `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_TIMEOUT`.
Defaults remain Resend SMTP, port 587, TLS, user resend, timeout 10 seconds.
Optional `OPENAI_MEAL_ESTIMATION_MODEL` and `OPENAI_MEAL_ESTIMATION_TIMEOUT`
default to the existing model and a 110-second total AI budget. The timeout must
be greater than zero and at most 110 seconds; it covers sequential provider calls,
with SDK retries disabled. Gunicorn uses four request threads in one worker and
an explicit 120-second worker-liveness timeout. At most two SDK calls run at once;
timed-out calls retain their slots until they finish, and excess AI requests
return a safe JSON 503. See [backend behavior](../../backend/README.md).

The Infrastructure MacroMapper backend vhost must have `proxy_read_timeout 120s`
to avoid its former 60-second default terminating estimates. This gateway change
belongs to the separately authorized Infrastructure release; deploy it before
the app change. The local frontend/standalone proxies use the same 120-second
API read limit. The 110-second AI budget leaves response headroom within both
the gateway limit and [Cloudflare's default 125-second proxy read timeout](https://developers.cloudflare.com/fundamentals/reference/connection-limits/).
Confirm the zone's effective limit during rollout. Verify a delayed estimate
and an ordinary authenticated API read concurrently, then a controlled timeout
returning JSON 503 without a worker restart or late proposal write.
No shared release code or parity pin changes are needed for this app policy.
Canonical production host/origin/debug/DB settings are set by the app's
`build_bundle.py`; incompatible explicit overrides fail. Values are single-line
raw env files, so dollar signs, hashes and quotes retain their literal bytes.
Secrets are not uploaded as CI artifacts or printed by release commands.

The approved operator must provision these paths **before activation**, owned
by the deployment identity and mode 0700:

- App root: `/opt/apps/macromapper` (existing DB remains at `db.sqlite3`).
- Its `incoming`, `releases` and `recovery` children.
- `/var/lib/jude-deploy-locks`, with existing regular mode-0600 files
  `maintenance.lock`, `notoli.lock` and `macromapper.lock`.

The current host needs root access for the existing paths. Do not infer a
non-root uploader works or change DB/key ownership blindly. The operator
reviews any permission change in the production plan. Locks must be protected
stable inodes; never replace them, and reject symlinks. Provisioning commands
and the initial legacy-workflow hold are in the infrastructure runbook.

CI reserves a fresh `incoming/<source-sha>-<run-id>-<attempt>` directory and
uploads only its bundle. It never overwrites active files before locking.
Staging and releases must be on the same app filesystem. Unique attempts may
not be reused. No first-install/empty-DB bootstrap is performed: this migration
requires the existing nonempty SQLite bind file.

## Transaction and failure states

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
SQLite backup. Private `data-state.json` records the exact writer ID or a unique generation
label plus a checksummed complete checkpoint. Capture never guesses by container
start time. It discovers all backend/management writers by labels, including
temporary Compose names, stops them, and copies the selected generation's
DB plus WAL/rollback journal from the stopped container into a private isolated
directory, and recovers that copy. This matters because only the main DB file is
bind-mounted; sidecars can be in the container filesystem. A backup and isolated restore copy
must both pass integrity checks before production checks/migrations. SQLite
copy/restore operations have a 60-second progress deadline. Management
containers carry app/release identity labels and unique names. They are stopped
and verified after Docker CLI timeout; rollback quiesces surviving labelled
containers too. Stopped containers are retained because their journals can be
recovery evidence. Cleanup needs explicit operator review, like image retention.
These containers join only backend egress; they never contend with Notoli's reserved
backend address. Before migration and again before app startup, verified data is consolidated
into the main host DB with its original owner/mode. Before an inode swap, the
complete checkpoint and consumed writer IDs are persisted; their old journals
are retired from future selection. A missing/unstarted replacement uses that
checkpoint, while a started temporary-name container is captured by its generation.
Unknown or multiple current writers fail closed. Copies use DELETE journal
mode; this does not enable WAL or relocate storage. Migration/startup use the
selected digest, no pull at startup.
Readiness includes direct Django /api/notifications/ returning 401, HTTPS HTML
root and JSON 401 API response. Attempts are bounded by a 90-second
retry window plus at most one in-flight round of bounded requests; Docker exec
times out at 10 seconds and HTTP requests at 5 seconds. Other Docker commands
time out at 300 seconds.

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
environment and possible DB journals; treat them as private recovery evidence. Command errors intentionally withhold captured
output; diagnose privately using the saved configuration.

## Operator commands after separate authorization

CI invokes the equivalent of:

```bash
python3 "$app_root/incoming/$release_id/release.py" deploy \
  --root "$app_root" --bundle "$app_root/incoming/$release_id"
```

Set `app_root=/opt/apps/macromapper`; select the exact reviewed release/recovery ID from the
private record. Use a reviewed copy of this new release tool, never the legacy
deploy script. For an approved rollback that can lose post-snapshot writes:

```bash
python3 "$app_root/releases/$release_id/release.py" rollback \
  --root "$app_root" --recovery "$release_id" --restore-database
```

Recovery verifies cached images before stopping the backend, saves the current
DB/journals from the stopped writer too, restores the selected DB with its
original ownership/mode, and recreates **only app services**, no pull. It runs
the same readiness gates and records success only afterward. Failed rollback
stops backend writers and leaves the failure marker/recovery data intact.

If backup/check failed **before migration started**, the operator may instead
restart the captured previous app configuration with all current data (no older
snapshot selection). Current journals are consolidated before container recreation:

```bash
python3 "$app_root/releases/$release_id/release.py" rollback \
  --root "$app_root" --recovery "$release_id" --keep-database
```

That mode is rejected after the recorded migration-started stage. Its safe-data
flag persists through rollback failure, allowing a retry after transient readiness
failure without editing markers or choosing an unnecessary old snapshot. If a crash
occurred before the marker/recovery set was complete, inspect privately and use
a specifically approved recovery plan; do not fabricate a success record.
Rollback is not a substitute for off-host backups and a full functional restore
drill. Both remain deployment acceptance gates.

## Validation and remaining acceptance

Run `python -m unittest discover -s deploy/tests -v` with Docker.
Tests use synthetic credentials, real Compose/container env parsing, real SQLite
backup/restore, and Linux locks with injected migration/backup/readiness failures.
Real Docker recovery rehearsals recreate captured image IDs, commands, raw
environment and DB binds without changing another container; stop a real writer
after a short CLI timeout and a simulated interrupted invocation; and recover a
committed WAL-only row after an unclean exit with the actual single-file bind.
A real recovery retry then replaces the host inode, fails before new startup,
removes the canonical backend, fails during a temporary-name replacement, and
retries successfully without replaying a retired journal or touching a companion.
POSIX transaction tests run in Linux CI (Windows skips them); local Linux Docker
runs can exercise them independently. Shared vhost routing and proxy endpoint
reversal are tested in the infrastructure repository.

After an authorized release, compare the gateway and other app's container IDs,
start times, images and network IDs before/after; verify both sites and a repeat
app release. Full sign-in, password-reset delivery, catalog/meal/user-isolation and explicitly approved AI calls, persistence,
reboot, off-host restores, monitoring and resource evidence are operator
acceptance work, not inferred from these tests. Keep the implementation issues
open until that evidence exists.

The shared release pin includes template-policy regression coverage coordinated
with [FullStackTemplate #217](https://github.com/VanillaIceCube/FullStackTemplate/issues/217)
and [Infrastructure #26](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/pull/26).
It derives common preflight fixtures from app policy while retaining this app's
existing trust, networks, environment requirements, workflow and runtime bytes.
The same immutable source commit is proposed for all three consumers. These
source-pin PRs do not authorize merging, promotion, or deployment.

## 🔑 Estimation credential rotation

The Actions repository secret `MACROMAPPER_OPENAI_API_KEY` must contain only
`Prod · Application · AI Estimate` from the `MacroMapper Production` OpenAI
project. The deployment job has no GitHub environment binding. Updating the
secret takes effect in a new private release bundle during the separately
authorized app release; it does not change the running container. Keep the old
key valid for rollback until all consumers and retained recovery bundles are
accounted for. See the [migration and validation steps](../../.github/README-WORKFLOWS.md#-independent-estimation-credentials).


## 🔌 Shared MCP framework

Follow the [MCP framework contract](../../docs/MCP-FRAMEWORK.md) before activating an optional app. Notoli keeps its current MCP profile; MacroMapper source defaults off; its prepared central production policy enables MCP only through coordinated env-prod activation. Use this guide for immutable app releases and explicit recovery; framework adoption does not provision a new template instance.

## Central MCP production policy

The prepared `app.json` sets `DJANGO_MCP_ENABLED=1`, fixes the verified existing
`DJANGO_TRUSTED_PROXY_IPS=172.20.0.3`, requires the dedicated introspection secret
and adds exact resource/issuer JSON plus anonymous MCP 401 challenge probes.
Ordinary website/API health remains unchanged. Source defaults remain off;
this policy is released only through the owner's coordinated `env-prod` promotion
after shared OAuth/YNAB, identity/registry and ingress acceptance. Main-source
approval is not an instruction for this app agent to deploy.

`MACROMAPPER_MCP_INTROSPECTION_SECRET` is passed from its Actions repository secret
into the existing private `.backend.env` bundle via the generated app workflow.
It is required with no default. Bundle preparation and enabled production checks
reject missing credentials. The exact gateway peer is also pinned in
`gateway.addresses["macromapper-ingress"]`; backend `.2` and frontend `.4` cannot
forward trusted metadata. Keep Uvicorn `--no-proxy-headers`; only the canonical
exact-peer ASGI wrapper accepts it. No new network, address migration, secret
volume, runtime release engine or production credential change is made here.

The existing empty `backend_required_env` preflight is retained so the first
central release can start from the old disabled backend. The incoming bundle's
fixed env and gateway address checks, plus new-runtime production checks, enforce
the selected peer. The operator verifies effective backend trust after release.
For disabled recovery, `mcp-disabled-policy.json` is an explicit app-owned policy
delta: disable MCP, remove only its two probes and required introspector, retain
ordinary health and all five-network/exact-peer policy. Re-render workflow and
review/release the selected compatible image through the established app-only
path. Retain additive identity/confirmation tables; no automatic DB restore.
See [the MCP runbook](../../docs/MCP.md) for identity linking and real-client checks.

### Stage disabled-runtime recovery before first activation

Before first MCP activation, prepare and privately stage a separate rollback tool
from the exact reviewed app checkout. A failed enabled release sets `FAILED.json`,
so a new disabled **deploy** is barred; the failed enabled tool also requires MCP
health from its captured old disabled backend and cannot complete that rollback.
Prepare the matching disabled-policy rollback tool **before** exposing this risk:

```bash
python3 deploy/production/prepare_mcp_recovery.py \
  --source-revision '<approved-full-app-source-sha>' \
  --target '<fresh-local-staging-directory>'
```

The output is the byte-identical canonical `release.py`, derived disabled
`app.json`, and a manifest binding their SHA-256 checksums plus app/shared source
revisions. It contains no credentials, environment payload or database. Verify
the checkout revision and hashes independently, then have the approved operator
stage that exact directory at
`/opt/apps/macromapper/recovery-tools/mcp-disabled-<approved-source-sha>` before
activation, with directories 0700/files 0600 and deployment-owner access. Keep
these files with the retained images/recovery evidence. Never edit an immutable
failed bundle, captured env, recovery set or failure marker to change policy.

For a failed **first** enabled release, first verify privately that the selected
recovery captured `DJANGO_MCP_ENABLED=0` (or its old absent/default-off value).
The separate tool changes readiness policy; it does not rewrite captured runtime
environment. Invoke the staged disabled-policy `release.py` itself, using the
failed release's existing recovery ID and the separately selected database mode:

```bash
python3 "$app_root/recovery-tools/mcp-disabled-$approved_source_sha/release.py" rollback \
  --root "$app_root" --recovery "$failed_release_id" --restore-database
```

Database restore requires its deliberate operator authorization and can discard
post-snapshot writes. Use `--keep-database` instead only for the already-documented
pre-migration eligibility. This rollback retains the original failure barrier,
locks, writer quiescence, cached image identity, capture/backup and explicit DB
selection; successful ordinary root/API health clears the barrier normally.
It preserves the five-network/exact-peer policy and touches no shared gateway.
Do not select this tool for a capture whose backend remains MCP-enabled; use a
matching enabled recovery policy or a separately reviewed contained forward fix.
After recovering the old disabled runtime, future deploys can again proceed.
The normal disabled-profile/gateway sequence below applies to planned downgrade
to an older three-network app bundle.

The central rollout policy now expects the exact existing three gateway networks
plus `ynab_mcp_private` / ingress `172.30.89.2` and `mcp_auth_private` / ingress
`172.30.92.2`; Notoli remains `172.30.88.2`. The two companion services are allowed
but only ingress is required, preserving independent app recovery. This does not
attach MacroMapper to another network. The gateway rollout must establish this
five-network baseline before an app release with this policy.

Legacy matched three-network rollback requires an explicit bounded sequence:
release MacroMapper's disabled profile with ordinary health under the five-network
baseline, have the gateway owner select **both** explicit disabled route profiles
and verify hostname tombstones plus the three-network baseline, then use the
matched legacy app bundle. Never use implicit `base`, edit old private manifests,
drop exposed hostnames, or weaken exact topology checks. See [MCP rollback](../../docs/MCP.md#health-outage-and-rollback).
