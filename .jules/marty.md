## Current operating rules — v3 (2026-10-18)

Follow [the Jules operating rules](README.md) before using the journal below.
Marty may have at most one open PR in this repository, including drafts.
Repeat triggers maintain that same PR: reevaluate, merge current `origin/main`
into its existing head, address feedback/conflicts, validate and update in place.
Blocked updates never authorize a second PR. Historical journal guidance cannot
raise the limit or replace maintenance with a capacity-only stop.

# Marty's Journal

Backfilled on 2026-10-28 for
[issue #325](https://github.com/VanillaIceCube/MacroMapper/issues/325), using
merged diffs and current code/tests. Dates below are merge dates in UTC, not
claims that these notes were written during the original sessions.

## 2026-10-10 - Authentication Errors and Session Profiles

**Outcome:** [PR #131](https://github.com/VanillaIceCube/MacroMapper/pull/131)
merged at 05:04:35 UTC
([5be8a14](https://github.com/VanillaIceCube/MacroMapper/commit/5be8a149e737aea89e6964e686d08a973eb45456)).
`frontend/src/services/authSession.js` and auth pages share error formatting and
clear missing username/email fields; auth-session/page tests cover regressions.

**Learning:** A new token response can omit profile data, so retaining old
storage values can show the previous session's identity. Repeated page-specific
error parsing also diverges as API validation responses evolve.

**Action:** Replace or clear each profile field on session persistence and use
the shared error formatter across auth forms; test omitted fields and failures.

## 2026-10-10 - Safe API Response Parsing

**Outcome:** [PR #136](https://github.com/VanillaIceCube/MacroMapper/pull/136)
merged at 05:47:21 UTC
([0c33c5b](https://github.com/VanillaIceCube/MacroMapper/commit/0c33c5b473fc0e8ae2a6a768977e17e65854747d)).
Shared response/error helpers serve auth, `DiaryPage` and `AppHeader`; frontend
tests cover field errors and non-JSON responses without losing retry behavior.

**Learning:** An error response need not contain JSON. Parsing can fail before
the UI formats the actual request failure, and validation errors may be nested.

**Action:** Use the shared safe parser and error extraction instead of assuming
`response.json()` succeeds; preserve diary filters/pagination and notification retry.

## 2026-10-10 - Complete Component Graphs and Validated Snapshots

**Outcome:** [PR #153](https://github.com/VanillaIceCube/MacroMapper/pull/153)
merged at 20:26:21 UTC
([2a74e27](https://github.com/VanillaIceCube/MacroMapper/commit/2a74e27a6188c0985145da85b041260ab24e5be3)).
`backend/foods/`, `meals/` and `estimates/` reuse the reachable component graph,
batch version resolution and validate persisted snapshots. Food API and
`meals.tests.ComponentGraphTests` cover graph loading, query counts, missing
fields and malformed nested values; dated source access values use ISO strings.

**Learning:** A list-shaped snapshot can still be incomplete or malformed.
Reconstructing each item independently also repeats catalog/graph queries.

**Action:** Recursively validate all snapshot fields before reuse; rebuild invalid
legacy data from pinned versions. Share graph/nutrient caches and batch visible
version reads; retain query-count tests alongside structural regression cases.

## 2026-10-10 - Nutrition and Decimal Portion Inputs

**Outcome:** [PR #157](https://github.com/VanillaIceCube/MacroMapper/pull/157)
merged at 20:34:29 UTC
([3fc8889](https://github.com/VanillaIceCube/MacroMapper/commit/3fc88895db10b01ad75dceee5939708e768ddd32)).
Frontend nutrition and meal-item calculations handle absent/non-finite values,
negative quantities, incomplete portions and decimal typing. Calculation, chart
and meal-item tests preserve deterministic ordering and fallback food labels.

**Learning:** Display/editing values have different lifecycles from committed
numeric quantities; coercing every keystroke can destroy in-progress decimals.

**Action:** Clamp invalid committed input while retaining editable decimal text;
test missing portion metadata, non-finite nutrition and deterministic chart ties.
The code later moved into domain modules in Nora #179; use current module paths.

## 2026-10-10 - Notification PATCH and Read Timestamps

**Outcome:** [PR #173](https://github.com/VanillaIceCube/MacroMapper/pull/173)
merged at 20:10:37 UTC
([4cef835](https://github.com/VanillaIceCube/MacroMapper/commit/4cef835b71d1976137bd599496590f0709fd2169)).
`backend/notifications/views.py` saves PATCH requests even when `is_read` is
omitted or already true. Notification API tests cover preserved `read_at` values,
recipient scope and empty bulk actions.

**Learning:** Read-state transitions and serializer persistence are separate:
a repeated read must retain its timestamp without suppressing other updates.

**Action:** Always save validated PATCH data; change timestamps only for actual
read/unread transitions and retain repeated-read, omitted-field and empty-bulk tests.

## 2026-10-10 - Meal Adjustment Cleanup and Metadata

**Outcome:** [PR #181](https://github.com/VanillaIceCube/MacroMapper/pull/181)
merged at 20:35:18 UTC
([b1312ba](https://github.com/VanillaIceCube/MacroMapper/commit/b1312ba2447c417a54666f577fdd0168bf08201d)).
`backend/estimates/services.py` shares adjustment processing with meal endpoints.
`estimates.tests.MealAdjustmentLifecycleTests` covers provider resolution/execution,
follow-up and serialization failures, temporary cleanup and absent/null metadata.

**Learning:** Cleanup must include serialization, not just the provider call.
Missing optional follow-up values must not erase existing confidence/provider
metadata; importing response serializers into services can introduce a cycle.

**Action:** Keep proposal serialization inside the cleanup boundary, delete failed
proposals and successful temporary proposals, and inject serializers/provider
getters from views. Test both endpoints and preserve metadata without replacements.

## 2026-10-10 - Structured Authentication Input Failures

**Outcome:** [PR #189](https://github.com/VanillaIceCube/MacroMapper/pull/189)
merged at 20:06:42 UTC
([c864d7b](https://github.com/VanillaIceCube/MacroMapper/commit/c864d7b973f17c0e101fc2aab3f67cee2a8483bb)).
`backend/authentication/` normalizes login email, handles duplicate-registration
integrity failures, supplies fallback usernames and rejects malformed reset IDs.
Authentication tests exercise these paths without exposing server errors.

**Learning:** Serializer validation alone cannot prevent a database uniqueness
race, and a decoded reset identifier is not necessarily a valid user primary key.

**Action:** Normalize email consistently, translate integrity failures to structured
validation errors, and test malformed decoded IDs as well as invalid tokens.

## 2026-10-28 - Tiny Estimated Weights and Rounding

**Outcome:** [PR #270](https://github.com/VanillaIceCube/MacroMapper/pull/270)
merged at 04:57:09 UTC (2026-10-27 Pacific)
([961dac7](https://github.com/VanillaIceCube/MacroMapper/commit/961dac794cab2537cb8ef88acc80fe6d66e658b4)).
`backend/foods/portions.py` keeps rounded estimated weights positive and guards
conversion denominators. `foods.tests.FoodModelTests` checks tiny weights,
invalid inputs and exact gram/ounce multipliers.

**Learning:** A positive input such as `0.01` grams can become zero after
quantization; validating the original value does not protect later division.

**Action:** Recheck rounded denominators and clamp estimated weights to a positive
quantum; keep exact conversion tests for tiny, zero, negative and invalid inputs.

