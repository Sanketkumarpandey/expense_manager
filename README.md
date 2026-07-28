# Expense Manager

A Frappe Framework application for personal and family expense tracking,
with a Telegram bot front-end that lets users log expenses by **voice note**
or text command.

> 🎙️ *"I spent 200 on Zomato"* → transcribed → parsed → an Expense record,
> categorized automatically, with a summary reply in Telegram.

## Personas

Two personas are supported:

- **Individual (Guardian)** — the primary account holder. Creates expense
  categories, sets monthly budgets per category, manages dependents,
  allocates pocket money, and views reports via Telegram or the Frappe desk.
- **Dependent** — a family member without desk access. Logs expenses via
  Telegram voice or text, checks remaining pocket money, and can roll
  unused period-end pocket money into savings.

## Core Flow

```
Telegram voice note
      ↓
Sarvam AI (speech → text)
      ↓
Groq LLM (text → structured Expense JSON)
      ↓
ExpenseService.create_expense() → Expense DocType
      ↓
BudgetService.refresh_budget() + PocketMoneyService.refresh_balance()
      ↓
Reply to user with summary (+ overspend warning if applicable)
```

## Tech Stack

| Layer               | Choice                                    |
|---------------------|-------------------------------------------|
| Backend framework   | Frappe v16 (Python 3.14+, MariaDB, Redis, Bench) |
| Bot interface       | Telegram Bot API (webhook-based)           |
| Speech-to-text      | Sarvam AI Speech-to-Text API                |
| Text → structured JSON | Groq LLM (llama-3.3-70b-versatile default)        |
| Reporting           | Frappe Query Reports + matplotlib/PNG      |
| Deployment          | Local bench (see `docs/deployment.md`)     |

## Project Structure

```
expense_manager/
├── api/                    # Whitelisted Frappe REST endpoints
│   ├── expenses.py         # Expense CRUD
│   ├── budgets.py          # Budget CRUD
│   ├── categories.py       # Category CRUD
│   ├── dependents.py       # Dependent CRUD
│   ├── pocket_money.py     # Pocket money allocation CRUD
│   ├── reports.py          # Report data endpoints
│   └── telegram.py         # Telegram linking endpoints
├── telegram/               # Telegram bot layer
│   ├── bot.py              # Background update dispatcher
│   ├── router.py           # Command/voice → handler routing
│   ├── webhook.py          # Guest webhook ingress, validation, enqueue
│   ├── config.py           # Secret/config getters (env → site_config)
│   ├── handlers/           # One file per command/flow
│   ├── services/           # Telegram-specific orchestration (TelegramService)
│   ├── middleware/         # Auth, logging
│   └── utils/              # File download, helpers
├── services/               # Business logic layer (the core)
│   ├── expense_service.py  # Expense creation, update, delete
│   ├── category_service.py # Category CRUD + validation
│   ├── budget_service.py   # Budget CRUD, overspend detection, refresh
│   ├── dependent_service.py# Dependent CRUD, validation
│   ├── pocket_money_service.py # Allocation, balance, rollover
│   ├── report_service.py   # Summaries, breakdowns, trends
│   ├── telegram_link_service.py # Account linking lifecycle
│   ├── ai_service.py       # Voice → expense orchestration
│   └── exceptions.py       # Typed domain exceptions
├── ai/                     # External AI integrations
│   ├── speech_to_text.py   # Sarvam AI adapter
│   ├── ai_parser.py        # Groq LLM adapter
│   └── exceptions.py       # AI-specific exceptions
├── jobs/                   # Scheduled background jobs
│   ├── budget_alerts.py    # Daily overspend notifications
│   ├── reminders.py        # Daily nudge/summary reminders
│   ├── monthly_rollover.py # Pocket money period rollover
│   └── reports.py          # Report generation jobs
├── constants/              # Enums and static data
├── report/                 # Frappe Query Reports (5 reports)
├── doctype/                # Frappe DocType definitions
├── tests/                  # 290 unit + integration tests
└── hooks.py                # Frappe hooks (scheduler_events active)
```

## Documentation Index

| Document | Description |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | System architecture & data flow |
| [`docs/api.md`](docs/api.md) | REST API surface |
| [`docs/doctypes.md`](docs/doctypes.md) | Every DocType, field, relationship, validation |
| [`docs/telegram.md`](docs/telegram.md) | Telegram bot design |
| [`docs/telegram_commands.md`](docs/telegram_commands.md) | Flow for every bot command |
| [`docs/ai.md`](docs/ai.md) | Sarvam AI + Groq LLM integration |
| [`docs/webhook.md`](docs/webhook.md) | Webhook lifecycle, security, deduplication |
| [`docs/database.md`](docs/database.md) | Schema overview |
| [`docs/error_handling.md`](docs/error_handling.md) | Retries, logging, recovery |
| [`docs/environment.md`](docs/environment.md) | Configuration variables |
| [`docs/deployment.md`](docs/deployment.md) | Local bench setup |
| [`docs/testing.md`](docs/testing.md) | Quick test reference |
| [`docs/testing_strategy.md`](docs/testing_strategy.md) | Test layers and coverage |
| [`docs/coding_guidelines.md`](docs/coding_guidelines.md) | Code style and conventions |
| [`docs/roadmap.md`](docs/roadmap.md) | What's built vs. planned |
| [`docs/codex_workflow.md`](docs/codex_workflow.md) | Phase-by-phase build plan |
| [`telegram_architecture.md`](telegram_architecture.md) | Detailed Telegram architecture |
| [`PROJECT_ANALYSIS.md`](PROJECT_ANALYSIS.md) | Initial codebase analysis |

## Getting Started

See `docs/deployment.md` for the full walkthrough. Quick version:

```bash
bench get-app expense_manager <repo_url>
bench --site mysite.local install-app expense_manager
bench --site mysite.local set-config sarvam_api_key "..."
bench --site mysite.local set-config groq_api_key "..."
bench --site mysite.local set-config telegram_bot_token "..."
bench --site mysite.local set-config telegram_webhook_secret "..."
bench start
```

## Running Tests

```bash
bench --site mysite.local run-tests --app expense_manager
```

290 tests covering services, Telegram routing, webhook validation,
AI orchestration, scheduled jobs, and integration workflows.

## Status

**Core functionality complete.** All six DocTypes, eight services, REST API,
Telegram bot with 15 commands, voice expense logging, daily scheduled jobs
(budget alerts, reminders, pocket money rollover), and 290 passing tests.

See [`docs/roadmap.md`](docs/roadmap.md) for phase completion details.
