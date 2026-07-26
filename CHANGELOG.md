# Changelog

## 2026-07-26

### Added

- Added the MacroMapper React and Material UI application shell.
- Added a protected Hello World home page.
- Added Django REST Framework authentication with registration, email-first JWT login, refresh tokens, forgot-password, and password-reset support.
- Added responsive authentication pages, shared snackbar feedback, session renewal, and logout behavior.
- Added frontend, backend, and repository-automation test coverage.
- Added Docker, Nginx, GHCR, SSH deployment, Dependabot, CodeQL, lint, test, vulnerability, malware, AI review, and security-alert workflows based on Notoli.
- Added the Modified MIT License (Non-Commercial Use Only).
- Added a MacroMapper GitHub Project matching Notoli's fields and views.

### Changed

- Adapted application names, domains, image names, environment names, workflow prompts, and deployment paths from Notoli to MacroMapper.
- Configured the frontend container to proxy authentication, API, and admin requests to Django for direct-container and same-origin operation.
- Removed Notoli-specific boards, lists, notes, notifications, sharing, reordering, and navigation domains from the starter application.
