# MacroMapper product vision

## Product promise

MacroMapper is a personal nutrition and activity tracker for people who want a
fast, understandable daily record of what they ate and how it relates to their
goals. Users can enter meals manually or describe them in natural language.
MacroMapper uses GPT and source-aware research to propose an estimated meal,
shows its components and nutrients for review, and saves the user's accepted
version to their diary.

MacroMapper is inspired by the quick diary experience of MyFitnessPal. Its
distinction is transparency: an estimate explains what it contains, the source
or confidence behind it, and what the user may edit.

## Initial product boundary

MacroMapper is personal-use first. Accounts, meal histories, activity records,
goals, and saved custom foods belong to individual users. Household, social,
and coaching collaboration are outside the initial release.

MacroMapper records nutrition and activity information; it does not diagnose,
treat, or manage medical conditions, provide clinical guidance, or prescribe
diets. It may calculate and display user-editable tracking targets, but must
not present them as medical or professional advice.

## Core experience

1. A user sets a nutrition target manually or receives an editable starting
   calculation from basic profile inputs and normal non-exercise activity.
2. They log food by selecting Food Items, creating an entry manually, or
   describing a meal such as "a Double-Double from In-N-Out."
3. MacroMapper searches the catalog first. When it needs an estimate, it
   proposes Food Items, components, quantities, nutrient totals, sources, and
   confidence for the user to review.
4. The user can remove cheese, change portions, add foods, and save the exact
   meal they ate. The saved Meal Entry retains its own nutrient snapshot.
5. The diary and trends show food calories, nutrients, activity calories, net
   calories, and progress against the user's goals.

## Food data principles

### One Food Item concept

A Food Item may be consumed directly or be composed from other Food Items. A
lettuce serving is a Food Item. A restaurant burger is also a Food Item whose
component rows may include bun, patties, lettuce, tomato, cheese, and spread.
This avoids a separate, less reusable ingredient type.

Each Food Item needs a serving definition, nutrients, provenance, confidence,
and versioned definition. The launch nutrient set is calories, protein,
carbohydrates, fat, fiber, sugar, sodium, and cholesterol, with micronutrients
recorded whenever source data is available. Unknown nutrients are unavailable,
not zero.

### Shared and personal catalog records

Catalog records have one of three trust states:

- **Official / verified:** backed by a brand or restaurant's published label or
  nutrition page.
- **Community or AI estimate:** reusable, source-linked estimate that has not
  yet been verified.
- **Personal:** private user-created food, recipe, or frequent variation.

MacroMapper must search the shared catalog before creating a new estimate. A
user's modification to a meal is private: removing cheese from one meal never
redefines the canonical shared restaurant item. Candidate shared entries should
be deduplicated, checked for nutrient/component consistency, and reviewed or
verified before promotion to the official state.

## Activity and calorie accounting

The baseline calorie target represents normal daily life excluding workouts and
sports that the user plans to log. The user selects the baseline that describes
their non-exercise life, such as desk work, being on their feet, or physical
work. Basketball, gym sessions, and unusual travel walking are logged as
separate activity entries with editable date, duration, intensity, and
estimated calories burned.

For each day MacroMapper shows:

```text
baseline calorie target
+ activities marked "count toward today's budget"
= activity-adjusted calorie budget

food calories - activity-adjusted calorie budget = daily balance
```

Activity energy is an estimate and should always be labeled accordingly. A
per-entry toggle lets users record an activity without automatically adding its
calories to the day's food budget. A future simplicity setting may let users
choose a target that already includes regular exercise; that setting must not
double-count logged activities.

## MVP scope

- Individual accounts and a dated daily diary.
- Manual food logging and editable custom foods.
- Food Item search and composite component editing.
- Text-based GPT meal proposals with catalog-first lookup, sources, confidence,
  and required review before saving.
- Calories, protein, carbohydrates, fat, fiber, sugar, sodium, cholesterol,
  and available micronutrients.
- Manual and calculated/editable nutrition targets.
- Activity presets, free-text activity logging, and an activity-adjusted budget.
- Daily, weekly, and monthly trends for intake, macro adherence, activity, net
  calories, meal timing, and frequently logged foods.

## Deferred work

- Photo recognition and barcode scanning.
- Weight tracking.
- Social, household, coach, and sharing features.
- Clinical, medical, or prescriptive dietary recommendations.

## Delivery sequence

1. Build the Food Item/composite catalog and nutrition data model.
2. Build the private editable meal diary with durable meal snapshots.
3. Add catalog-first GPT estimation and a review-before-save flow.
4. Add nutrition goals and trend reporting.
5. Add exceptional-activity logging and activity-adjusted budgets.
6. Add catalog verification, review, and promotion workflows.

The detailed, prioritized work is tracked on the
[MacroMapper Project](https://github.com/users/VanillaIceCube/projects/11).
