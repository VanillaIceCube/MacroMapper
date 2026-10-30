# 🤖 MacroMapper GitHub Automation
MacroMapper's CI/CD and security automation validates the application,
publishes its images, deploys production, reviews pull requests, and keeps
security work synchronized with the MacroMapper Project.

Production bundles default `OPENAI_MEAL_ESTIMATION_TIMEOUT` to 110 seconds for
the entire AI operation, with retries disabled. An optional repository variable
can shorten this budget (greater than zero, at most 110). The two-minute
Infrastructure API proxy change must be released before the app image change;
passing CI does not authorize either production operation.

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
- Dependabot auto-merge after all independent gates pass

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
job enables auto-merge for eligible updates, so its nested reusable-workflow
check name never becomes a branch-protection dependency. Dependabot pull
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

Credential provisioning is a separate operator step. Configure the new secrets
and project variable before activating these workflows. Missing keys fail
visibly; there is no fallback to the old shared `OPENAI_API_KEY`.

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
6. Stage the new secrets and `OPENAI_REVIEWERS_PROJECT_ID` while leaving the
   legacy `OPENAI_API_KEY` and `OPENAI_PROJECT_ID` unchanged. Existing default-
   branch jobs can continue using the legacy pair until the source is merged.
   Keep old keys valid until every affected consumer has verified the new keys;
   retain any Default-project key still used elsewhere. To reverse the source
   change, revert the workflow change; the retained legacy pair remains usable.
   Do not place a shared legacy key into the three new secret slots or expose
   key values in logs/issues.

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
