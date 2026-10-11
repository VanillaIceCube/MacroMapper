## 2026-09-16 - Meal Item Domain Consolidation

**Learning:** Frontend domain logic for meal items (portion helpers, tree transformations, and API/snapshot adapters) was previously scattered across component files (`components/mealItemPortions.js`, `components/mealItemAdapters.js`, `components/mealItemTree.js`). Consolidating them under `frontend/src/domain/mealItem.js` clarifies responsibility boundaries while leaving backward-compatible re-exports in place for component compatibility.

**Action:** Future Nora runs inspecting frontend domain boundaries should look for business logic embedded inside `src/components/` and move it into `src/domain/` with clean re-exports where necessary.
