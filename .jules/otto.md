# 🦦 Otto's Journal — Reusable Backlog Management Knowledge

## 2026-08-31 - Architectural Decomposition & Vocabulary Synchronization Sequence
**Learning:** Structural refactor issues (#94 frontend decomposition, #107 backend decomposition, #108 naming convention standardization) describe closely related architectural improvements that should be executed sequentially rather than in parallel to avoid repeated refactored file movements and import churn.
**Action:** Maintain explicit dependency relationships between #94, #107, and #108 in backlog reviews so implementation agents execute backend and frontend structural decomposition before attempting cross-stack terminology standardization.

## 2026-08-31 - Landing Page Migration Dependency Tracking
**Learning:** Issue #111 (remove static Home page and default to Meal Diary) acts as a prerequisite for #112 (build data-driven Today dashboard), while PR #114 is the active implementation PR addressing #111.
**Action:** In future daily audits, ensure #112 remains deferred until #111 is fully merged and sufficient supporting domain data (goals, activities, trends) is implemented in the codebase.

## 2026-09-06 - Isolated Sandbox Forensic Audit Scope
**Learning:** When executing daily backlog audits in an isolated agent sandbox without GitHub CLI (`gh`) authentication, live issue and project board mutation APIs cannot be directly queried or updated. Reconciling backlog state through local git repository analysis (commit history, active specialist branches, and workflows) ensures accurate backlog reporting.
**Action:** Reconcile backlog context through local git repository analysis, record durable learnings in `.jules/otto.md`, and present a clear Daily Organization Report without modifying application code or introducing speculative issues.

## 2026-09-09 - Specialist Hardening Branches and API Stability
**Learning:** Specialist hardening work on active `jules/marty/*` branches (e.g. portion recovery, nutrition math, error message consolidation, estimation tree safety) addresses localized reliability edge cases without altering core domain contracts or requiring backlog status shifts.
**Action:** Protect in-flight specialist branches and avoid restructuring corresponding backlog items or altering acceptance criteria while active hardening commits are being merged.

## 2026-09-10 - Canonical Issue Preservation for Active Specialist Implementation
**Learning:** Issues such as #124 ("Prevent duplicate Jules/Otto backlog-audit pull requests") have active implementation PRs (#125) undergoing review, while specialist PRs from Marty (#157, #159, #161) address distinct modules across nutrition math and meal portion editing without requiring issue splitting or criteria changes.
**Action:** Treat active implementation PRs as protected in-flight work. Ensure the canonical tracking issue remains open and untouched until the corresponding PR is merged or closed.

## 2026-09-11 - Automated Dependency Update Reconciliations
**Learning:** Dependabot pull requests (such as #163 updating `djangorestframework` to 3.18.1 and #171 updating `openai` to 3.13.0) are automatically merged into `main` after CI checks pass, without introducing domain logic or backlog scope changes.
**Action:** Treat routine dependency bumps as self-contained automated chores that do not require creating, modifying, or closing product backlog tickets.

## 2026-09-12 - Reconciling Security Action Pinning and Duplicate Backlog Audit PR Hygiene
**Learning:** Downstream parity PRs from Kira (such as PR #164 aligning security-alerts action pinning) and open backlog audit PRs (#125, #166) are part of automated maintenance and deduplication flows. Overlapping audit PRs are filtered by the deduplication workflow (`prevent-duplicate-otto-backlog-audit-prs`).
**Action:** In daily audits, treat in-flight Kira security action pinning and Otto backlog audit PRs as system-level maintenance work. Keep canonical product backlog tickets (#26-#124) cleanly separated from routine automation PRs.

## 2026-09-14 - Incremental Notification Logic Hardening & Active Implementation Reconciliation
**Learning:** Recent specialist commits (such as `108d144` hardening notification PATCH update handling and test coverage) resolve localized edge cases in existing domain endpoints without altering task scope or displacing active implementation PRs.
**Action:** Verify that incremental reliability fixes merged into `main` update test suites cleanly, and preserve active specialist PRs in review without modifying issue boundaries or changing Project metadata underneath ongoing work.

## 2026-09-16 - Automated React-DOM Version Bump Reconciliation
**Learning:** Dependency update PR #175 bumped `react-dom` to 19.3.0 and merged cleanly into `main` after passing frontend test and lint gates. Routine framework dependency bumps managed by Dependabot maintain full backward compatibility with application components.
**Action:** Treat automated dependency upgrades as routine environment maintenance that does not alter product backlog scope or require creating untracked follow-up issues.

## 2026-09-17 - Testing Library Dependency Update Reconciliations
**Learning:** Dependency update PR #180 bumped `@testing-library/dom` to 10.4.2 and merged cleanly into `main` after passing frontend test and lint gates without breaking component test coverage.
**Action:** Treat automated test library dependency upgrades as routine maintenance chores that keep testing tools current without requiring backlog scope modifications or tracking issue creation.

## 2026-09-18 - Automated Docker Action and Backend SDK Version Bump Reconciliation
**Learning:** Recent automated pull requests (#183 updating `docker/setup-qemu-action` to 4.4.0, #185 updating `openai` to 3.14.0, and #186 updating `docker/setup-buildx-action` to 4.4.0) were automatically merged into `main` after passing CI test and lint gates.
**Action:** Treat routine CI action and SDK version upgrades as automated infrastructure maintenance that does not require backlog ticket creation or manual project board updates.
