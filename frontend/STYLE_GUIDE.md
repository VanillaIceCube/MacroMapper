# MacroMapper frontend style guide
## Foundations
- Use Material UI components and responsive `sx` values before adding custom
  layout primitives.
- Keep colors in the CSS custom properties declared in `src/App.css`.
- Preserve MacroMapper's theme tokens: dark `#1a1a1a` backgrounds, pale-yellow
  `#f5e79e` surfaces, amber `#ffc107` accents, gray `#555555` controls and
  surface text, and white `#ffffff` text on dark backgrounds.
- Use the MacroMapper secondary color for focused Material UI text
  fields.
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
