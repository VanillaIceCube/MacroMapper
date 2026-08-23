# 🥗 MacroMapper
**A Source-Aware Nutrition and Activity Tracker**

MacroMapper is a personal nutrition and activity tracker for people who want a
fast diary without hiding how meal estimates were created. Users can log food
manually or describe a meal in natural language, review an editable GPT
estimate with its sources, and decide what enters their history.

It is inspired by MyFitnessPal's quick daily logging experience, with a
transparent Food Item catalog that can break meals into reusable components.
MacroMapper tracks nutrition and activity information without providing
medical, clinical, or prescriptive dietary advice.

The authentication, application, Food Item catalog, private meal diary, and
GPT-assisted meal-estimation flows are implemented. Activity and goal features
remain planned in the [product roadmap](docs/PRODUCT_VISION.md).

## ✨ Features
- **Account foundation:** email-first registration, JWT sessions, password
  reset, protected routes, and recipient-scoped notifications
- **Private meal diary:** dated meal entry creation, editing, deletion, durable
  saved food/component details, and daily launch-nutrient totals
- **GPT meal proposals:** clause-aware, typo-tolerant multi-food catalog reuse
  with quantity extraction and full-clause AI fallback only for unresolved
  foods, plus conversational follow-up additions and corrections within the
  editable,
  source-aware estimates with explicit provenance, immutable review revisions,
  and confidence that require review before saving
- **Reusable Food Items:** authenticated catalog APIs for standalone and
  composite foods with portions, nutrients, provenance, sources, and confidence
- **Catalog separation:** initial AI definitions become deduplicated shared
  catalog records, while user-adjusted and fully personal records remain
  attributable and private
- **Goals and trends (planned):** nutrition targets, activity-adjusted budgets,
  and factual daily, weekly, and monthly reporting
- **Same-origin routing:** React at `/`, authentication at `/auth/`, application
  APIs at `/api/`, and Django admin at `/admin/`
- **Dockerized deployment:** frontend, backend, and Nginx reverse proxy with
  local HTTPS and production-oriented configuration

## 🚀 Tech Stack
- **Backend:** Django + Django REST Framework
- **Frontend:** React + Vite + Material UI
- **Authentication:** Simple JWT
- **Testing:** Django test runner + Vitest + Testing Library
- **Code quality:** Ruff + ESLint + Prettier
- **Deployment:** Docker + Nginx
- **Hosting:** DigitalOcean
- **DNS/Proxy:** Cloudflare
- **Email:** Resend
- **CI/CD & Workflows:** GitHub Actions
- **Security automation:** CodeQL, dependency and malware review, Dependabot,
  blocking AI PR reviewer verdicts enforced through required checks, and
  scheduled security-alert aggregation

## 📚 Documentation
- Product vision and delivery roadmap: [`docs/PRODUCT_VISION.md`](docs/PRODUCT_VISION.md)
- Setup, environment variables, and common commands: [`AGENTS.md`](AGENTS.md)
- Backend (API, auth, configuration): [`backend/README.md`](backend/README.md)
- Frontend (routing, sessions, API base URL): [`frontend/README.md`](frontend/README.md)
- Deployment (Docker, Nginx, Cloudflare, DigitalOcean): [`deploy/README.md`](deploy/README.md)
- GitHub Apps, Project, and repository settings: [`docs/GITHUB_SETUP.md`](docs/GITHUB_SETUP.md)
- CI/CD and automation: [`.github/README-WORKFLOWS.md`](.github/README-WORKFLOWS.md)
- Changelog: [`CHANGELOG.md`](CHANGELOG.md)

## 📜 License
This project is licensed under a **Modified MIT License (Non-Commercial Use
Only)**. See [`LICENSE.md`](LICENSE.md) for full details.

## 🙏 Acknowledgments
This project includes code derived from
[`conda_export.py`](https://github.com/andresberejnoi/Conda-Tools) by
**Andres Berejnoi**, used under the terms of the original
[MIT License](https://opensource.org/licenses/MIT).
