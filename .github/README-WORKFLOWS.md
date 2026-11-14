# ⚙️ MacroMapper GitHub workflows

This folder owns GitHub Actions, dependency updates, AI reviews, and
security-alert automation for this repository.

## 🚦 Before your first pull request

Complete the [GitHub setup checklist](GITHUB_SETUP.md) before expecting all
required workflows to pass. It covers repository settings, reviewer Apps,
Actions and Dependabot credentials, the GitHub Project, and branch protection.
Repository settings and secret values are configured separately from source.

## 🧭 Structure

- `workflows/`: CI, review, security-alert, and release entry points.
- `actions/`: reusable local actions and regression tests.
- `dependabot.yml`: dependency update configuration.
- [Workflow reference](WORKFLOW-REFERENCE.md): exact triggers, gates, and credential contracts.
- [Reviewer guide](AI-REVIEWERS.md): review context, feedback, and recovery.

## 🔄 Pull requests and releases

Pull requests run the applicable validation and security checks plus the
required AI reviews. Missing required credentials and unavailable reviewer
results remain visible failures. Forks retain their credential isolation.

Live-server releases follow the [production guide](../deploy/production/README.md);
local Docker instructions live in the [deployment README](../deploy/README.md).

## 🧪 Checks and diagnostics

See the [repository test guide](../tests/README.md) for local commands and
prerequisites. The [CI/CD architecture](CI-CD-ARCHITECTURE.md) maps
workflow events and trust boundaries.

## 📚 Detailed workflow reference


<details>
<summary>Triggers, checks, credentials, and maintenance contracts</summary>

<a id="major-upgrade-review-evidence"></a>

- [Major-upgrade review evidence](WORKFLOW-REFERENCE.md#major-upgrade-review-evidence)

<a id="-repository-settings-baseline"></a>

- [⚙️ Repository Settings Baseline](WORKFLOW-REFERENCE.md#-repository-settings-baseline)

<a id="-pull-request-ci"></a>

- [✅ Pull-Request CI](WORKFLOW-REFERENCE.md#-pull-request-ci)

<a id="-ai-review-apps"></a>

- [🤖 AI Review Apps](WORKFLOW-REFERENCE.md#-ai-review-apps)

<a id="-security-alert-aggregation"></a>

- [🛡️ Security-Alert Aggregation](WORKFLOW-REFERENCE.md#-security-alert-aggregation)

<a id="-deployment"></a>

- [🚀 Deployment](WORKFLOW-REFERENCE.md#-deployment)

<a id="-dependabot"></a>

- [📦 Dependabot](WORKFLOW-REFERENCE.md#-dependabot)

<a id="-main-branch-protection"></a>

- [🔒 Main Branch Protection](WORKFLOW-REFERENCE.md#-main-branch-protection)

<a id="-local-automation-checks"></a>

- [🧰 Local Automation Checks](WORKFLOW-REFERENCE.md#-local-automation-checks)

<a id="-separate-openai-reviewer-credentials"></a>

- [🔑 Separate OpenAI reviewer credentials](WORKFLOW-REFERENCE.md#-separate-openai-reviewer-credentials)

<a id="-independent-estimation-credentials"></a>

- [🍽️ Independent estimation credentials](WORKFLOW-REFERENCE.md#-independent-estimation-credentials)

<a id="-shared-mcp-framework"></a>

- [🔌 Shared MCP framework](WORKFLOW-REFERENCE.md#-shared-mcp-framework)

<a id="-dependency-evidence-and-alert-lifecycle-parity"></a>

- [🛡️ Dependency evidence and alert lifecycle parity](WORKFLOW-REFERENCE.md#-dependency-evidence-and-alert-lifecycle-parity)

<a id="-shared-deployment-action-update"></a>

- [🔄 Shared deployment action update](WORKFLOW-REFERENCE.md#-shared-deployment-action-update)

<a id="-reviewer-model"></a>

- [🤖 Reviewer model](WORKFLOW-REFERENCE.md#-reviewer-model)

<a id="-compatible-codeql-updates"></a>

- [📦 Compatible CodeQL updates](WORKFLOW-REFERENCE.md#-compatible-codeql-updates)

<a id="-protected-dependabot-auto-merge"></a>

- [🔒 Protected Dependabot auto-merge](WORKFLOW-REFERENCE.md#-protected-dependabot-auto-merge)

<a id="-atomic-codeql-regression-guard"></a>

- [🧪 Atomic CodeQL regression guard](WORKFLOW-REFERENCE.md#-atomic-codeql-regression-guard)

<a id="security-alert-recovery"></a>

- [Security-alert recovery](WORKFLOW-REFERENCE.md#security-alert-recovery)

<a id="batch-2-security-baseline"></a>

- [Batch 2 security baseline](WORKFLOW-REFERENCE.md#batch-2-security-baseline)

<a id="repository-validation-and-browser-diagnostics"></a>

- [Repository validation and browser diagnostics](WORKFLOW-REFERENCE.md#repository-validation-and-browser-diagnostics)

<a id="reviewer-context-follow-ups-and-usage"></a>

- [Reviewer context, follow-ups and usage](WORKFLOW-REFERENCE.md#reviewer-context-follow-ups-and-usage)

<a id="architecture-and-production-summaries"></a>

- [Architecture and production summaries](WORKFLOW-REFERENCE.md#architecture-and-production-summaries)

<a id="security-alert-configuration-contract"></a>

- [Security-alert configuration contract](WORKFLOW-REFERENCE.md#security-alert-configuration-contract)

<a id="-retired-agent-cleanup"></a>

- [🧹 Retired agent cleanup](WORKFLOW-REFERENCE.md#-retired-agent-cleanup)

<a id="codeql-maintenance"></a>

- [CodeQL maintenance](WORKFLOW-REFERENCE.md#codeql-maintenance)

<a id="shared-docker-login-maintenance"></a>

- [Shared Docker login maintenance](WORKFLOW-REFERENCE.md#shared-docker-login-maintenance)

</details>
