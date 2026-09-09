# 🦦 Otto's Journal

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
