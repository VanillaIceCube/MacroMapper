# Estimates test preservation: PR #305

Audit date: 2026-11-11.

Compared the original `backend/estimates/tests.py` at PR base
`4e5f70b12df7a62486b39c4e3781013c3ef15a74` and updated main
`04eecfd373c836de37543bbcdc386c9a6a69adc7` against the split `backend/estimates/tests/`
package. Both baselines have the same 59 tests.

Python AST comparison (`ast.dump(..., include_attributes=False)`) keyed every
function by class/method name, including non-test methods and top-level helpers.
All 65 functions match exactly: 59 tests, three shared builders, two setup
methods and one assertion helper. No missing, added, renamed or intentionally
modified tests or assertions.
Class bases, keywords and decorators match too, including provider
`override_settings`. Only imports and module placement changed. There are no
teardown methods or other executable class-level statements to relocate.

Relative model/provider imports now traverse one extra package level. Helpers
are imported from `.helpers`; mocks still patch the production lookup sites
(`estimates.services`, `estimates.views`, `estimates.serializers`, or provider
client objects), so restructuring does not change what they replace. Normal discovery
must reach all four `test_*.py` modules through `tests/__init__.py`.

Django suite construction confirms each original class/method is discovered
exactly once under all three labels: `backend` (226 methods), `estimates` (68),
and `estimates.tests` (59). This verifies preservation independently of pass/fail
results and catches exclusions or duplicate collection.

The inventory below records test methods, not subtest iterations. An instrumented
`unittest.TextTestResult.addSubTest` run of `estimates.tests` passed all 59 methods
and recorded 17 successful subtests across seven parent methods (69 leaf cases
if each subtest replaces its parent in the count: `59 - 7 + 17`). The earlier
claim of 68 executions including subtests is not the measured subtest count.
All original subtest loops and assertions are preserved by the AST comparison.

The complete `estimates` app discovers 68 methods: these 59 plus eight existing
timeout/transaction tests in `test_timeouts.py` and one Linux-only Gunicorn test
in `test_runtime.py`. Those separate modules are unchanged; the Gunicorn test
is skipped on Windows and must run in Linux CI. `estimates.tests` and `estimates`
are therefore different suite labels, both verified during this refactor.

Integration with newer main required one fixture-import update in
`macromapper_mcp/tests.py`: `estimates.tests.helpers.ai_estimate` replaces
`estimates.tests.ai_estimate`. The MCP-enabled suite passed 34 tests with one
expected disabled-profile-only skip. No fixture behavior changed.

Full backend discovery from the repository root needs the explicit `backend`
directory label (`python backend/manage.py test backend`); the old unlabelled
command discovered zero tests. Running from `backend` with `python manage.py test`
also discovers the complete suite and matches CI. Documentation now records both.

| Module | Test class | Methods |
| --- | --- | ---: |
| `test_adjustments.py` | `MealAdjustmentLifecycleTests` | 6 |
| `test_admin.py` | `MealProposalAdminTests` | 1 |
| `test_proposals.py` | `MealProposalApiTests` | 38 |
| `test_provider.py` | `OpenAIProviderTests` | 14 |

## Original-to-package inventory

Each method below exists under the same class name in both baselines and the
new module. No coverage was intentionally removed or changed.

### test_adjustments.py

Class: `MealAdjustmentLifecycleTests`.

- `test_provider_failure_cleans_up_both_adjustment_endpoints`
- `test_provider_resolution_failure_cleans_up_both_adjustment_endpoints`
- `test_follow_up_processing_failure_cleans_up_both_adjustment_endpoints`
- `test_serialization_failure_cleans_up_both_adjustment_endpoints`
- `test_missing_follow_up_fields_preserve_confidence_and_provider_metadata`
- `test_absent_follow_up_collections_leave_proposal_unchanged`

### test_admin.py

Class: `MealProposalAdminTests`.

- `test_standalone_revision_admin_is_immutable`

### test_proposals.py

Class: `MealProposalApiTests`.

- `test_catalog_match_bypasses_provider_and_retains_official_source`
- `test_personal_catalog_match_retains_user_entered_source`
- `test_catalog_resolver_combines_typoed_composite_and_joined_food_with_quantity`
- `test_catalog_resolver_applies_quantity_before_the_provider_name`
- `test_catalog_resolver_handles_heavily_typoed_provider_and_food`
- `test_ai_intents_resolve_same_food_from_two_providers`
- `test_ai_intents_estimate_only_the_provider_food_missing_from_catalog`
- `test_mixed_catalog_and_ai_items_keep_same_name_from_different_providers`
- `test_ai_intent_does_not_match_fries_to_fried_chicken`
- `test_catalog_resolver_uses_ai_only_for_unmatched_foods`
- `test_partial_catalog_match_sends_complete_food_clause_to_ai`
- `test_builder_adjustment_can_create_a_meal_from_no_foods`
- `test_builder_adjustment_preserves_catalog_foods_and_applies_quantity_changes`
- `test_builder_adjustment_accepts_removed_catalog_components`
- `test_builder_adjustment_cleans_up_proposal_on_unexpected_exception`
- `test_follow_up_addition_reuses_a_matching_catalog_food`
- `test_ai_generated_proposal_round_trips_through_follow_up_validation`
- `test_follow_up_persists_reviewed_fields_when_no_food_change_applies`
- `test_unsafe_provider_catalog_metadata_is_rejected_before_publication`
- `test_unsafe_provider_source_url_is_rejected_before_publication`
- `test_overlong_provider_source_url_is_rejected_before_publication`
- `test_duplicate_provider_source_urls_are_rejected_before_publication`
- `test_catalog_proposal_keys_include_the_full_component_path`
- `test_ai_proposal_can_be_edited_and_accepted_as_private_snapshot`
- `test_ai_proposal_rounds_provider_values_to_storage_precision`
- `test_ai_proposal_accepts_reviewed_component_nutrients`
- `test_ai_proposal_rolls_up_known_nutrients_when_a_component_is_unknown`
- `test_catalog_nutrient_adjustment_creates_a_personal_copy`
- `test_initial_ai_estimate_becomes_shared_and_is_reused_by_another_user`
- `test_unmodified_ai_estimate_acceptance_reuses_shared_version`
- `test_multiple_servings_are_multiplied_exactly_once_when_accepted`
- `test_equivalent_ai_outputs_are_deduplicated`
- `test_proposal_revisions_preserve_generated_reviewed_and_accepted_values`
- `test_edited_draft_can_be_deleted_without_removing_shared_base`
- `test_proposals_are_owner_scoped`
- `test_proposal_edits_reject_non_finite_numbers`
- `test_proposal_edits_cannot_inject_untrusted_portion_options`
- `test_provider_failure_returns_safe_service_unavailable`

### test_provider.py

Class: `OpenAIProviderTests`.

- `test_source_url_schema_is_supported_and_still_validated`
- `test_provider_extracts_catalog_search_intents_without_web_search`
- `test_provider_generates_a_meal_name_without_web_search`
- `test_provider_uses_web_search_structured_output_and_retains_metadata`
- `test_provider_returns_a_refreshed_follow_up_meal_name`
- `test_provider_normalizes_declared_total_nutrients_to_one_base_serving`
- `test_provider_detects_implausible_totals_even_when_basis_is_mislabeled`
- `test_provider_keeps_valid_per_serving_nutrients_for_multiple_servings`
- `test_provider_defaults_beverages_to_natural_containers`
- `test_provider_defaults_nested_components_to_measurement_units`
- `test_prompt_forbids_medical_advice`
- `test_prompt_anchors_grams_to_a_concise_stable_serving`
- `test_prompt_requires_atomic_meal_components`
- `test_prompt_keeps_shared_food_fields_free_of_personal_context`
