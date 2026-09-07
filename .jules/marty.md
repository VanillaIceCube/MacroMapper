# Marty's Journal

## 2026-09-07 - Food Component Tree Bulk Loading **Learning:** Serializing `FoodItem` models with composite version components requires passing `component_map` (built via `build_component_map`) in serializer context to avoid N+1 database queries across nested child components and source references. **Action:** Any view or service serializing `FoodItemVersion` or `FoodComponent` trees should pass `component_map` in context or use `build_component_map` when loading current definitions.
