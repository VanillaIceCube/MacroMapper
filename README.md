# MacroMapper

MacroMapper is a full-stack application starter built from the proven Notoli foundation. It currently provides a complete authentication flow and a protected React page that displays `Hello World`, ready for MacroMapper-specific product development.

## Included

- React 19 single-page application with Material UI
- Django REST Framework backend with a custom user model
- Email-first JWT registration, login, token refresh, and session renewal
- Forgot-password and tokenized password-reset flows
- Responsive login, registration, reset, and protected home screens
- Frontend, backend, and repository-automation tests
- Biome, Prettier, Ruff, CodeQL, dependency review, and npm malware gates
- Dependabot, AI-assisted pull-request review workflows, and security-alert aggregation
- Docker images, Docker Compose, Nginx, GHCR publishing, and SSH deployment
- A Notoli-matched GitHub Project for planning and security automation

## Quick start

Backend:

```powershell
python -m pip install -r backend/requirements.txt
python backend/manage.py migrate
python backend/manage.py runserver 8000
```

Frontend, in a second terminal:

```powershell
Set-Location frontend
npm ci
npm start
```

Open `http://localhost:3000`. Create an account or log in to reach the protected Hello World page.

## Documentation

- [Developer setup and repository guidance](AGENTS.md)
- [Backend and authentication API](backend/README.md)
- [Frontend routes and session behavior](frontend/README.md)
- [Docker and production deployment](deploy/README.md)
- [GitHub Actions and repository configuration](.github/README-WORKFLOWS.md)
- [Changelog](CHANGELOG.md)

## License

MacroMapper uses the [Modified MIT License (Non-Commercial Use Only)](LICENSE.md).
