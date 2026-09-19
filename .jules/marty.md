# Marty's Journal 🦀

## 2026-08-31 - Safe Nutrition Calculations and Chart Summaries
**Learning:** Frontend nutrition calculation utilities (`nutritionMath.js`) process item data from various sources (catalog API, proposal revisions, user inputs) where nutrients or servings may be null, missing, string, or non-finite (`NaN`). Defensive numeric checks (`Number.isFinite`) and fallback key/name resolution prevent unstable sorting and `NaN` propagation in macro chart rendering.
**Action:** Future runs touching nutrition components or math utilities should rely on `nutritionMath.js` helpers and maintain strict `Number.isFinite` checks for all calculations.
