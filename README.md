# Expense Manager

A Frappe Framework application for personal and family expense tracking,
with a Telegram bot front-end that lets users log expenses by **voice note**.

> 🎙️ *"I spent 200 on Zomato"* → transcribed → parsed → an Expense record,
> categorized automatically, with a summary reply in Telegram.

## Why this project exists

Two personas are supported:

- **Individual** — the primary account holder. Sets up expense categories,
  allocates a monthly budget per category, gets overspend notifications,
  adds Dependents and allocates them pocket money, and views weekly/monthly
  reports (with charts) for themselves and their dependents.
- **Dependent** — e.g. a child or family member without desk/login access.
  Logs their own expenses via Telegram, checks remaining pocket money, and
  can roll unused month-end pocket money into "savings".

## Core Flow

```
Telegram voice note
      ↓
Sarvam AI (speech → text)
      ↓
OpenAI GPT (text → structured Expense JSON)
      ↓
Frappe Expense DocType (created via existing validation)
      ↓
Reply to user with a summary
```

## Tech Stack

| Layer               | Choice                                   |
|---------------------|-------------------------------------------|
| Backend framework   | Frappe v16 (Python, MariaDB, Redis, Bench) |
| Bot interface       | Telegram Bot API (webhook-based)           |
| Speech-to-text      | Sarvam AI Speech-to-Text API                |
| Text → structured JSON | OpenAI GPT (gpt-4o-mini default)        |
| Reporting/charts    | Frappe Query Reports + matplotlib/PNG      |
| Deployment (current phase) | Local bench (see `docs/deployment.md`) |

## Documentation Index

Core:
- [`docs/architecture.md`](docs/architecture.md) — system architecture & data flow
- [`docs/database.md`](docs/database.md) — schema overview (see also `docs/doctypes.md`)
- [`docs/telegram.md`](docs/telegram.md) — bot design
- [`docs/api.md`](docs/api.md) — REST API surface
- [`docs/ai.md`](docs/ai.md) — Sarvam AI + OpenAI GPT integration
- [`docs/coding_guidelines.md`](docs/coding_guidelines.md)
- [`docs/testing.md`](docs/testing.md)
- [`docs/roadmap.md`](docs/roadmap.md)

Extended specification:
- [`docs/prd.md`](docs/prd.md) — full Product Requirements Document
- [`docs/doctypes.md`](docs/doctypes.md) — every DocType, field, relationship, validation, permissions
- [`docs/telegram_commands.md`](docs/telegram_commands.md) — flow for every bot command
- [`docs/prompts.md`](docs/prompts.md) — all GPT prompt templates & JSON schemas
- [`docs/webhook.md`](docs/webhook.md) — webhook lifecycle, security, retries, file downloads
- [`docs/deployment.md`](docs/deployment.md) — local bench setup (this phase)
- [`docs/environment.md`](docs/environment.md) — all environment variables
- [`docs/testing_strategy.md`](docs/testing_strategy.md) — unit/integration/webhook/AI/e2e tests
- [`docs/error_handling.md`](docs/error_handling.md) — retries, logging, recovery, user-facing errors
- [`docs/codex_workflow.md`](docs/codex_workflow.md) — phase-by-phase autonomous build plan

## Getting Started (local bench)

See `docs/deployment.md` for the full walkthrough. Quick version:

```bash
bench get-app expense_manager <repo_url>
bench --site mysite.local install-app expense_manager
bench --site mysite.local set-config sarvam_api_key "..."
bench --site mysite.local set-config openai_api_key "..."
bench --site mysite.local set-config telegram_bot_token "..."
bench start
```

## Status

Early stage — see `docs/roadmap.md` for what's built vs. planned, and
`docs/codex_workflow.md` for the current phase.
