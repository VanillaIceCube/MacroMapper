# 🥗 MacroMapper

**A source-aware nutrition and activity tracker**

MacroMapper is a personal nutrition tracker inspired by MyFitnessPal's quick
daily logging. Log food manually or describe a meal, review an editable AI
estimate with sources, and decide what enters your private diary.

Food logging, the reusable catalog, and AI meal review are implemented;
activity and goals remain planned. The application provides nutrition
information rather than medical or prescriptive dietary advice.

## ✨ Features

- A private meal diary with daily nutrient totals and editable saved meals.
- AI meal proposals with sources, confidence, and a review step before saving.
- Reusable foods, recipes, serving sizes, and ingredient breakdowns.
- Accounts, password recovery, and recipient-scoped notifications.
- An MCP integration for working with the application through connected clients.

## 🚀 Tech stack

- **Frontend:** React, Vite, and Material UI.
- **Backend:** Django REST Framework and JWT authentication.
- **Development and hosting:** Docker, Nginx, and GitHub Actions.

## 📚 Documentation

- [Product vision](docs/PRODUCT_VISION.md) — scope, roadmap, and author's note.

- [Backend](backend/README.md) — setup, APIs, authentication, email, and MCP.
- [Frontend](frontend/README.md) — setup, pages, components, and browser tests.
- [Deployment](deploy/README.md) — local Docker, configuration, and live-server guides.
- [GitHub setup and workflows](.github/README-WORKFLOWS.md) — first-PR setup and automation.
- [Scripts](scripts/README.md) — repository helpers.
- [Tests](tests/README.md) — validation commands and coverage.
- [Changelog](CHANGELOG.md) — project updates.

## 📜 License

[Modified MIT License (Non-Commercial Use Only)](LICENSE.md).
Commercial use requires separate permission from the copyright holder.
