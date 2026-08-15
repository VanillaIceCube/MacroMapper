# GitHub setup
Complete this setup before opening the first pull request so every required workflow can run.

## 0. Match the repository settings
FullStackTemplate starts from the live Notoli repository baseline. Apply this
configuration to a new repository before opening its first pull request. The
template intentionally keeps a read-only Actions default and omits the
standalone `CodeQL` required check; see the rationale below.

### General

- Keep the default branch named `main`.
- Keep the repository public with Issues, Projects, Wiki, and Discussions
  enabled. Downloads remain disabled.
- Enable merge commits, squash merges, and rebase merges.
- Enable **Allow auto-merge**. Keep automatic head-branch deletion disabled,
  keep **Allow update branch** disabled, and leave commit signoff disabled.
- Keep the default merge titles/messages (`PR_TITLE`, `MERGE_MESSAGE`,
  `COMMIT_OR_PR_TITLE`, and `COMMIT_MESSAGES`).

### Actions → General

- Enable Actions and allow all actions and reusable workflows.
- Set workflow permissions to **Read repository contents and packages
  permissions** (read-only default).
- Leave **Allow GitHub Actions to create and approve pull requests** disabled.
- Set fork pull-request approval to **Require approval for first-time
  contributors**.

The repository and workflow permissions are intentionally different: the
repository default matches Notoli, while individual workflows still request
the narrowest permissions they need.

### Security → Code security and analysis

Enable the following repository controls:

- Dependency graph
- Dependabot alerts
- Dependabot security updates
- Secret scanning
- Secret scanning push protection

Do not enable GitHub's default CodeQL setup for this template. CodeQL is
already supplied by the pinned workflows under `.github/workflows/`; those
workflows upload the results to **Security → Code scanning**. The template
uses the same `actions`, JavaScript/TypeScript, and Python coverage as Notoli.

### Labels used by security automation

Create these labels with the following descriptions so the scheduled alert
workflows can group and update their managed issues:

| Label | Description |
| --- | --- |
| `dependencies` | Dependabot-authored dependency update PRs |
| `codeql` | Grouped CodeQL security alerts. |
| `vulnerability` | Grouped non-urgent Dependabot vulnerability alerts. |
| `malware` | Grouped Dependabot malware alerts. |
| `codex` | Work generated or assisted by Codex |

## 1. Create the Project
Authenticate GitHub CLI with repository and Projects access:

```powershell
gh auth login
gh auth refresh -s project
powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/create-github-project.ps1 `
  -Owner YOUR_GITHUB_OWNER `
  -Repository YOUR_REPOSITORY
```

The script uses Notoli's Project as the reusable Project template. It:

1. Refuses to create a duplicate Project with the same title.
2. Copies Notoli's views, custom fields, configured workflows, and insights
   without copying its linked issues.
3. Rewrites the Project description and README for the target repository.
4. Links the copied Project to the target repository.
5. Verifies the copied fields, views, and supported workflows against Notoli.
6. Sets the target repository variable `SECURITY_ALERTS_PROJECT_ID`.

The copied fields match Notoli:

- `Status`: `Backlog`, `Ready`, `In Progress`, `In Review`, `Done`
- `Domain`: `Frontend`, `Backend`, `UX/UI`, `Data Model`, `Deployment`, `CI/CD`
- `Type`: `Bug`, `Feature`, `Enhancement`, `Refactor`, `Chore`, `Research`,
  `Security`
- `Priority`: `P0`, `P1`, `P2`, `P3`
- `Size`: `XS`, `S`, `M`, `L`, `XL`
- `Estimate`, `Start date`, and `End date`

The copied views match Notoli's `Kanban`, `Detailed Kanban`, `New Issues`,
`Updated Issues`, `Issue Picker`, and `Roadmap` layouts, including their visible
fields, filters, grouping, and sorting.

GitHub does not copy the repository-scoped `Auto-add to project` workflow.
After the script completes, open the new Project's **Workflows** page and
configure `Auto-add to project` for the target repository. The remaining
configured workflows, including `Auto-add sub-issues to project`, are copied
and verified by the script.
GitHub documents this behavior in
[Copying an existing project](https://docs.github.com/en/issues/planning-and-tracking-with-projects/creating-projects/copying-an-existing-project).

Notoli is the default source (`VanillaIceCube` Project `8`). A different source
can be supplied with `-SourceProjectOwner` and `-SourceProjectNumber`.

## 2. Register the AI reviewer GitHub Apps
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

## 3. Configure secrets for Dependabot-triggered reviews
Dependabot-triggered workflows receive only **Dependabot** secrets, not the
normal **Actions** secrets. To run the same required AI reviewers for trusted
Dependabot pull requests, add these four values again under **Settings →
Secrets and variables → Dependabot → Secrets**:

```text
OPENAI_API_KEY
OBI_WAN_CODE_NOBI_PRIVATE_KEY
LINT_EASTWOOD_PRIVATE_KEY
ROBOCOP_PRIVATE_KEY
```

Use the same values as their Actions-secret counterparts. GitHub never reveals
or copies secret values between the stores, so this is a deliberate manual
setup step. Repository variables, including the OpenAI project and GitHub App
IDs, remain configured under **Actions → Variables**.

## 4. Configure OpenAI and security aggregation
Set:

```text
Variable: OPENAI_PROJECT_ID
Secret:   OPENAI_API_KEY
Variable: SECURITY_ALERTS_PROJECT_ID
Secret:   SECURITY_ALERTS_TOKEN
```

`SECURITY_ALERTS_TOKEN` must be a distinct user token with access to the
personal or organization Project. Do not reuse a GitHub App key or installation
token. The three scheduled/manual alert workflows use RoboCop to read alerts
and manage repository issues, while this token adds and updates those issues in
the Project.

Enable the repository settings in [the baseline above](#0-match-the-repository-settings),
then install RoboCop with the permissions listed in this guide. Add the
`SECURITY_ALERTS_TOKEN` secret before running an alert workflow; it cannot be
copied from Notoli because it is a credential.
Run each `Alert: ...` workflow manually once after the first successful CI run.
No-alert runs should succeed without creating issues.

## 5. Branch rules after the first PR
Wait until one pull request has produced the actual check names, then add the
Notoli-inspired ruleset for `main`:

- require a pull request before merging;
- require the independent lint, test, CodeQL scope, CodeQL analyzer,
  automation-test, vulnerability, and malware checks;
- require the three AI reviewer child checks and the `Auto Merge` check;
- require all review threads to be resolved;
- allow merge commits, squash merges, and rebases;
- block force pushes and branch deletion;
- configure no bypass actors.

Do not require a standalone `CodeQL` context. FullStackTemplate's reusable
CodeQL workflow emits `CodeQL / Detect CodeQL Scope` and the three analyzer
contexts. Scope-empty pull requests skip the analyzers and do not emit a
standalone parent check, so requiring that context would leave a permanent
pending check. This is an intentional compatibility difference from Notoli's
current ruleset. Validate the actual check names from the first CI run before
saving the ruleset; GitHub status checks are matched by exact name.

The required AI reviewer contexts are:

```text
AI Code Review / Obi-Wan Code-nobi code review
AI Build Sheriff Review / Lint Eastwood build sheriff review
AI Security Review / RoboCop security review
Auto Merge
```

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

## 6. Deployment configuration
The complete deployment variables and secrets are in
[the deployment guide](../deploy/README.md). The deploy workflow only runs on
`env-prod` pushes or manual dispatch, so application CI can be proven before
production credentials are ready.
