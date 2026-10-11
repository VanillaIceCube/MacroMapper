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
