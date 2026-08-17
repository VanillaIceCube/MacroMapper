# MacroMapper frontend style guide

## Foundations

- Use Material UI components and responsive `sx` values before adding custom
  layout primitives.
- Use the centralized Material UI theme in `src/theme.js` and the matching CSS
  custom properties in `src/App.css`; do not introduce one-off brand colors.
- Follow the Field Atlas direction documented in
  `../docs/design/FIELD_ATLAS.md`: warm paper surfaces, ink structure, restrained
  cartographic details, and factual rather than clinical language.
- Use Bone `#F6F1E7` for the canvas, Midnight ink `#17324D` for text and
  structure, Forest `#2E6B4F` for confirmed states and primary actions,
  Persimmon `#E46B3C` for editable estimates, and Mineral blue `#A9CAD4` for
  neutral data surfaces.
- Use Forest for protein, the accessible dark Mineral token for carbohydrates,
  Persimmon for fat, and the deeper activity token for activity. Pair every
  state color with text, an icon, or another non-color cue.
- Use `Newsreader` for editorial headings and `Inter` for navigation, controls,
  labels, and body copy. Apply tabular numerals to nutrition data with the
  `numeric-data` class.
- Prefer one-pixel ink borders, 10–14 px radii, and surface shifts to elevation.
  Shadows should remain subtle and limited to floating menus or focus layers.
- Preserve 44 px minimum interactive targets, visible keyboard focus, reduced
  motion behavior, and WCAG 2.2 AA contrast.
- Keep authenticated and public routes visually consistent with the shared
  application shell.

## Authentication
- Build public authentication pages with `AuthPageShell`.
- Give every form a visible heading, native submit behavior, and browser
  autocomplete metadata.
- Show API outcomes through the shared application snackbar.
- Avoid exposing whether an email address belongs to an account in
  forgot-password responses.

## Application shell

- Keep `MacroMapper` as the app-header title.
- Preserve the drawer, notification, profile, and logout entry points when
  adding product routes.
- Keep the Home page specific to MacroMapper and clearly distinguish active
  capabilities from roadmap features.
- Add future product routes behind `AuthenticatedRoute` unless they are
  intentionally public.
- Keep contour lines low contrast and away from dense forms, tables, and data
  visualizations.
- Concentrate mapping language around meal creation and provenance; use plain
  language for ordinary settings and account actions.

## Nutrition surfaces

- Present daily totals as bordered data cards with tabular numerals. Use the
  semantic protein, carbohydrate, and fat tokens; keep calories and secondary
  nutrients on neutral paper surfaces.
- Use Forest to identify saved meals and confirmed catalog actions, Mineral for
  neutral date and search surfaces, and Persimmon for user-entered food
  estimates.
- Call saved records “meal items” in the interface. Reserve component language
  for the optional ingredient breakdown within a composite food.
