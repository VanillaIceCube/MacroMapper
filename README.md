# 🥗 MacroMapper

**A source-aware nutrition and activity tracker**

MacroMapper is a personal nutrition tracker inspired by MyFitnessPal's quick
daily logging. Log food manually or describe a meal, review an editable AI
estimate with sources, and decide what enters your private diary.

Food logging, the reusable catalog, and AI meal review are implemented;
activity and goals remain planned. The application provides nutrition
information rather than medical or prescriptive dietary advice.

<details>
<summary>A note from the author</summary>

First and foremost, I created this application because I wanted a Calorie Counting App. I used to use MyFitnessPal, but I wanted something AI-Powered, and all options were like $20 bucks a month. I also didn't want to take pictures of my food? I mean I feel like that would just give you the worst estimate of all time.

I had a vision where you'd write up a description then it would do it's best to fact check it against the internet. Like if I said I wanted a double double animal style with no lettuce (this is an example, I love lettuce) from inn-n-out, it would go to the internet and find the double double facts, find the animal style if it can, then break it down into components, and then remove the lettuce. And that info would be available for everyone in the application, with confidence level, the actual source, and a provenance marking.

Outside of that, I mean my goal was to get a good personal use application that utilized generative AI in a manner that you could trust and audit it.

</details>

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

- [Backend](backend/README.md) — setup, APIs, authentication, email, and MCP.
- [Frontend](frontend/README.md) — setup, pages, components, and tests.
- [Deployment](deploy/README.md) — local Docker, configuration, and live-server guides.
- [GitHub setup and workflows](.github/_README.md) — first-PR setup and automation.
- [Changelog](CHANGELOG.md) — project updates.

## 📜 License

[Modified MIT License (Non-Commercial Use Only)](LICENSE.md).
Commercial use requires separate permission from the copyright holder.
