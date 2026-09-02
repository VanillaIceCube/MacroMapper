# Marty's Journal

## 2026-03-31 - Builder adjustment provider mocking **Learning:** Estimation provider mocks patched at `estimates.views.get_estimation_provider` or `meals.views.get_estimation_provider` require passing `provider` through service functions like `process_builder_adjustment` so existing view tests continue matching provider mocks seamlessly. **Action:** Future service refactorings that consume estimation providers should accept an optional `provider=None` kwarg defaulting to `get_estimation_provider()`.
