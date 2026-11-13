# Meal interpretation and portion semantics

One draft tree is the calculation basis for AI estimates, manual review and saved
meals. Each node has a unique stable key, immutable catalog identity/version
references, a base serving definition and an instance `servings` multiplier.
Composite nutrients ordinarily sum children multiplied by each child's local
servings. Direct fields with matching official source verification retain their
verified parent values; inferred component totals do not replace those fields.
Consumed nutrients multiply that result by the parent's servings once.

## Recipes and corrections

Recipe descriptions are interpreted as a whole, including when some ingredients
already exist in the catalog. Full recipe ingredient quantities remain children
of the prepared food. The provider's optional `recipe_fraction` becomes the
top-level recipe's servings; it requires a composite with one full recipe as its
basis. For 75% of chilaquiles plus two chicken breasts and yogurt, the recipe is
0.75, chicken is 2 and yogurt keeps its separately described quantity. The
provider must not pre-scale recipe children. Nutrition normalization and rollup
remain deterministic after interpretation.

Follow-ups support targeted operations on exact existing keys:

- `reparentings`: move a node to an existing composite (`parent_key`) or meal
  level (`null`). Local ingredient quantities, IDs and nutrition are retained.
- `fraction_updates`: set an absolute recipe fraction, not a multiplier of its
  previous fraction. `excluded_keys` protects separate foods from quantity and
  size operations in that response. Excluded children must first be moved out.
- `serving_updates`: change an existing node's absolute quantity.
- `portion_updates`: select an existing portion option. Natural size changes
  preserve count; measurement conversions preserve consumed weight/nutrition.
- `remove_keys`: remove an existing subtree. New foods still require the
  existing catalog/publication validation path.

Moves do not recreate ingredients. Ingredient-tree changes invalidate parent
verification before recalculation; consumed-fraction-only changes preserve
per-serving evidence and official values. Cycles, unknown keys, duplicate node keys,
leaf destinations, excessive depth/cardinality and conflicting fraction/child
quantity edits fail atomically with actionable validation. Removing the final
child clears the former composite's nutrition rather than retaining stale
totals. A local recipe quantity stays local when moved beneath a partially
consumed recipe; its consumed contribution then follows that recipe's fraction.

The AI remains responsible for resolving natural-language references and
choosing the correct keys. The existing best-effort conversational policy is
retained; ambiguous natural language is not a guarantee of a clarification
dialog. Unsupported operations fail visibly. No paid meal-model call is required
for the synthetic regression suite.

## Canonical names and food-specific portions

Generic leading size wording is removed from food identity; variety/color stays
in the name. Branded product names and marketed size/SKU distinctions are kept.
`natural_servings` is an optional list of `{key, label, weight_grams}` definitions
for that particular food version. Choices appear as `size:<key>` portion options
with multipliers derived from each gram weight divided by the base serving's
gram weight. No universal Small/Medium/Large gram weights are assumed. A requested size is
reused from the catalog only when a food-specific choice or the declared base
serving represents that size. Otherwise the request remains unmatched for
estimation; an unsupported Large request cannot silently reuse a Small base.
Serialized size choices survive follow-up catalog lookup without requiring size
words in the canonical food name or base label.

For two Small apples, selecting Large keeps the count at two and changes the
base-serving multiplier. Selecting grams converts the displayed quantity while
preserving consumed nutrition. When food-specific sizes are unavailable, the
existing natural base serving and grams/ounces options remain the fallback.
Natural portion definitions are estimated unless their source/provenance says
otherwise; this change does not introduce a verified food-weight database.

Serving changes affect the draft instance; they do not mutate shared catalog
versions. Meals migration `0005_mealitem_selected_portion_key` adds a defaulted
selection field without changing historical quantities or nutrients. New
component snapshots retain selected portion keys. Old snapshots use their
original base-serving display. The food schema and opt-in legacy duplicate
cleanup procedure are documented in [CANONICAL-FOODS.md](CANONICAL-FOODS.md).
