# 🦦 Otto's Journal — Reusable Backlog Management Knowledge

## 2026-09-21 — Recurring Downstream Agent PR Deduplication and Patch Comparison
### Learning
Scheduled runs of recurring downstream agents (such as Kira or Marty) can produce
duplicate pull requests (e.g. Kira PR #164 duplicating PR #139 for security-alert
action SHA pinning) when an earlier PR remains open across audit cycles. Comparing
exact commit patch diffs across open agent PRs reliably distinguishes true duplicate
implementation from distinct modular work.
### Action
In daily audits, before classifying active PRs as protected distinct implementations,
inventory all open agent PRs and compare changed files and commit diffs. Identify
duplicate PRs and surface them under Attention Needed for human review or safe
closure.

---

# Otto Retirement Record — 2026-10-17

**Status: RETIRED — Google Jules daily backlog and Project organizer.** This entry records the historical decision; it is not an instruction to restart Otto and does not disable an external Jules schedule by itself.

## Original responsibility
Otto was intended to audit MacroMapper issues, GitHub Project metadata, dependencies, active specialist PRs, and repository backlog hygiene. It was expected to correct verified organizational problems without disrupting concurrent feature development.

## Why it was retired
1. **Independent audit runs duplicated work.** PRs [#118](https://github.com/VanillaIceCube/MacroMapper/pull/118) and [#119](https://github.com/VanillaIceCube/MacroMapper/pull/119) originated from separate Jules tasks but added nearly identical Otto journals from the same base. [Issue #124](https://github.com/VanillaIceCube/MacroMapper/issues/124) documents the collision, an unchanged-tree retry commit, and a probable externally owned scheduler trigger.
2. **The proposed fix did not land as an operational control.** [PR #125](https://github.com/VanillaIceCube/MacroMapper/pull/125) documented one-PR-per-period and unchanged-tree guards but was closed without merge; it did not implement the external scheduler. Issue #124 remained open at retirement.
3. **Routine audits often produced documentation instead of backlog corrections.** [PR #135](https://github.com/VanillaIceCube/MacroMapper/pull/135) reviewed 13 issues and three active PRs while reporting zero issue updates, metadata corrections, closures, or dependencies added, yet opened a journal PR.
4. **Later improvements were valuable but limited.** [PR #194](https://github.com/VanillaIceCube/MacroMapper/pull/194) (merged) documented how to compare repeated agent PR patches after identifying Kira [#164](https://github.com/VanillaIceCube/MacroMapper/pull/164) versus [#139](https://github.com/VanillaIceCube/MacroMapper/pull/139); that same report recorded zero duplicate PRs automatically resolved and zero issue/Project updates. Learning was recorded, but recurrent housekeeping remained mostly reporting rather than action.
5. **The September Otto reset did not make the three-repository workflow consistently worthwhile.** The original queue was retired and the prompt tightened; subsequent cross-repository runs still generated no-diff PRs, documented in the companion Notoli and FullStackTemplate retirement records.

## Decision and legacy
Retire Otto's recurring Jules backlog-audit role, not GitHub Projects or all specialized agents. Preserve this file's earlier historical lessons for context only. Do not resume automatic daily audit/journal PR creation based on this entry. Future issue and PR hygiene should use scoped, evidence-backed requests with explicit mutation verification and no PR on a no-change result. The actual external Jules schedule/configuration must be disabled separately.
