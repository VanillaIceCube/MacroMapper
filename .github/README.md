# ⚙️ GitHub automation

GitHub Actions, repository setup, dependency updates, and AI reviews for MacroMapper.
Source-controlled configuration and GitHub account/repository settings are separate.

## 🧭 Structure

- [Workflows](workflows/README.md): triggers, required gates, security checks, releases, and diagnostics.
- [Local actions](actions/README.md): reviewer context, feedback lifecycle, request policy, and regression tests.
- `dependabot.yml`: dependency-update configuration.
- `workflows/*.yml` and `actions/*/action.yml`: executable automation definitions.

## 🚦 Before your first pull request

1. Configure Actions, dependency alerts, advanced CodeQL, and available secret scanning/push protection using this repository's settings below.
2. Install the three reviewer GitHub Apps and set their App ID variables.
3. Store each persona's OpenAI key and App private key in both Actions and Dependabot secrets: six reviewer secrets in each store.
4. Configure this repository's reviewer project, security-alert Project, and separate Project token.
5. Verify fresh same-repository human and Dependabot PR results before activating or changing required checks.
6. Configure deployment separately through the app or gateway production guide.

Missing credentials and unavailable review evidence fail visibly. Existing secret
values are not recoverable from GitHub; use the original credentials through the
owner's approved process. Never weaken checks to make setup pass.

## ⚙️ Repository setup

### 0. Configure the repository settings

MacroMapper uses a read-only Actions default and omits the standalone `CodeQL`
required check; see the rationale below. Apply this configuration before
relying on the pull-request gates.

#### General

- Keep the default branch named `main`.
- Keep the repository public with Issues, Projects, Wiki, and Discussions
  enabled. Downloads remain disabled.
- Enable merge commits, squash merges, and rebase merges.
- Enable **Allow auto-merge**. Keep automatic head-branch deletion disabled,
  keep **Allow update branch** disabled, and leave commit signoff disabled.
- Keep the default merge titles/messages (`PR_TITLE`, `MERGE_MESSAGE`,
  `COMMIT_OR_PR_TITLE`, and `COMMIT_MESSAGES`).

#### Actions → General

- Enable Actions and allow all actions and reusable workflows.
- Set workflow permissions to **Read repository contents and packages
  permissions** (read-only default).
- Leave **Allow GitHub Actions to create and approve pull requests** disabled.
- Set fork pull-request approval to **Require approval for first-time
  contributors**.

The repository and workflow permissions are intentionally different: the
repository default is read-only, while individual workflows request the
narrowest permissions they need.

#### Security → Code security and analysis

Enable the following repository controls:

- Dependency graph
- Dependabot alerts
- Dependabot security updates
- Secret scanning
- Secret scanning push protection

Do not enable GitHub's default CodeQL setup for MacroMapper. CodeQL is
already supplied by the pinned workflows under `.github/workflows/`; those
workflows upload the results to **Security → Code scanning** for Actions,
JavaScript/TypeScript, and Python.

#### Labels used by security automation

Create these labels with the following descriptions so the scheduled alert
workflows can group and update their managed issues:

| Label | Description |
| --- | --- |
| `dependencies` | Dependabot-authored dependency update PRs |
| `codeql` | Grouped CodeQL security alerts. |
| `vulnerability` | Grouped non-urgent Dependabot vulnerability alerts. |
| `malware` | Grouped Dependabot malware alerts. |
| `codex` | Work generated or assisted by Codex |

### 1. Create or recover the MacroMapper Project

Reuse the existing MacroMapper Project whenever possible. Check the owner's
Projects before creating a replacement so you do not duplicate the board.
Authenticate GitHub CLI with repository and Projects access:

```powershell
gh auth login
gh auth refresh -s project
gh project list --owner VanillaIceCube
```

Only when the board is missing, copy Notoli's established Project structure:

```powershell
gh project copy 8 --source-owner VanillaIceCube --target-owner VanillaIceCube --title MacroMapper
```

Link the copied or existing MacroMapper Project and set its repository variable:

```powershell
$macroMapperProjectNumber = Read-Host 'MacroMapper Project number'
gh project link $macroMapperProjectNumber --owner VanillaIceCube --repo VanillaIceCube/MacroMapper
$macroMapperProjectId = gh project view $macroMapperProjectNumber --owner VanillaIceCube --format json --jq '.id'
if ($LASTEXITCODE -ne 0 -or -not $macroMapperProjectId) { throw 'Could not read the MacroMapper Project ID.' }
gh variable set SECURITY_ALERTS_PROJECT_ID --repo VanillaIceCube/MacroMapper --body $macroMapperProjectId
```

Enter the actual numeric MacroMapper Project number when prompted. Update the
Project description and README for MacroMapper in the GitHub UI, and verify
the fields, views, and workflows there before running security aggregation.

The copied fields match Notoli:

- `Status`: `Backlog`, `Ready`, `In Progress`, `In Review`, `Done`
- `Domain`: `Frontend`, `Backend`, `UX/UI`, `Data Model`, `Deployment`, `CI/CD`
- `Work type`: `Bug`, `Feature`, `Enhancement`, `Refactor`, `Chore`, `Research`,
  `Security`
- `Priority`: `P0`, `P1`, `P2`, `P3`
- `Size`: `XS`, `S`, `M`, `L`, `XL`
- `Estimate`, `Start date`, and `End date`

The copied views match Notoli's `Kanban`, `Detailed Kanban`, `New Issues`,
`Updated Issues`, `Issue Picker`, and `Roadmap` layouts, including their visible
fields, filters, grouping, and sorting.

GitHub does not copy auto-add workflows. Open the MacroMapper Project's
**Workflows** page and configure the required auto-add workflows for the
target repository, including `Auto-add to project`. Verify the remaining
copied workflows manually.
GitHub documents this behavior in
[Copying an existing project](https://docs.github.com/en/issues/planning-and-tracking-with-projects/creating-projects/copying-an-existing-project).

Notoli (`VanillaIceCube` Project `8`) owns the field, view, and workflow
structure used by MacroMapper. If recovering from a different source, change
the source owner and Project number in the copy command.

### 2. Register the AI reviewer GitHub Apps

Create three private GitHub Apps under the repository owner. Give each app only
the listed repository permissions, generate one private key, and install it on
this repository.

| App | Repository permissions |
| --- | --- |
| Obi-Wan Code-nobi | Contents: read; Pull requests: read and write; Metadata: read |
| Lint Eastwood | Contents: read and write; Pull requests: read and write; Metadata: read |
| RoboCop | Contents: read; Pull requests: read and write; Checks: read; Issues: read and write; Code scanning alerts: read; Dependabot alerts: read; Metadata: read |

GitHub recommends choosing the minimum app permissions and protecting private
keys as credentials. See [registering a GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)
and [managing private keys](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps).

Set these repository variables to the numeric App IDs:

```text
OBI_WAN_CODE_NOBI_APP_ID
LINT_EASTWOOD_APP_ID
ROBOCOP_APP_ID
```

Store each complete downloaded PEM as the matching repository secret:

```text
OBI_WAN_CODE_NOBI_PRIVATE_KEY
LINT_EASTWOOD_PRIVATE_KEY
ROBOCOP_PRIVATE_KEY
```

### 3. Configure secrets for Dependabot-triggered reviews

Dependabot-triggered workflows receive only **Dependabot** secrets, not the
normal **Actions** secrets. To run the same required AI reviewers for trusted
Dependabot pull requests, add these six values again under **Settings →
Secrets and variables → Dependabot → Secrets**:

```text
OBI_WAN_OPENAI_API_KEY
LINT_EASTWOOD_OPENAI_API_KEY
ROBOCOP_OPENAI_API_KEY
OBI_WAN_CODE_NOBI_PRIVATE_KEY
LINT_EASTWOOD_PRIVATE_KEY
ROBOCOP_PRIVATE_KEY
```

Use the same values as their Actions-secret counterparts. GitHub never reveals
or copies secret values between the stores, so this is a deliberate manual
setup step. Repository variables, including the OpenAI project and GitHub App
IDs, remain configured under **Actions → Variables**.

### 4. Configure OpenAI and security aggregation

Set:

```text
Variable: OPENAI_REVIEWERS_PROJECT_ID
Secret:   OBI_WAN_OPENAI_API_KEY
Secret:   LINT_EASTWOOD_OPENAI_API_KEY
Secret:   ROBOCOP_OPENAI_API_KEY
Variable: SECURITY_ALERTS_PROJECT_ID
Secret:   SECURITY_ALERTS_TOKEN
```

`SECURITY_ALERTS_TOKEN` must be a distinct user token with access to the
personal or organization Project. Do not reuse a GitHub App key or installation
token. The three scheduled/manual alert workflows use RoboCop to read alerts
and manage repository issues, while this token adds and updates those issues in
the Project.

Enable the repository settings in [the baseline above](#0-configure-the-repository-settings),
then install RoboCop with the permissions listed in this guide. Add the
`SECURITY_ALERTS_TOKEN` secret before running an alert workflow; it must be
created specifically for MacroMapper because GitHub does not copy credentials.
Run each `Alert: ...` workflow manually once after the first successful CI run.
No-alert runs should succeed without creating issues.

### 6. Deployment configuration

The complete deployment variables and secrets are in
[the deployment guide](../deploy/README.md). The deploy workflow only runs on
`env-prod` pushes or manual dispatch, so application CI can be proven before
production credentials are ready.

### 🔑 Deferred OpenAI migration

Use the [reviewer key mapping and cutover sequence](README.md#-credential-ownership). Keep meal-estimation credentials separate from the reviewer project; production and local estimation use independent keys/projects.

## 🔑 Credential ownership

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

### 🍽️ Application credentials

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

## 🔒 Branch protection

### 5. Branch rules after the first PR

Wait until one pull request has produced the actual check names, then add the
MacroMapper ruleset for `main`:

- require a pull request before merging;
- require the independent lint, test, CodeQL scope, CodeQL analyzer,
  automation-test, vulnerability, and malware checks;
- require the three AI reviewer child checks and the `Auto Merge` check;
- require all review threads to be resolved;
- allow merge commits, squash merges, and rebases;
- block force pushes and branch deletion;
- configure no bypass actors.

Do not require a standalone `CodeQL` context. MacroMapper's reusable
CodeQL workflow emits `CodeQL / Detect CodeQL Scope` and the three analyzer
contexts. Scope-empty pull requests skip the analyzers and do not emit a
standalone parent check, so requiring that context would leave a permanent
pending check. Validate the actual check names from the first CI run before
saving the ruleset; GitHub status checks are matched by exact name.

The required AI reviewer contexts are:

```text
AI Code Review / Obi-Wan Code-nobi code review
AI Build Sheriff Review / Lint Eastwood build sheriff review
AI Security Review / RoboCop security review
Auto Merge
```

Each AI child check must reflect its native review verdict. The shared review
publisher leaves `APPROVE` and `COMMENT` checks successful, but fails the
corresponding required check after publishing `REQUEST_CHANGES`. Repeated
blocking verdicts remain failed; a later approval for the updated head commit
produces a passing check. When validating or recovering the ruleset, exercise
both verdicts and confirm GitHub blocks merging while a changes-requested check
is failing.

The reviewers run for trusted same-repository pull requests, including
Dependabot pull requests once [the Dependabot secrets](#3-configure-secrets-for-dependabot-triggered-reviews)
are present. CI always emits the required top-level `Auto Merge` context: it
reports not-applicable for ordinary pull requests and records gate eligibility
for Dependabot. A separate Dependabot-only job enables auto-merge for eligible
updates. Obi-Wan adds an advisory **Major upgrade brief** for Dependabot
semver-major updates. It reports exact Dependabot metadata alongside supplied
Dependabot information, externally retrieved GitHub Release notes where
available, repository-diff, and verification evidence. It explicitly marks
unknown information only when it affects the recommendation. The brief is part of Obi-Wan's
normal review and adds no required check. Fork pull requests intentionally
receive no sensitive secrets, so they
cannot satisfy these required reviewer child checks. Bring a fork change into a
trusted same-repository branch before merging it.

Do not require branches to be up to date before merging.

## 🧪 Verification

Repository CI helpers live in `.github/tools/`: `bounded_log.py` retains bounded
reviewer diagnostics; `install_actionlint.sh` installs the pinned, checksum-verified
Linux Actionlint release; `validate_repository.py` checks workflow/script syntax
and synthetic Compose configuration; `ci_architecture.py` validates the documented
CI contract and regenerates `docs/CI-CD-SOURCE-INVENTORY.json`. Run these from the
repository root. See the [workflow checks](workflows/README.md#-checks-and-diagnostics)
and [CI architecture](../docs/CI-CD-ARCHITECTURE.md) for dependencies and commands.

Verify the current head's independent checks and all three native review identities.
Distinguish synthetic local tests from actual GitHub runner/credential acceptance.
After an authorized merge, verify default-branch baselines and separately review
alert-workflow side effects before fresh manual dispatches. A successful human PR
does not prove access to the separate Dependabot secret store. Source review does
not authorize merging, branch promotion, production deployment, or key rotation.

## 📚 Related guides

- [Workflow behavior and maintenance](workflows/README.md).
- [Shared action and reviewer contracts](actions/README.md).
- [CI/CD architecture](../docs/CI-CD-ARCHITECTURE.md).
- [Application production setup and recovery](../deploy/production/README.md).
