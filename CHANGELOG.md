# Changelog
All notable changes to this project are documented in this file.

## 2026-08-22

### Fixed

- Rolled composite meal nutrition up from component values even when a parent
  food version contains stale or zero direct nutrient columns.

### Changed

- Expanded meal-estimate review with a meal-level calorie summary, macro chart,
  and per-component protein, carbohydrate, and fat values that recalculate as
  servings and ingredients change.
- Added grams and calorie-share percentages to the meal summary chart legends
  so macro and component contributions can be compared at a glance.

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
