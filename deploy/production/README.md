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

### 🌿 Main-first source and intentional release lag

Land reviewed source on `main`, then promote only an authorized, deployable
revision to `env-prod` through the normal review and CI gates. These are source
requirements from the [shared main-first policy](https://github.com/VanillaIceCube/FullStackTemplate/blob/main/docs/SHARED-ROLLOUT-POLICY.md#main-first-releases):
the promotion's entire source tree must match its exact reviewed main commit.
These are source
and operator rules; the workflow's branch check does not enforce main ancestry.
If the owner explicitly authorizes an exceptional production-branch fix, review it and reconcile its
history and changes back into `main` before the next promotion. Preserve merge
history; do not reset or force-push either branch to manufacture parity.

Production may deliberately remain on an earlier reviewed release. MacroMapper's
current policy enables its own MCP/OAuth under #284; the retired shared issuer
remains removed. The application owns user permissions, confirmation and client
setup; Infrastructure owns ordinary Nginx routing only. See [the MCP contract](../../docs/MCP.md).
Branch reconciliation does not authorize a deployment, require matching production
trees or authorize unrelated newer main changes for production.

The [#329 audit](https://github.com/VanillaIceCube/MacroMapper/issues/329) on
2026-10-30 compared `main` at `fe8820bf2a390354fe3b2d5e046f6212ee7bd502`
with `env-prod` at `fc5ff4245fd0e241839f1f58df317f1a16aacf5d`. The five commits
unique to production were merges, and its full tree exactly matched main
ancestor `52e9e845bddc58ab173a69584242c24c7af56840`. Reconcile that ancestry
without reverting newer main source or deploying unrelated changes. The later
central-MCP withdrawal preserves this history and does not require a MacroMapper
production deployment: that enabled policy was never released.

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
with SDK retries disabled. Disabled local profiles use Gunicorn with four request threads in one worker and
an explicit 120-second worker-liveness timeout. The enabled production profile
uses one Uvicorn ASGI worker, preserving the same application AI budget. At most two SDK calls run at once;
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
root, JSON 401 API response, exact app-owned issuer/resource metadata JSON and
an unauthenticated MCP 401 with the exact resource-metadata challenge. Attempts are bounded by a 90-second
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

MacroMapper uses the unchanged [canonical framework](../../docs/MCP-FRAMEWORK.md)
and its own [domain/OAuth contract](../../docs/MCP.md). Its fixed production
settings enable MCP at the app origin and trust only gateway peer `172.20.0.3`.
The release checks that exact gateway address while preserving all existing
networks and Notoli's `.2` trust. The frontend Docker build enables connection
routes without extending the shared release workflow. No new credential or
shared authorization service is required. OAuth and app confirmation migrations
run only after the normal private SQLite capture and integrity checks.

### 🛟 First-enable recovery

Before promotion, record the previous accepted disabled release directory and
verify its private `manifest.json`, `app.json`, controller and cached images.
`backend_required_env` stays empty for this transition because preflight inspects
the OLD backend, which has no new MCP trust setting. The NEW bundle fixes that
setting to `172.20.0.3`; verify it and the MCP flag in final runtime acceptance.
Do not alter the shared controller or retained immutable bundles to pass checks.

If the first enabled release fails, invoke the retained previous disabled
controller with the failed candidate's recovery ID, for example:

```bash
python3 "$previous_disabled_release/release.py" rollback \
  --root "$app_root" --recovery "$failed_release_id" --restore-database
```

Resolve these paths/IDs from verified private records, not this example. The old
controller uses its own ordinary readiness, so restored disabled images can pass.
The enabled candidate controller would demand unavailable MCP metadata. Keep
`--keep-database` only for the documented pre-migration safe stages; after
migration, explicit database restore can discard later writes and needs the
appropriate recovery authorization. Capture the current writer/journals before
restoring; never reverse OAuth migrations manually. Shared gateway routing can
remain pointed at the disabled app (no connector is advertised by that backend).
Client registrations, grants and plugin installation are separate from deployment.
Ordinary Notoli, Notoli MCP and MacroMapper REST/frontend checks remain acceptance
requirements.
