# MacroMapper frontend style guide

## Foundations

- Use Material UI components and responsive `sx` values before adding custom layout primitives.
- Keep colors in the CSS custom properties declared in `src/App.css`.
- Use the MacroMapper secondary color for focused Material UI text fields.
- Keep authenticated and public routes visually consistent with the shared application shell.

## Authentication

- Build public authentication pages with `AuthPageShell`.
- Give every form a visible heading, native submit behavior, and browser autocomplete metadata.
- Show API outcomes through the shared application snackbar.
- Avoid exposing whether an email address belongs to an account in forgot-password responses.

## Starter page

- The home page is intentionally minimal until MacroMapper product requirements are added.
- Add future product routes behind `AuthenticatedRoute` unless they are intentionally public.
