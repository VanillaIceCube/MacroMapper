# FullStackTemplate GitHub automation
FullStackTemplate carries forward the proven CI/CD and security automation from
Notoli and MacroMapper, adapted to the template's repository, images, and
generic GitHub Project.

## Repository settings baseline
The live FullStackTemplate repository uses the Notoli baseline with intentional
least-privilege differences: auto-merge is enabled; merge commits, squash
merges, and rebases are allowed; Actions allow all actions with a read-only
default workflow permission; and GitHub Actions cannot create or approve pull
requests by default. Fork pull requests require approval from first-time
contributors. Workflows request write permissions explicitly when required.

Code security uses the repository's enabled Dependabot alerts/security updates,
secret scanning, and push protection controls. CodeQL default setup remains
unconfigured because the pinned CodeQL workflows in this repository provide the
scanner. The `dependencies`, `codeql`, `vulnerability`, `malware`, and `codex`
labels are used by the alert and operational automation. New repositories must
recreate these settings, labels, and the `SECURITY_ALERTS_TOKEN` secret; see
[`docs/GITHUB_SETUP.md`](../docs/GITHUB_SETUP.md).

## Pull-request CI
`.github/workflows/ci-orchestrator.yml` coordinates:

- Frontend Prettier and ESLint checks
- Backend Ruff checks and formatting
- React/Jest tests
- Django tests
- Node tests for repository automation
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

## AI review apps
Three GitHub Apps provide separate review identities:

- Obi-Wan Code-nobi: code review
- Lint Eastwood: build review and lint auto-fix commits
- RoboCop: security review and security-alert issue management

Required repository variables:

- `OPENAI_PROJECT_ID`
- `OBI_WAN_CODE_NOBI_APP_ID`
- `LINT_EASTWOOD_APP_ID`
- `ROBOCOP_APP_ID`

Required repository secrets:

- `OPENAI_API_KEY`
- `OBI_WAN_CODE_NOBI_PRIVATE_KEY`
- `LINT_EASTWOOD_PRIVATE_KEY`
- `ROBOCOP_PRIVATE_KEY`

Install the Apps on the generated repository with the permissions in
[`docs/GITHUB_SETUP.md`](../docs/GITHUB_SETUP.md). Store the same four review
secrets in both the Actions and Dependabot secret stores. Dependabot workflows
receive only Dependabot secrets, so this duplication lets their pull requests
run the required reviewers. Fork pull requests never receive either store's
secrets and cannot satisfy the required reviewer child checks.

## Security-alert aggregation
The daily/manual `alert-codeql.yml`, `alert-vulnerability.yml`, and `alert-malware.yml` workflows group open alerts into managed FullStackTemplate issues and synchronize them with the FullStackTemplate Project.

Additional configuration:

- Repository variable `SECURITY_ALERTS_PROJECT_ID` set to the generated
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

`scripts/create-github-project.ps1` copies Notoli's Project structure, links it
to the target repository, verifies its fields, views, and supported workflows,
and sets `SECURITY_ALERTS_PROJECT_ID`. GitHub excludes the repository-scoped
`Auto-add to project` workflow from Project copies, so configure it for the
target repository in the GitHub UI as described in
[`docs/GITHUB_SETUP.md`](../docs/GITHUB_SETUP.md).

## Deployment
`.github/workflows/ci-deploy.yml` runs on `env-prod` pushes or manually. It:

1. Builds and pushes `fullstacktemplate-backend` and `fullstacktemplate-frontend` to GHCR.
2. Uploads Docker Compose, Nginx, and optional Cloudflare origin certificates.
3. Connects over SSH, writes the backend environment, recreates the stack, and runs Django migrations.

Repository variables:

- `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH`, optional `DEPLOY_PORT`
- `DJANGO_DEBUG`, `DJANGO_SQLITE_PATH`
- `DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ALLOWED_ORIGINS`, `DJANGO_CSRF_TRUSTED_ORIGINS`
- optional `DJANGO_FORCE_SCRIPT_NAME`
- `DJANGO_FRONTEND_BASE_URL`, `DJANGO_EMAIL_BACKEND`, `DJANGO_EMAIL_TIMEOUT`, `DJANGO_DEFAULT_FROM_EMAIL`
- optional `REACT_APP_API_BASE_URL`

Repository secrets:

- `DEPLOY_SSH_KEY`
- `DJANGO_SECRET_KEY`
- `DJANGO_EMAIL_HOST_KEY`
- optional automated TLS secrets `CLOUDFLARE_ORIGIN_CERT_PEM` and `CLOUDFLARE_ORIGIN_KEY_PEM`

See `deploy/README.md` for server and Cloudflare details.

## Dependabot
`.github/dependabot.yml` checks npm, pip, GitHub Actions, and Docker dependencies daily. Patch and minor Dependabot updates can auto-merge only after the lint, test, CodeQL, vulnerability, and malware gates succeed.

The main-branch ruleset mirrors Notoli and includes the orchestrator-level
`Auto Merge` context among its required checks. CI emits that top-level context
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
All three reviewers inherit the same 512 KiB diff budget from
`.github/actions/get-pr-diff/action.yml`; reviewer workflows do not override it.
OpenAI review requests also cap combined reasoning and visible output at 16,000
tokens so they do not reserve the model's full output allowance against project
rate limits.

## Main branch protection
The active `main` ruleset requires pull requests, resolved review threads, the
lint/test/CodeQL scope and analyzer/dependency checks, the Automation Tests
check, all three AI reviewer child checks, and `Auto Merge`. The reviewers run
for trusted same-repository pull requests, including Dependabot once its four
review secrets are configured. The ruleset blocks force pushes and branch
deletion and has no bypass actors. The standalone `CodeQL` context is
intentionally not required because the scope-aware workflow does not emit that
parent check for scope-empty pull requests. This is an intentional compatibility
difference from Notoli; validate exact check names after the first CI run when
creating the ruleset.

## Local automation checks
```powershell
node --test .github/actions/collect-upstream-major-upgrade-evidence/collect-upstream-major-upgrade-evidence.test.js .github/actions/publish-ai-review/publish-ai-review.test.js .github/actions/security-alerts/sync-security-alerts.test.js
docker run --rm -v "${PWD}:/repo" --workdir /repo rhysd/actionlint:latest -color
```
