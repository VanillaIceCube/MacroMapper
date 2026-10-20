## Current operating rules — v3.1 (2026-10-20)

Follow [the Jules operating rules](README.md) before using the journal below.
Nora may have at most one open PR in this repository, including drafts.
Ownership requires branch `jules/nora/*` or explicit Nora PR attribution;
Dependabot, human, and other-persona PRs do not consume Nora's slot.
Repeat triggers maintain the canonical or existing PR: reevaluate, merge `origin/main`
into its head, address feedback/conflicts, validate, and update in place.
When multiple legacy PRs exist, maintain the canonical/oldest PR and report excess.
Blocked updates never authorize a second PR or duplicate publication.

## 2026-10-10 — Frontend Domain Boundaries

### Learning

Meal-item portions, adapters, and tree operations belong in focused modules under
`frontend/src/domain/mealItem/`. Shared nutrition definitions and calculations
belong under `frontend/src/domain/nutrition/`. Domain logic must not import from
UI components; nutrient display metadata and chart decoration stay in the
presentation layer. The original consolidation proposal was rebuilt from current
`main` to preserve later validation fixes and cleanup.

### Action

Use current behavior as the source of truth during architectural refactors.
Migrate consumers directly and remove obsolete wrappers when no consumers remain.
Keep numeric formatting shared through neutral utilities where both domain
labels and UI displays use it, and verify dependency direction, cycles, and
existing functionality with the frontend tests.
