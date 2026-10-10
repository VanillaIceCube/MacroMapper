# 🦦 Otto's Journal — Reusable Backlog Management Knowledge

## 2026-09-21 - Recurring Downstream Agent PR Deduplication and Patch Comparison
**Learning:** Scheduled runs of recurring downstream agents (such as Kira or Marty) can produce duplicate pull requests (e.g. Kira PR #164 duplicating PR #139 for security-alert action SHA pinning) when an earlier PR remains open across audit cycles. Comparing exact commit patch diffs across open agent PRs reliably distinguishes true duplicate implementation from distinct modular work.
**Action:** In daily audits, before classifying active PRs as protected distinct implementations, inventory all open agent PRs and compare changed files and commit diffs. Identify duplicate PRs and surface them under Attention Needed for human review or safe closure.
