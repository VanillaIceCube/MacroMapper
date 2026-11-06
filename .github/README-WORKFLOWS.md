# 🤖 MacroMapper GitHub Automation
MacroMapper's CI/CD and security automation validates the application,
publishes its images, deploys production, reviews pull requests, and keeps
security work synchronized with the MacroMapper Project.

Production bundles default `OPENAI_MEAL_ESTIMATION_TIMEOUT` to 110 seconds for
the entire AI operation, with retries disabled. An optional repository variable
can shorten this budget (greater than zero, at most 110). The two-minute
Infrastructure API proxy change must be released before the app image change;
passing CI does not authorize either production operation.

## Major-upgrade review evidence

Obi-Wan uses Dependabot's per-dependency metadata for grouped upgrades.
Release lookups use each major update's own ecosystem and target version.
Repository usage searches cover every listed dependency and retain the
tracked-file exclusions and 30,000-byte limit. Numeric Actions references
such as 7 and v7 can match a full release tag such as v7.0.0. Opaque refs
leave a visible evidence gap. Required briefs need at least one valid HTTP(S)
source URL. The publisher keeps independent body findings when it suppresses
duplicate inline comments or sees an unchanged verdict.

## ⚙️ Repository Settings Baseline
The live MacroMapper repository uses least-privilege settings: auto-merge is
enabled; merge commits, squash
merges, and rebases are allowed; Actions allow all actions with a read-only
default workflow permission; and GitHub Actions cannot create or approve pull
requests by default. Fork pull requests require approval from first-time
contributors. Workflows request write permissions explicitly when required.

Code security uses the repository's enabled Dependabot alerts/security updates,
secret scanning, and push protection controls. CodeQL default setup remains
unconfigured because the pinned CodeQL workflows in this repository provide the
scanner. The `dependencies`, `codeql`, `vulnerability`, `malware`, and `codex`
labels are used by the alert and operational automation. If repository settings
are recovered or rebuilt, restore these settings, labels, and the
`SECURITY_ALERTS_TOKEN` secret; see
[`GITHUB_SETUP.md`](GITHUB_SETUP.md).

## ✅ Pull-Request CI
`.github/workflows/ci-orchestrator.yml` coordinates:

- Frontend Prettier and ESLint checks
- Backend Ruff checks and formatting
- React/Vitest tests and the Vite production build
- Django tests
- Node tests for repository automation
- Deployment configuration, SQLite recovery, and disposable Nginx routing tests
- CodeQL for Python, JavaScript/TypeScript, and GitHub Actions
- GitHub dependency review at high/critical severity, with detailed findings retained in the check logs and annotations
- npm malware advisory review for changed lockfile packages, including initial lockfile additions against an empty dependency baseline and batched `package@version` advisory queries
- AI code, build, and security reviews for trusted same-repository pull requests
- Dependabot auto-merge after independent gates and all three reviewers pass

For a Dependabot semver-major update, Obi-Wan also publishes a structured
**Major upgrade brief**. It uses Dependabot's exact package/version metadata,
the target release and first release of the new major line retrieved from
GitHub Releases where available, package-registry metadata for npm and PyPI
packages to locate those release notes, the supplied Dependabot pull-request
description, primary-source web search, the repository diff, and a bounded
exact-match search of tracked repository text with lockfiles excluded. Web
search is enabled only for semver-major code reviews. The brief must explain
the dependency, a cohesive upstream story covering why the update appeared,
why it required a major release, and what the repository gains, followed by a
repository-impact paragraph, a recommendation, and primary sources.
Incomplete briefs fail visibly instead of being published. The verdict and
recommendation retain Obi-Wan's calm mentor character without weakening the
technical explanation.
The brief is advisory: it does not add a required status check or replace the
existing lint, test, CodeQL, vulnerability, malware, or reviewer gates.

Path detection prevents unrelated application suites from running. A detector failure is treated as a CI failure instead of silently skipping checks.

RoboCop consumes the CodeQL scope detector's explicit language outputs and
normalizes them against successful analyzer checks and CodeQL analyses on the
default branch. A neutral GitHub summary saying that a default-branch language
configuration was omitted from a pull-request analysis is informational when
that language was intentionally out of scope and its default-branch baseline
exists. It does not block RoboCop approval when the scope and aggregate CodeQL
gates succeeded. Scope-detection failures, aggregate failures, required
analyzer failures, baseline-query failures, and genuinely absent baselines
remain visible evidence gaps.

The policy is implemented by `.github/actions/collect-codeql-evidence` and the
corresponding `gate-codeql.yml`, `ci-orchestrator.yml`, `review-security.yml`,
and `gate-test.yml` workflows.

## 🤖 AI Review Apps
Three GitHub Apps provide separate review identities:

- Obi-Wan Code-nobi: code review
- Lint Eastwood: build review and lint auto-fix commits
- RoboCop: security review and security-alert issue management

Required repository variables:

- `OPENAI_REVIEWERS_PROJECT_ID`
- `OBI_WAN_CODE_NOBI_APP_ID`
- `LINT_EASTWOOD_APP_ID`
- `ROBOCOP_APP_ID`

Required repository secrets:

- `OBI_WAN_OPENAI_API_KEY`, `LINT_EASTWOOD_OPENAI_API_KEY`, and `ROBOCOP_OPENAI_API_KEY`
- `OBI_WAN_CODE_NOBI_PRIVATE_KEY`
- `LINT_EASTWOOD_PRIVATE_KEY`
- `ROBOCOP_PRIVATE_KEY`

Install the Apps on the MacroMapper repository with the permissions in
[`GITHUB_SETUP.md`](GITHUB_SETUP.md). Store the same six review
secrets in both the Actions and Dependabot secret stores. Dependabot workflows
receive only Dependabot secrets, so this duplication lets their pull requests
run the required reviewers. Fork pull requests never receive either store's
secrets and cannot satisfy the required reviewer child checks.

## 🛡️ Security-Alert Aggregation
The daily/manual `alert-codeql.yml`, `alert-vulnerability.yml`, and `alert-malware.yml` workflows group open alerts into managed MacroMapper issues and synchronize them with the MacroMapper Project.

Additional configuration:

- Repository variable `SECURITY_ALERTS_PROJECT_ID` set to the MacroMapper
  Project v2 node ID
- Repository secret `SECURITY_ALERTS_TOKEN` with personal Project v2 access
- RoboCop installed with `Issues: write`, `Code scanning alerts: read`, and `Dependabot alerts: read`

RoboCop's short-lived App token reads alerts and performs issue mutations. `SECURITY_ALERTS_TOKEN` is used only for personal Project v2 reads/writes. The action intentionally rejects missing or reused credentials.

The Project must contain:

- `Status`: `Backlog`, `Ready`, `In Progress`, `In Review`, `Done`
- `Domain`: including `CI/CD`
- `Type`: including `Security`
- `Priority`: `P0` through `P3`
- `Size`: `XS` through `XL`
- Numeric `Estimate`
- `Start date` and `End date`

Create or recover the board with the manual GitHub CLI and UI steps in
[`GITHUB_SETUP.md`](GITHUB_SETUP.md). Link it to MacroMapper,
verify its fields and views, and set `SECURITY_ALERTS_PROJECT_ID`. GitHub
excludes auto-add workflows from Project copies, so configure the required
auto-add workflows for the target repository in the GitHub UI.

## 🚀 Deployment
The automation test gate verifies pinned shared-source parity before the common
deployment tests; deployment builds also verify the standard before publishing.
The production workflow runs on `env-prod` pushes or a manual dispatch selecting
that branch. It serializes runs with `cancel-in-progress: false` and pins every
external action, including checkout, to an immutable commit SHA. Merging `main`
does not activate it; production activation requires separate owner approval.

See the [canonical production guide](../deploy/production/README.md) for required
variables/secrets, host preparation, activation order, release behavior and recovery.

## 📦 Dependabot
`.github/dependabot.yml` checks npm, pip, GitHub Actions, and Docker dependencies
under `/backend` and `/frontend` daily. Patch and minor Dependabot updates can
auto-merge only after the lint, test, CodeQL, vulnerability, and malware gates
succeed.

The main-branch ruleset includes the orchestrator-level `Auto Merge` context
among its required checks. CI emits that top-level context
for every pull request: it reports not-applicable for ordinary contributors and
records the independent-gate result for Dependabot. A separate Dependabot-only
default-branch follow-up enables native auto-merge after successful CI; its
separate check must not become a CI prerequisite. Dependabot pull
requests remain pending while GitHub reports an unstable merge state and are
never merged directly. Third-party Actions are pinned to
immutable commit SHAs, with release-version comments retained for maintenance.
Credential-handling GitHub Actions are pinned the same way. When a complete
pull-request diff exceeds an AI reviewer's configured budget, that reviewer's
GitHub App posts an explicit incomplete-review comment under its own identity
and then fails the check without publishing a verdict.
All three reviewers inherit the same 512 KiB source-diff budget from
`.github/actions/get-pr-diff/action.yml`; reviewer workflows do not override it.
Raw generated dependency lockfile payloads are omitted from AI prompts because
the dependency and malware gates review those files directly. Reviewers still
receive the manifests, changed-file metadata, check results, and scanner evidence.
OpenAI review requests also cap combined reasoning and visible output at 16,000
tokens so they do not reserve the model's full output allowance against project
rate limits.

The shared AI review publisher keeps each native review verdict aligned with
its required Actions check. `APPROVE` and non-blocking `COMMENT` verdicts leave
the check successful. A successfully published `REQUEST_CHANGES` verdict,
including an unchanged repeat of an earlier blocking verdict, fails the
reviewer's required check so the branch ruleset prevents merging. A later
approval on a new head commit can restore a passing reviewer check.

## 🔒 Main Branch Protection
The active `main` ruleset requires pull requests, resolved review threads, the
lint/test/CodeQL scope and analyzer/dependency checks, the Automation Tests
check, all three AI reviewer child checks, and `Auto Merge`. The reviewers run
for trusted same-repository pull requests, including Dependabot once its six
review secrets are configured. The ruleset blocks force pushes and branch
deletion and has no bypass actors. The standalone `CodeQL` context is
intentionally not required because the scope-aware workflow does not emit that
parent check for scope-empty pull requests. Validate exact check names after
the first CI run when creating or recovering the ruleset.

## 🧰 Local Automation Checks
```powershell
node --test .github/actions/collect-upstream-major-upgrade-evidence/collect-upstream-major-upgrade-evidence.test.js .github/actions/collect-codeql-evidence/collect-codeql-evidence.test.js .github/actions/publish-ai-review/publish-ai-review.test.js .github/actions/security-alerts/sync-security-alerts.test.js
python -m unittest discover -s deploy/tests -v

docker run --rm -v "${PWD}:/repo" --workdir /repo rhysd/actionlint:latest -color
```

AI review context includes bounded recent owner/collaborator reviews and replies to prior findings as discussion evidence. Prior bot verdicts must be rechecked against current source/scanners; the diff legend distinguishes active added/context lines from deleted old code. This does not change reviewer verdict rules or authorize merges/deployments.

External GitHub Actions use immutable commit SHAs with version comments.
Keep that convention when updating workflows or composite actions; preserve
review/scanner failure gates and do not treat action updates as deployment approval.

When updating the pinned `actions/create-github-app-token` revision, update the
security-alert workflow assertion in
`.github/actions/security-alerts/sync-security-alerts.test.js` and rerun the
repository automation tests. The current reviewed action revision is
`64ab729a6294000f5aa4a4bc0b73d1f32bc45510` (v3.3.0).

The shared release pin includes template-policy regression coverage coordinated
with [FullStackTemplate #217](https://github.com/VanillaIceCube/FullStackTemplate/issues/217)
and [Infrastructure #26](https://github.com/VanillaIceCube/JudeAndrewAlabaInfrastructure/pull/26).
It derives common preflight fixtures from app policy while retaining this app's
existing trust, networks, environment requirements, workflow and runtime bytes.
The same immutable source commit is proposed for all three consumers. These
source-pin PRs do not authorize merging, promotion, or deployment.

## 🔑 Separate OpenAI reviewer credentials

The four existing repositories already use the accepted persona-specific
credentials and reviewer projects. The following is an onboarding/operator
reference, not a pending model or credential migration. Configure these names
before activating a new installation; missing keys fail visibly and there is
no fallback to a shared `OPENAI_API_KEY`.

Use a dedicated **MacroMapper · AI Reviewers** OpenAI project (or the
repository's existing reviewer-only project). Never share credentials between
repositories. Create three distinct keys with these exact display names:

| OpenAI key display name | GitHub secret | Consumer |
| --- | --- | --- |
| `CI · Obi-Wan · Code Review` | `OBI_WAN_OPENAI_API_KEY` | Obi-Wan PR reviews |
| `CI · Lint Eastwood · Build Review` | `LINT_EASTWOOD_OPENAI_API_KEY` | Lint Eastwood PR reviews |
| `CI · RoboCop · Security Review` | `ROBOCOP_OPENAI_API_KEY` | RoboCop PR reviews and all three scheduled/manual alert feeds |

In this repository, add all three keys as **Actions repository secrets** and
also as **Dependabot repository secrets**, with identical names and values in
both stores. Keep the three existing GitHub App private-key secrets in both
stores as well (six review secrets total).

1. In OpenAI Platform, select the repository's reviewer project, open its API
   keys page, and create the three keys above. Restrict each key to the API
   permissions needed for Responses requests; retain model access and Obi-Wan's
   existing semver-major web-search capability. Choose an expiration under your
   rotation policy and record when replacement is due.
2. In GitHub **Settings → Secrets and variables → Actions → Secrets**, add the
   exact secret names in the table. Each value is the full secret key from its
   matching OpenAI entry, not its display name or key ID. Use Dependabot's
   separate secret settings too where specified above.
3. In **Actions → Variables**, set `OPENAI_REVIEWERS_PROJECT_ID` to that same OpenAI
   project's actual `proj_...` ID. All three keys and the project header must
   match. This is an OpenAI project ID; `SECURITY_ALERTS_PROJECT_ID` is a separate
   GitHub Project node ID and stays unchanged. App identity variables/private
   keys and deployment credentials also stay unchanged.
4. Run a same-repository PR smoke test for all three reviewers. Where supported,
   also verify a Dependabot PR using its separate secret store. After an
   approved merge, manually run CodeQL Alert, Vulnerability Alert, and Malware
   Alert on the default branch and observe their next scheduled runs. Do not
   run production deployment to test reviewer credentials.
5. In OpenAI Usage, filter by the reviewer project and individual API key to
   confirm each persona's attribution. An empty alert feed may make no model
   call; record that outcome rather than assuming usage was verified.
6. For configuration recovery, restore the last accepted persona-specific key/
   project bindings and validated reviewer variables, then rerun the latest head.
   Any source revert must use ordinary protected review and retain its matching
   credential contract. A legacy key used elsewhere is not an active reviewer
   fallback; never copy it into all three persona slots or expose key values.
   This reference does not rotate or provision credentials during Batch 3.

See [OpenAI key security, expiration and usage guidance](https://developers.openai.com/api/docs/guides/production-best-practices#api-keys).

## 🍽️ Independent estimation credentials

Meal estimation keeps its existing `MACROMAPPER_OPENAI_API_KEY` name. Its keys
must not come from the reviewer project or be shared between environments:

| OpenAI project | Exact key display name | Destination |
| --- | --- | --- |
| `MacroMapper Production` | `Prod · Application · AI Estimate` | Actions repository secret `MACROMAPPER_OPENAI_API_KEY` used by `ci-deploy.yml` |
| `MacroMapper Development` | `Local · Application · AI Estimate` | `MACROMAPPER_OPENAI_API_KEY` in ignored `backend/.env` (native) or `deploy/.env` (Docker) |

1. Create one independently rotatable key in each project, with model-inference
   access appropriate to the existing estimation client. Keep project usage,
   model access, and budget settings independent. Never put the production key
   on a developer machine or in Dependabot secrets.
2. At an explicitly scheduled application cutover, replace only the value of
   the Actions repository secret `MACROMAPPER_OPENAI_API_KEY` with the production
   key. The current workflow has no GitHub environment binding. Do not store
   this value in the reviewer secret slots or add a reviewer project header to
   estimation. Shared release source, policy and Compose remain unchanged.
3. The production workflow injects that secret into the private release bundle.
   Changing the GitHub secret alone does not update the running application.
   Use the approved app-only release procedure and its separately authorized
   promotion/deployment; do not edit the live container or recovery bundle.
4. Put only the local key in the ignored local env file for the setup you use;
   restart the native backend process or recreate the local Docker backend so
   it reads the new value (a plain container restart keeps the old environment).
   Preserve other env settings. `deploy/backend.env` is a tracked example, never a secret target.
5. Validate a non-catalog AI estimation locally and after the authorized
   production deployment. Check OpenAI Usage in each project and by key before
   retiring old credentials. Keep previous credentials valid for explicit release
   rollback; rollback bundles may still contain the old production key.

This source change provisions no keys and performs no estimation, deployment,
or revocation. Track live/local acceptance separately in issue #289.


## 🔌 Shared MCP framework

The backend test gate checks the pinned MCP framework manifest, runs ordinary backend tests and separately runs `mcp_framework macromapper_mcp` with MCP enabled and the application factory. Synthetic OAuth and mocked provider tests cover domain permissions without live credentials or paid requests. The shared deployment workflow stays unchanged: MacroMapper enables the connection UI through its app-owned Docker build default. See [the app MCP guide](../docs/MCP.md).

## 🛡️ Dependency evidence and alert lifecycle parity

The reusable baseline is FullStackTemplate's `.github/actions/prepare-vulnerability-report`.
MacroMapper, Notoli and Infrastructure carry the same report implementation and
regression contract. Dependency Review still blocks high/critical additions;
every non-success scanner outcome, missing/malformed output or failed evidence
preparation fails the independent Vulnerability check. No empty-array fallback
may turn unavailable evidence into a clean scan. RoboCop receives at most 16 KiB
of package/severity/manifest context, with omitted-entry counts. The
`dependency-review-evidence` artifact retains every structured entry for seven
days, excluding untrusted free text and arbitrary URLs; unavailable evidence is
retained as structured diagnostics. Artifacts have the repository's Actions
access controls, not an additional private storage boundary.

Alert synchronization saves source history/replacement links first, ensures
Project membership, then writes End date before Status Done. Done can trigger
Project auto-close. The issue client re-reads state before a separate state-only
close. Only GitHub's observed HTTP 422 `Validation Failed` with an empty errors
array is eligible for recovery, and only if another read proves closed/completed
with the exact saved lifecycle body. Other failures propagate. Partial Project
failures leave the issue open for rerun; issue mutations remain attributed to
RoboCop and Project writes use the separate Project credential. New items use
the live `Work type` field. No credentials, branch protections or deployments
change.

Historical evidence: FullStackTemplate #192 closed at 2026-10-11 16:40:51 UTC,
before run 38156425534's state-close PATCH returned 422 at 16:40:52 UTC with
`errors: []`. Notoli #825 has the same earlier pattern. All four Projects have
Auto-close issue enabled (read-only verification 2026-10-20). This establishes
the competing-close ordering; GitHub's internal validation cause is not exposed.
Mocks reproduce that interleaving and reject unrelated errors. Empty scheduled
feeds do not establish that a live close race occurred.

## 🔄 Shared deployment action update

Docker login v4.7.0 is rendered from Infrastructure commit
`f3f049830fcd5e5869d1ae120c57d9ccb6c99200`. Keep `deploy/shared-source.json` and
the generated workflow synchronized; deployment parity remains mandatory.

## 🤖 Reviewer model

Code, build and security reviewers and security-alert grouping use `gpt-6-luna` through the existing Responses API action. Per-reviewer credentials, project isolation, output budgets, triggers and failure gates are preserved. See [the model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna) and [shared tracking #241](https://github.com/VanillaIceCube/FullStackTemplate/issues/241). Application AI models and Jules schedules are independent of this setting.

## 📦 Compatible CodeQL updates

Dependabot groups all `github/codeql-action` entry points (including `init`,
`analyze`, `autobuild` and `upload-sarif`) in `codeql` version-update PRs.
A separate `codeql-security` group applies the same matching to security updates;
GitHub does not combine version and security updates in one group. Keep both
patterns (`github/codeql-action` and `github/codeql-action/*`) so repository and
entry-point dependency names match. Review every CodeQL entry point together,
keep their immutable revisions aligned, and preserve normal CI/reviewer gates.

The applications retain daily updates. Infrastructure retains weekly updates,
its owner/labels/PR limits, general Actions group for non-CodeQL updates, and
separate Compose updates. The template aligns its mutable CodeQL tag with the other repositories'
immutable v4.39.1 revision. Scanner scope, permissions and merge/deployment
gates remain unchanged. Canonical rollout:
[FullStackTemplate #271](https://github.com/VanillaIceCube/FullStackTemplate/issues/271).

## 🔒 Protected Dependabot auto-merge

FullStackTemplate (#240) owns the canonical application policy. After successful
PR CI, `ci-auto-merge.yml` runs only reviewed main code, with no PR checkout,
artifacts, caches, PAT, reviewer keys or production secrets. The API resolves the
successful CI workflow and its exact open main PR; rerun actor identity is not
used as PR authorship. Forks and non-Dependabot PRs receive a nonblocking policy
result without any automatic merge or secret-dependent review.

Each application main ruleset must require **Dependabot Policy**, pinned to the
GitHub Actions integration (15368). The follow-up creates this check in progress
on the PR head. All other required checks and all three current-head persona
approvals must pass. The check stays pending while native auto-merge is enabled
with `expectedHeadOid`, then succeeds only after validation/activation succeeds.
Failures leave it failing or pending. A later push has no policy result and
cannot inherit the preceding head's approval. This also avoids trying to enable
native auto-merge on an already-clean PR. No direct merge fallback exists.

Automatic eligibility requires exactly one verified Dependabot-authored commit
matching the current head. Explicit update types are parsed from its signed YAML
metadata with pinned PyYAML safe loading, without overriding runner event paths
or trusting PR descriptions. Every grouped member must be patch/minor; missing
metadata fails visibly and major updates stay manual. Before allowing a manual
major update, the policy disables an existing native auto-merge request.

All open Dependabot alerts are paginated with the built-in token's explicit
`vulnerability-alerts: read` permission. Every matching updated dependency must
have a known CVSS score at most 6.9. Dismissed/fixed alerts cannot hide another
open alert, and neither later group members nor alerts beyond the first page are
ignored. The workflow publishes only the policy outcome, not alert details.

The guard reads active branch rules using API 2026-03-10 (Metadata: read), checks
required contexts and integration identities, rejects requested changes and
checks every persona's current-head approval. Scoped CodeQL skips must also
match authoritative API diff paths, including previous paths on renames. Null or
unknown mergeability and propagation of the pending policy check are polled at
most six times with two-second waits; unstable/conflicting states fail closed.
Repeated events are idempotent and genuine API failures remain visible. GitHub
retains final enforcement of review-thread resolution and all branch rules.

Generated repositories that install their own reviewer Apps can set optional
`OBI_WAN_REVIEWER_LOGIN`, `LINT_EASTWOOD_REVIEWER_LOGIN`, and
`ROBOCOP_REVIEWER_LOGIN` repository variables to their actual bot logins, including
`[bot]`. Defaults match the existing shared persona Apps. All three must be
distinct bot identities. Existing per-persona credentials and fork exclusions
remain unchanged. Repository writers who can alter workflows remain privileged;
helper checks do not constrain arbitrary workflow writers.

For activation, merge reviewed source first, then add Dependabot Policy to the
main ruleset without removing any existing requirement or bypass restriction.
The new rule requires a fresh successful CI completion to publish policy evidence;
existing open PRs may need a CI rerun. Do not require the follow-up workflow's
nested job name, which starts only after CI. No production branch is involved.
The first eligible real default-branch Dependabot follow-up remains separate
runtime acceptance in #240; a human implementation PR does not establish it.

CI supplies read-only live branch-rule/schema evidence to Obi-Wan when reviewing
auto-merge/orchestration changes. This confirms actual token access and current
GraphQL input fields without changing reviewer verdict requirements.

## 🧪 Atomic CodeQL regression guard

Before required scope detection, all CodeQL action entry points in workflow and
composite-action YAML must share one full immutable SHA. Structural safe parsing
covers flow mappings, quoted/escaped keys, folded values, aliases and mixed-case
owner/repository names. Negative regressions reject drift, mutable pins and
missing analysis. The existing version/security update groups and daily cadence
remain unchanged. Infrastructure adopts this guard and reviewer eligibility,
retaining weekly updates, independent Required CI and owner merge.

```sh
python -m pip install PyYAML==6.0.3
node --test .github/actions/check-codeql-pins/*.test.js .github/actions/dependabot-auto-merge/*.test.js
```

The local actionlint 1.7.12 schema predates GitHub's documented
`vulnerability-alerts: read` scope. Its other diagnostics remain enforced; GitHub
validates the new permission and CI must pass before merge.

The reviewer API evidence step uses direct read-only API calls and executes no
PR-workspace module with its GitHub client.

Every skipped lint, test or analyzer check is now verified against the actual
reviewed detector filters, with original and renamed API diff paths. Unknown
filter forms refuse skip authorization. GitHub Action subpaths also match their
repository-level package alerts when enforcing the CVSS ceiling.


## Security-alert recovery

Each feed serializes scheduled and manual reconciliation. Before issue writes,
source coverage must be complete and unique. A valid model draft that omits refs
gets deterministic source-linked work items and an explicit warning; malformed
JSON, invalid schemas, unknown refs and duplicate memberships fail before writes.
Existing managed source refs select the canonical issue even when wording changes.

Project attachment retries transient failures at most three times, reading back
possibly committed writes before retrying. Unresolved attachments identify the
saved issue; rerun the same feed to reuse it. Interrupted field initialization fills
only missing fields, preserving human planning. All active groups synchronize before
superseded issues can close. Closure saves source history and End date before Done.
Only the observed empty-error or exact Issue/custom concurrent-close HTTP 422 may
recover, and only after readback proves closed/completed with the exact saved body.
All other errors remain failures. A successful empty feed does not exercise the race.

Dependabot check readiness is re-read at most six times with two-second delays.
A success conclusion and completion timestamp do not override an in-progress
status. Persistent inconsistency fails visibly; rerun CI for the current head.
Only signed exact-head patch/minor metadata can enable native auto-merge. Signed
SHA-only Action updates without update-type, restricted to Action YAML diffs,
pass policy for manual review after all checks and current-head approvals pass;
they never infer semver or activate auto-merge. Missing ordinary/group metadata fails.

Malware classification fetches each unique GHSA referenced by this repository's
open Dependabot alerts, rather than enumerating the global malware catalogue.
Empty feeds make no advisory requests. Failed or unverifiable classification
stops before source checkpoint or issue writes; it never implies no malware.

## Batch 2 security baseline

External Actions use verified immutable commits with readable version comments.
The shared `check-workflow-security` tests reject mutable references, broad grants
and privileged PR-target triggers. Automation tests run for all `.github/**`
changes. Forks retain credential isolation and all configured reviewers remain
required. Repository settings are audited independently of source; stage read-only
defaults/disabled workflow-token approvals and SHA enforcement after source CI
passes. Reviewer App tokens and scoped auto-merge/deployment grants remain explicit.

The PR npm malware gate scans only added/changed exact package versions, at most
25 per request, 200 requests total and 20 pages per batch, with 30-second timeouts.
A missing base lock scans the complete head; a missing head lock while a frontend
manifest remains fails. Invalid refs, unsupported/malformed locks, unverifiable
versions, API/range evidence failures and known malware fail visibly. Removing the
whole frontend has no remaining npm graph. This gate is distinct from the scheduled
repository-alert feed. Mocked regressions make no API writes or model calls.

Python malware coverage follows [the canonical decision](../docs/PYTHON-MALWARE-DECISION.md).
Shared deployment files are synchronized to the Infrastructure source pin, including
the approved Action-upgrade/unauthorized-drift regression. Update the source before
consumers; never edit a vendored workflow or test independently.

Repository Actions secrets are not branch-scoped: writers able to install arbitrary
workflows remain privileged. This helper validates checked-in policy but cannot
constrain a workflow that bypasses it. GitHub rulesets and independent review
remain necessary. The checker parses YAML nodes, including quoted/flow/sequence
forms, rejects aliases, duplicate and merge keys, and requires pinned PyYAML 6.0.3.

Mapping-form writes are checked against `.github/workflow-write-grants.json`,
which records reviewed per-workflow/job grants. Unknown scopes/grant levels and
new writes fail. Changes to that policy require review with the workflow; it does
not grant GitHub permissions itself or replace branch protection.

On pull requests, grant authority comes from the platform event base SHA, never
from the proposed policy file. Bootstrap derives existing writes from that exact
base when no manifest exists. To add a grant, first merge a separately reviewed
policy-only PR under the existing protected review gates; a later workflow PR
can consume it. Fetch the base commit before local PR-policy audits. This detects
self-authorizing policy/workflow changes; it does not make PR-owned code a sandbox
or remove repository-writer privileges.

## Repository validation and browser diagnostics

The path-aware test gate includes `.github/**`, `scripts/**`, `deploy/**`,
`tests/**` and maintained docs in automation validation. It runs workflow and
composite syntax, parser-only script checks and synthetic Compose configuration
plus the existing Batch 1 suites and focused mocked composite regressions.
[Coverage and external boundaries](../docs/AUTOMATION-COVERAGE.md) are explicit.

`scripts/bounded_log.py` retains early, sampled failing and late context within
16,000 characters for reviewers. Full output is streamed with `tee`; failed
logs have roughly 1 MiB capped artifacts retained seven days. Random delimiters
protect multiline outputs and the original command status still determines the
gate. An unavailable check cannot become success through log summarization.

Relevant app/harness changes also require the isolated Chromium job; its failure
or an applicable development-image failure fails Test Results. Browser traces
and screenshots use a 20 MiB/file, 50 MiB/run cap and seven-day retention.
See frontend/README.md for setup and local commands. No job uses real accounts,
production data, live email or paid AI requests for these tests.


## Reviewer context, follow-ups and usage

See [the reviewer contract](AI-REVIEWERS.md) for bounded untrusted human discussion,
verified App ownership, conservative self-owned thread reconciliation, serialized
writers, dated usage estimates and configuration recovery. The owner-selected
`gpt-6-luna` model, per-persona keys/projects and blocking native checks remain.
Repository variables `AI_REVIEW_MODEL`, `AI_REVIEW_REASONING_EFFORT` and
`AI_REVIEW_MAX_OUTPUT_TOKENS` are validated; unset values retain Luna/medium/16000.

The reviewed `workflow-write-grants.json` grants only `pull-requests: write`
to the deterministic promotion-summary workflow. That policy merged before the
workflow was introduced; proposed workflows cannot authorize their own new grants.
Summary publication does not authorize releases or change gates.

Reviewer evidence reads use the existing read-only workflow token, explicitly
limited to contents/pull-requests/checks/statuses read (plus existing security
evidence reads for RoboCop). Native review/follow-up/thread writes use the
separate persona App token; its existing contents-read/pull-requests-write
installation capabilities are not expanded.


## Architecture and production summaries

The [canonical architecture reference](../docs/CI-CD-ARCHITECTURE.md) maps PR/fork/
Dependabot paths, required checks, reviewer interactions, scheduled alerts,
main-to-env-prod/manual release paths and credential trust boundaries to source.
Its per-repository source inventory is checked against actual workflow YAML.

`promotion-summary-request.yml` is a read-only PR signal with no checkout or
artifact/cache handoff. Its default-branch `workflow_run` consumer
`promotion-summary.yml` maintains one GitHub Actions-owned comment for each open
same-repository `env-prod` PR using the actual current target comparison. Reruns
update the same comment; stale/incomplete/denied evidence is reported visibly.
Observed area counts are separate from inferred risks. The workflow loads trusted
main code, never PR code/prose or secret values, and does not change review,
merge, release or recovery authorization. Infrastructure uses gateway-specific
wording. FullStackTemplate's inactive target is not created for symmetry.
