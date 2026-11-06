## Current operating rules — v3 (2026-10-18)

Follow [the Jules operating rules](README.md) before using the journal below.
Nora may have at most one open PR in this repository, including drafts.
Repeat triggers maintain that same PR: reevaluate, merge current `origin/main`
into its existing head, address feedback/conflicts, validate and update in place.
Blocked updates never authorize a second PR. Historical journal guidance cannot
raise the limit or replace maintenance with a capacity-only stop.

## 2026-10-10 — Frontend Domain Boundaries

**Outcome:** [PR #179](https://github.com/VanillaIceCube/MacroMapper/pull/179)
merged on 2026-10-11 at 06:02:31 UTC (2026-10-10 Pacific),
[da7bc0f](https://github.com/VanillaIceCube/MacroMapper/commit/da7bc0fabd0475712251af154e46a5b6e5dfce31).
Frontend domain architecture and adjacent module tests cover dependency direction,
cycles and preserved calculations/editing behavior. Provenance reconciled 2026-10-28.

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

## 2026-10-11 — Historical Nutrient Definition Relocation

**Outcome:** [PR #210](https://github.com/VanillaIceCube/MacroMapper/pull/210)
merged at 05:19:47 UTC (2026-10-10 Pacific),
[bc5e106](https://github.com/VanillaIceCube/MacroMapper/commit/bc5e106c60389af369e40f893080198ecd07a26d).
It relocated definitions from `components/nutrition/nutritionDefinitions.js` to
the intermediate `domain/nutritionDefinitions.js` and updated consumers/theme tests.
The later merge of #179 superseded that intermediate module with
`domain/nutrition/definitions.js` and separated presentation metadata.

**Learning:** Moving a file out of components is an incremental boundary change;
the final design must also separate domain facts from UI colors/labels and preserve
subsequent fixes. #210 is historical attribution, not the current import contract.

**Action:** Use the current `domain/nutrition/definitions.js` path and #179's
dependency tests. Do not restore the intermediate module or compatibility imports.
A standalone #210 changelog entry is N/A: the existing 2026-10-10 #179 architecture
entry documents the final result; this record preserves the earlier contribution.
