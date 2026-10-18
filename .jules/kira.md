> **Historical journal — retired 2026-10-17:** Earlier entries are preserved as context. Their scheduled-agent instructions are superseded by the retirement record below.

# Kira's Journal — Downstream Parity Learnings

## 2026-09-04 — Security Alert Action SHA Pinning Parity
### Learning
The security-alerts composite action at `.github/actions/security-alerts/action.yml`
contained an unpinned `actions/github-script@v9` step, whereas all other
`actions/github-script` steps across repository workflows and the FullStack Template
baseline are SHA-pinned to
`3a2844b7e9c422d3c10d287c895573f7108da1b3 # v9.0.0`.
### Action
Verify that all third-party and GitHub-provided script steps in composite actions
maintain explicit commit SHAs matching the repository security baseline.

## 2026-09-18 — GitHub Project Security Alerts Eventual Consistency Retry
### Learning
Eventual consistency in GitHub Project item creation can throw 'Content already
exists in this project' when an item was added concurrently or index propagation is
delayed. Exponential backoff retries in `findProjectItemIdEventually` prevent sync
job crashes.
### Action
Retain `findProjectItemIdEventually` in `sync-security-alerts.js` for all Project v2
item additions across FullStack Template downstream applications.
---

# Kira Retirement Record — 2026-10-17

**Status: RETIRED — Jules downstream infrastructure reconciler.** The owner retired Kris and Kira on 2026-10-17. Kira's weekly Friday schedules in MacroMapper and Notoli, and Kris's weekly Monday schedule in FullStackTemplate, were deleted in Jules and their removal verified. This record does not authorize recreating them.

## Responsibility and useful legacy

Kira reconciled applicable infrastructure from the current merged FullStackTemplate baseline into MacroMapper while preserving intentional local differences. Useful work is retained:

- [PR #139](https://github.com/VanillaIceCube/MacroMapper/pull/139) merged an immutable Action reference in security-alert aggregation.
- [PR #187](https://github.com/VanillaIceCube/MacroMapper/pull/187) merged Project v2 eventual-consistency retry handling and a regression-test change.
- [Task 16370558345669924791](https://jules.google.com/task/16370558345669924791) identified MacroMapper's generated-lockfile exclusion as an upstream candidate. The audit verified the difference at the cited repository snapshots. A useful finding counts even without a submitted PR.

The earlier journal entries above remain historical context, not an active scheduled-agent playbook. Retirement does not revert the accepted fixes.

## Why the recurring role was retired

[PR #164](https://github.com/VanillaIceCube/MacroMapper/pull/164) repeated #139's implementation and closed without merge. The wider workflow also accumulated three duplicate Notoli proposals and recurring capacity-only or already-aligned reports. Later Kira runs respected the revised PR limit, but the complete upstream-curation and downstream-reconciliation loop did not reliably complete the work it identified. Several Kris reports lacked reproducible sibling evidence.

The owner chose to retire both recurring agents for now and is considering a ticket-based alignment method. No open MacroMapper Krill PR remained at retirement; the three stale Notoli Kira PRs were closed without merge.

## Findings preserved as tickets

The verified remaining upstream opportunities are tracked in FullStackTemplate [#52](https://github.com/VanillaIceCube/FullStackTemplate/issues/52) (immutable Action references), [#69](https://github.com/VanillaIceCube/FullStackTemplate/issues/69) (review-verdict failure gates), [#214](https://github.com/VanillaIceCube/FullStackTemplate/issues/214) (generated-lockfile diff filtering), and [#215](https://github.com/VanillaIceCube/FullStackTemplate/issues/215) (bounded human review discussion). Existing canonical tickets were reused where available.

Future maintenance should start from explicit, deduplicated issues and current file evidence, with separately reviewed implementation PRs. Preserve the stronger local behavior, independent security gates, and product-specific configuration. This record does not create replacement automation or itself control external Jules scheduling.
