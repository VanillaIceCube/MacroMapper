# Changelog
All notable changes to this project are documented in this file.

## 2026-08-30

### Added

- Add combinable catalog scope, provider, provenance, and source-aware search
  filters to Map Your Meal, with visible active filters and add confirmation.

### Fixed

- Preserve personal-food provenance, validated meal dates, and intentionally
  removed recipe components throughout AI-adjusted meal drafts.
- Preserve reviewed meal dates and notes even when an AI follow-up produces no
  applicable food changes, and keep top-level catalog component serialization
  bulk-loaded.
- Preserve pinned food-version portion options when reopening saved meals.
- Ignore stale catalog responses when a newer food search has started.
- Allow AI adjustments to reuse archived food versions already pinned to the
  existing meal being edited.

### Changed

- Make AI Adjustments available while editing existing diary entries. AI
  changes remain a reviewable modal draft until the user saves the meal.
- Use one complete Map Your Meal draft for AI review, manual mapping, and
  existing-meal edits. All three paths now expose the same catalog, nutrition,
  portion, and nested-component controls, while existing meals still update in
  place.

## 2026-08-29

### Added

- Rotate the Map it with AI input placeholder across 100 examples covering
  everyday meals, restaurants, cuisines, quantities, drinks, substitutions,
  leftovers, and uncertain descriptions.

### Fixed

- Keep broad catalog searches responsive by rendering at most the first 25
  matches.

### Changed

- Load the 20 most recently created visible foods when Map Your Meal opens,
  while keeping broader catalog searches explicitly limited in the interface.
- Rename the Add meal modal to Map Your Meal.
- Rename the related backend meal-adjustment serializer and field to Map Your Meal.
- Generate blank meal names from the selected foods when a meal is saved, with
  sequential `Meal-00`, `Meal-01`, and `Meal-02` names when the LLM is unavailable.
- Use Add meal as the single meal-building surface. Estimate meal first gathers a
  description and creates an initial estimate, then transitions to Add meal in the
  same dialog; Add manually opens Add meal directly.
- Make AI Adjustments available for both estimated and manually assembled meals
  in the unified Add meal builder, with generalized adjustment naming throughout
  the current interface.
- Hide catalog foods after they are added to a meal and prevent duplicate
  additions until the existing item is removed.
- Extract meal-item editing into one shared component for all Add meal items,
  including the same responsive layout, nutrition editing,
  count/unit controls, details menu, removal, and recursive component breakdown.
- Consolidate meal nutrition definitions, calculations, item adapters, builder
  tree operations, macro split charts, and calorie-contribution charts into
  shared modules used by Add meal and the diary dashboard.
- Render each diary meal's Macro Balance with the shared macro-calorie component
  and use the same title, typography, number formatting, legend alignment, and
  bordered container across the meal log, Add meal builder, and daily dashboard.
- Place the meal-log food table and Macro Balance container in the same aligned
  grid row and move Foods & servings into the table header to remove the
  redundant label above them.
- Include nutrient values and nested details in catalog component payloads and
  saved component snapshots, and hydrate legacy snapshots so composite foods and
  their components no longer show blank nutrition.
- Show catalog provenance, confidence, and company/provider metadata as compact
  tags above each food result.
- Add an AI-style estimate-details action to catalog foods for reviewing their
  metadata and supporting source links.

### Removed

- Remove personal-food creation from Map Your Meal; existing personal foods
  remain available through catalog search.

## 2026-08-24

### Added

- Included each user's original Adjust with AI follow-up request in the saved
  meal Context, while retaining AI result messages separately in revision history.

### Changed

- Redesigned manual meal entry as a responsive meal-building workflow that
  mirrors estimate review with editable meal details, catalog nutrition and
  provenance, portion-aware item controls, live meal totals and
  macro/component charts, personal-food creation, and protected unsaved drafts.
- Refreshed the concise meal title whenever Adjust with AI successfully changes
  an estimate, so additions and removals are reflected before diary acceptance.
- Vertically centered the Macro Balance visualization when the neighboring
  Calories by meal chart grows taller.
- Rebalanced the Daily Summary charts around a balanced macro-calorie panel with
  a larger full-card donut layout and a wider Calories by meal chart with
  two-line space for longer meal titles, compact vertically centered labels,
  thicker stacked bars, and whole-number macro-split values.

## 2026-08-23

### Added

- Added conversational AI follow-ups to meal-estimate review so users can add
  forgotten foods or request clear removals and serving corrections while
  preserving the current editable draft, provenance, and revision history.

### Fixed

- Preserved concise AI-generated meal titles for mixed catalog and estimated
  foods, using a brief company-and-food naming format instead of diary prose.
- Rolled up known daily nutrient values even when another saved food lacks that
  nutrient, and stopped rendering unknown daily values as zero.
- Resolved meal descriptions by complete food clause so partial fuzzy catalog
  matches cannot discard defining terms or be combined with unrelated AI
  fallback foods; unresolved clauses now retain shared provider context.
- Prevented conversational descriptions such as fries from two different
  restaurants from bypassing existing catalog foods and creating duplicate AI
  estimates.
- Added a server-side publication boundary for provider-derived shared foods so
  only allowlisted, normalized, source-validated catalog fields can be made
  globally visible; unsafe or instruction-like metadata is rejected atomically.
- Kept meal review usable after an AI follow-up request fails by preserving the
  draft and request, showing a retryable error, and always unlocking the dialog.

### Changed

- Redesigned the meal diary as a Quick Logbook with date and nutrition
  summaries at the top, macro calorie-split and calories-by-meal charts, compact
  color-coded daily nutrient cards, parallel estimate/manual entry paths, and
  responsive meal ledger cards with food counts, daily calorie share, wider per-food
  macro-calorie, confidence, and provenance breakdowns, saved estimate confidence,
  serving context, per-meal macro donuts, and uniformly unshaded, outlined secondary
  nutrient totals without shortcut or method columns.
- Added structured AI food-intent extraction for descriptions the deterministic
  catalog path cannot fully resolve. Each provider-aware intent now searches the
  visible catalog before nutrition estimation, and AI follow-up additions use
  the same catalog-reuse step.
- Updated the shared MacroMapper logo asset to use the approved transparent,
  tightly cropped artwork across the application shell and install icons.

## 2026-08-22

### Added

- Added typo-tolerant multi-food catalog resolution that extracts quantities,
  prefers complete composites, groups duplicate identities, and sends only
  unmatched foods to GPT.
- Added deduplicated shared Food Items for initial AI estimates so later users
  can reuse the same sourced base definition without another model request.
- Added immutable generated, user-reviewed, and accepted proposal revisions,
  plus food-version lineage and retained AI provider/model metadata.
- Added a top-level calorie editor for composite foods that proportionally
  scales component quantities and all resulting macros in one adjustment.
- Made estimated calories, protein, carbohydrates, and fat editable through a
  per-item pencil control, with live parent, meal-total, and chart recalculation.
- Added consistently abbreviated portion-option dropdowns that pair a concise
  natural serving with appropriate weight or volume conversions for every
  GPT-estimated item.

### Fixed

- Prevented a partial catalog hit from dropping other requested foods or
  silently resetting their requested counts to one.
- Normalized GPT nutrient totals back to their declared base serving so a
  multi-serving estimate cannot multiply calories and macros twice.
- Required AI-generated composite foods to split identifiable ingredients into
  separate components instead of grouping multiple toppings into one row.
- Snapped AI-estimated component weights and liquid volumes to readable gram
  and fluid-ounce quantities instead of exposing conversion precision noise.
- Defaulted beverages to natural containers such as cans, glasses, bottles,
  and shakes while retaining standardized volume conversions in the dropdown.
- Preserved known macro totals when another component lacks that nutrient so
  carbohydrates and fats no longer disappear from meal breakdown charts.
- Removed redundant measured-serving labels such as `16 fl oz` from unit
  dropdowns when the equivalent standardized `fl oz` option is available.
- Reflowed meal-estimate food controls into a consistent responsive layout so
  quantity and unit/portion stay grouped while edit actions remain uncluttered.
- Rolled composite meal nutrition up from component values even when a parent
  food version contains stale or zero direct nutrient columns.
- Rounded GPT-estimated quantities, confidence scores, servings, and nutrients
  to their storage precision when saving an estimate to the diary.
- Rejected non-finite proposal numbers and replaced raw backend exception text
  with stable user-safe API errors.
- Generated nested catalog proposal keys from their full tree positions so
  reused composites remain uniquely editable.
- Removed the invalid root-level Docker Dependabot scan and documented that
  Docker dependency checks run from the backend and frontend directories.

### Changed

- Kept unchanged AI definitions shared while saving substantive nutrient or
  component edits as private user-modified versions derived from the shared
  base, with explicit adjusted-by-user attribution in the review UI.
- Reworked meal-estimate foods into aligned database-style rows with wrapping
  titles, compact count/unit controls, responsive mobile spacing, and secondary
  actions in overflow menus.
- Switched the default GPT meal-estimation model from GPT-5.5 to GPT-5.6
  Luna for substantially lower per-request cost.
- Defaulted nested meal components to grams for solids and fluid ounces for
  liquids while preserving natural portions for top-level foods.
- Replaced the original contour-map app mark with the selected compass-and-fork
  artwork across navigation, authentication, and installable app surfaces.
- Expanded meal-estimate review with a meal-level calorie summary, macro chart,
  and per-component protein, carbohydrate, and fat values that recalculate as
  servings and ingredients change.
- Added grams and calorie-share percentages to the meal summary chart legends
  so macro and component contributions can be compared at a glance.
- Centered the macro donut and legend as a bounded group so wide layouts keep
  the chart labels visually connected.
- Kept macro legend labels close to their values and collapsed estimated meal
  components by default for faster top-level scanning.
- Enlarged the macro donut responsively so it fills its summary card more
  evenly without stretching the legend.
- Simplified the meal-estimate review guidance to emphasize checking and
  adjusting nutrition values before saving.
- Separated calories from fat in the semantic nutrition palette by assigning
  calories to Midnight ink and carbohydrates to the higher-contrast dark
  Mineral token across cards, legends, and charts.
- Thickened component-calorie bars and stacked each row by its protein,
  carbohydrate, and fat calorie contribution while preserving total calorie
  length.
- Reserved consistent pencil/delete action space across estimated-food rows and
  tightened the spacing between those controls so nutrient cards stay aligned.

## 2026-08-16

### Added

- Added owner-scoped, catalog-first GPT meal proposals with structured OpenAI
  web research, persisted sources/confidence/provider metadata, editable
  component review, and acceptance into durable private diary snapshots.
- Added a responsive estimate-review interface with explicit official,
  catalog-estimate, and AI-estimate labels; source links; quantity and ingredient
  editing; catalog additions; and non-medical product language.
- Added a centralized Material UI Field Atlas theme, semantic nutrition and
  activity color tokens, responsive contour treatments, accessible focus
  states, reduced-motion safeguards, and updated visual regression assertions.
- Added an owner-scoped meal diary API with dated create, edit, delete, and
  daily-total endpoints backed by durable saved food, component, and nutrient
  values.
- Added a responsive meal diary interface with catalog search, personal-food
  creation, editable quantities and components, composite ingredient detail,
  launch-nutrient totals, and delete confirmation.
- Added backend authorization and historical-value regression coverage plus frontend
  create, edit, delete, and daily-total tests.

### Fixed

- Made native AI `REQUEST_CHANGES` verdicts fail their corresponding required
  reviewer checks, including repeated blocking verdicts, while approvals and
  non-blocking comments continue to pass.
- Kept meal-estimate source URLs and numeric values server-validated while
  removing unsupported `uri` and decimal-regex constructs from the OpenAI
  Structured Outputs schema.
- Preserved complete nutrient totals and component detail when independent
  composite-food branches reuse the same descendant definition.
- Rejected malformed meal-list dates and allowed metadata-only meal PATCH
  requests without replacing saved meal items.
- Made the nullable nutrient-column migration safely reversible while retaining
  seeded nutrient definitions and saved nutrient values.
- Allowed existing meals to retain and resize archived personal foods through
  their pinned historical versions without making those foods newly selectable.

### Changed

- Replaced the inherited dark, pale-yellow, amber, and gray placeholder styling
  across the application shell, authentication screens, dashboard, menus,
  notifications, forms, feedback states, manifest, and application mark with
  the warm paper, ink, forest, persimmon, and mineral-blue Field Atlas identity.
- Updated frontend guidance with the Field Atlas palette, typography, spacing,
  elevation, semantic data color, and accessibility rules.
- Upgraded the frontend to React Router 8.3 and raised the declared React
  compatibility floor to 19.2.8, removed obsolete v7 test-router flags, and
  added browser-routing regression coverage.
- Added the protected `/diary` route and Meal diary navigation destination,
  and documented the implemented diary workflow across the product overview
  and component guides.
- Extended the Field Atlas design system across the meal diary, meal editor,
  nutrition totals, empty states, and route-aware navigation treatments.
- Improved Django admin navigation with linked related records, inline meal
  contents, nutrition summaries, search, filters, and grouped detail forms.
- Renamed saved meal records to Meal Items throughout the backend and admin
  while preserving their historically stable nutrition values.
- Simplified catalog and meal nutrition storage to explicit nullable nutrient
  columns, preserving unknown-versus-zero semantics without database nutrient
  definition or amount tables.

## 2026-08-14
### Added
- Added Django-native Food Item catalog models and authenticated APIs for
  versioned nutrient definitions, composite foods, source references, shared
  catalog lookup, and private personal-food management.
- Added an intentional MacroMapper dashboard that explains the product's
  privacy, review, and tracking principles while clearly identifying the
  account capabilities available today.
- Added Vite and Vitest frontend tooling with explicit development, test,
  production-build, and Docker configuration.
### Fixed
- Prevented Django admin users from mutating historical Food Item definitions,
  nutrient definitions, related nutrient/source/component rows, the managed
  current-version pointer, or an existing Food Item's privacy classification.
- Corrected the GitHub setup cross-reference and separated the local console
  email sender from the verified-domain Resend production example.
- Prevented RoboCop from treating neutral CodeQL summaries for intentionally
  path-scoped language omissions as security coverage gaps when the authoritative
  scope and aggregate gates succeed and a default-branch baseline exists.
### Changed
- Made MacroMapper the sole application identity across runtime configuration,
  deployment guidance, user-agent metadata, navigation, test fixtures, and
  repository documentation.
- Standardized production routing on
  `https://macromapper.judeandrewalaba.com` and deployment on
  `/opt/apps/macromapper` for the documented non-root deploy user.
- Reshaped the root README to match Notoli's concise product-overview format
  and routed setup, component, deployment, and automation details to their
  dedicated documentation.
- Adopted FullStackTemplate's explicit CodeQL scope outputs, default-branch
  baseline interpretation, regression coverage, and documented policy.
- Rebranded the application, local routing, container and image names,
  environment variables, CI automation, tests, and documentation from the
  starter terminology to MacroMapper.
- Defined MacroMapper as a personal nutrition and activity tracker, documented
  the initial product roadmap, and aligned application-facing descriptions and
  documentation heading style with that direction.
- Migrated the frontend to React Router 7's `react-router` package and changed
  the client API configuration contract to `VITE_API_BASE_URL`.
- Raised the supported frontend runtime to Node.js 24.15 or newer and kept the
  production image on Node.js 26.
- Kept generated dependency lockfile payloads out of AI reviewer prompts so
  large lockfile migrations do not crowd out source, build, and security review.
### Removed

- Removed the reusable application initializer and the remaining starter,
  generated-repository, Lorem Ipsum, and fake-profile placeholders.
- Removed Create React App, its Jest runtime, the `react-router-dom`
  compatibility package, and the unused `web-vitals` dependency.

## 2026-08-12
### Added
- Added primary-source web search and bounded tracked-repository usage evidence
  to Obi-Wan's Dependabot semver-major reviews.
### Fixed
- Preserved every normalized major-upgrade field when publishing GitHub reviews
  so upstream rationale and repository exposure are no longer dropped.
### Changed
- Reframed Obi-Wan's major-upgrade brief around why the update appeared, why
  upstream required a major version, exact repository exposure, material
  benefits, sources, and a concrete recommendation while retaining his calm
  mentor voice.
- Condensed the major-upgrade brief to five items: dependency, why the upgrade
  matters, repository impact, recommendation, and sources.

## 2026-08-02
### Fixed
- Made Dependabot semver-major upgrade briefs collect the first release in the
  new major line and fail visibly when Obi-Wan omits the upstream change,
  repository impact, or recommendation required for an actionable review.

## 2026-07-27
### Added
- Added an advisory Obi-Wan major-upgrade brief for Dependabot semver-major
  updates, including external GitHub Release notes where available and
  concisely reporting upstream changes, repository impact, and a
  recommendation without adding a merge gate.
- Added required Dependabot-secret setup for the three AI reviewers so trusted
  dependency pull requests run the same reviewer gates as other repository PRs.
- Added a Notoli-derived GitHub repository setup guide covering merge methods,
  auto-merge, Actions permissions, fork approvals, security controls, alert
  labels, the `SECURITY_ALERTS_TOKEN` secret, and the complete main ruleset.
- Added and documented a Notoli-derived main-branch ruleset that requires
  pull requests, resolved review threads, and the independent CI/security
  check set while blocking force pushes and deletion.
- Added a Docker hot-reload development Compose workflow with React and Django
  source mounts.
- Bound development Docker ports to localhost and made documented `.env` and
  port overrides authoritative.
### Fixed
- Made the upstream major-upgrade collector executable under mocked registry
  and GitHub-release responses, including npm's string and object repository
  metadata forms and degraded lookup paths.
- Emitted a stable top-level `Auto Merge` check on every pull request so the
  required ruleset context no longer mismatches the nested Dependabot
  auto-merge workflow check.
- Removed the stale standalone `CodeQL` required-check context that blocked
  scope-empty pull requests while retaining the real CodeQL scope and analyzer
  checks.
### Changed
- Restored the three AI reviewer child checks and `Auto Merge` as required
  main-branch gates, matching Notoli's review policy while retaining the
  template's compatible CodeQL check set.
- Matched MacroMapper's live repository settings to Notoli while keeping
  a read-only default Actions permission, disabling default pull-request
  approvals by Actions, and omitting the standalone `CodeQL` context that the
  scope-aware template workflow does not emit for scope-empty pull requests.
- Added explicit least-privilege guidance for workflow permissions and documented
  the intentional ruleset difference from Notoli.
- Added `Tests / Automation Tests (Node)` to the required main-branch checks in
  MacroMapper and Notoli.
- Restored Notoli's yellow-and-gray theme across authentication, the
  application header, navigation drawer, profile and notification surfaces,
  and the protected placeholder page.
- Removed the persistent translucent selection overlay from the drawer's Home
  item.
### Removed
- Removed the shared multi-application local-ingress scripts and configuration;
  MacroMapper now uses its own application proxy like Notoli.
## 2026-07-26
### Added
- Added a shared local TLS ingress that routes Notoli, MacroMapper, and
  MacroMapper by `.localhost` hostname while one container owns ports
  80 and 443.
- Added first-class `macromapper.localhost` support for Django, Nginx, Docker, local password-reset links, and browser access.
- Added a PowerShell helper that generates a local TLS certificate with `mkcert` or OpenSSL.
- Added the MacroMapper React and Material UI application shell.
- Added a protected Material UI component showcase covering common actions,
  forms, feedback, data display, loading, empty, and confirmation states.
- Added Django REST Framework authentication with registration, email-first JWT login, refresh tokens, forgot-password, and password-reset support.
- Added responsive authentication pages, shared snackbar feedback, session renewal, and logout behavior.
- Added frontend, backend, and repository-automation test coverage.
- Added Docker, Nginx, GHCR, SSH deployment, Dependabot, CodeQL, lint, test, vulnerability, malware, AI review, and security-alert workflows based on Notoli.
- Added the Modified MIT License (Non-Commercial Use Only).
- Added a working generic Workspace → Collection → Item example with CRUD,
  inline editing, drag-and-drop ordering, mobile gestures, collaborator
  sharing, authorization boundaries, and persisted activity notifications.
- Added scripts to initialize generated repositories and create a linked GitHub
  Project with reusable planning fields.
- Added first-run documentation for CI secrets, three AI reviewer Apps,
  security alert aggregation, branch rules, Cloudflare, DigitalOcean, GHCR,
  Resend, and production deployment.
### Fixed
- Prevented port-free `macromapper.localhost` authentication requests
  from falling through to Notoli's backend when all three local applications
  are running.
- Made workspace, collection, and item creator metadata immutable so API
  clients cannot reassign `created_by` or grant access outside the workspace
  collaboration boundary.
- Preserved Dependabot source URLs through alert compaction and added regression
  coverage for generated security-issue links.
- Prevented Dependabot automation from merging pull requests while GitHub
  reports an unstable merge state.
- Pinned third-party and credential-handling GitHub Actions to immutable commit
  SHAs.
- Required each AI reviewer's GitHub App to explain an oversized diff under its
  own identity before failing the check without publishing a verdict.
- Corrected the GitHub Project initializer to copy and verify Notoli's exact
  custom fields, option sets, views, filters, grouping, sorting, and supported
  workflows instead of creating an approximate Project manually.
- Fixed the npm malware gate so an initial frontend lockfile can be reviewed when the base branch has no lockfile.
- Fixed dependency-review reporting for large initial lockfiles by keeping detailed package JSON in the check logs and annotations.
- Removed the Dependabot-only auto-merge job from required status checks so normal pull requests are not blocked by its intentional skip.
- Replaced the inherited Create React App toolchain that introduced high and critical transitive dependency vulnerabilities.
### Changed
- Reduced the authenticated frontend to a reusable header, navigation drawer,
  notifications, profile/logout controls, and one placeholder Material UI
  Paper.
- Replaced Vite, Vitest, and Biome with Notoli's Create React App,
  react-scripts, Jest, ESLint, and Prettier conventions.
- Decoupled persisted notifications from the removed sample domain while
  preserving recipient-scoped read and clear APIs.
- Standardized all three AI reviewers on one shared 512 KiB Git diff budget and
  bounded each review's output-token reservation.
- Changed Project setup to link the copied Project to the target repository and
  set `SECURITY_ALERTS_PROJECT_ID` automatically.
- Changed local setup documentation and environment templates to use `macromapper.localhost`.
- Adapted application names, domains, image names, environment names, workflow prompts, and deployment paths from Notoli to MacroMapper.
- Limited npm malware advisory queries to the changed package versions instead of downloading the full npm malware catalog.
- Modernized the frontend build, test, and lint toolchain to Vite, Vitest, and Biome while retaining React, Material UI, and the existing authentication behavior.
- Configured the frontend container to proxy authentication, API, and admin requests to Django for direct-container and same-origin operation.
- Documented the exact Python 3.12 and Node.js 25 versions required for
  non-Docker development.
- Adapted Notoli's application-specific boards, lists, and notes into the
  reusable Workspace, Collection, and Item domain.
### Removed
- Removed the Workspace, Collection, and Item backend, starter data, sharing,
  ordering, mobile gestures, component showcase, and related frontend routes,
  services, documentation, and tests.
