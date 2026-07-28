# Expense Manager — Project Analysis

## 1. Repository Structure

The application is a fully implemented Frappe v16 app with six DocTypes,
eight business services, a Telegram bot, REST API, scheduled jobs, five
Query Reports, and 290 passing tests.

```text
apps/expense_manager/
├── expense_manager/
│   ├── api/                        # Whitelisted REST endpoints (7 modules)
│   ├── telegram/                   # Bot: webhook, router, handlers, services, utils
│   ├── services/                   # Business logic (8 service modules + exceptions)
│   ├── ai/                         # Speech-to-text (Sarvam) + expense parser (Groq)
│   ├── jobs/                       # Scheduled background jobs (4 modules)
│   ├── constants/                  # Enums and static data (9 modules)
│   ├── report/                     # Frappe Query Reports (5 reports)
│   ├── doctype/                    # DocType definitions (nested expense_manager/)
│   ├── tests/                      # 290 unit + integration tests
│   ├── config/                     # Configuration exceptions
│   ├── utils/                      # Logger and utilities
│   ├── hooks.py                    # Active scheduler_events (daily jobs)
│   └── modules.txt                 # "Expense Manager"
├── docs/                           # Product, architecture, API docs
├── AGENTS.md                       # Implementation instructions
├── README.md                       # Project overview
└── pyproject.toml                  # Python 3.14+ / Ruff config
```

## 2. DocTypes

Six DocTypes are fully implemented:

| DocType | Purpose | Key Fields |
|---|---|---|
| Category | Expense categories per user | `category_name`, `owner_user`, `icon`, `is_active` |
| Budget | Monthly category allocation | `owner_user`, `category`, `allocated_amount`, `spent_amount`, `period`, `start_date`, `end_date`, `alert_threshold_pct`, `is_active` |
| Dependent | Family member managed by a guardian | `guardian`, `dependent_name`, `relationship`, `default_monthly_allowance`, `telegram_username`, `telegram_user_id`, `allow_carry_forward`, `is_active` |
| Pocket Money Allocation | Dependent allowance per period | `dependent`, `allocation_period`, `allocated_amount`, `carry_forward_amount`, `total_available_amount`, `allocation_date`, `is_active` |
| Expense | Spending record | `owner_user`, `category`, `amount`, `expense_date`, `dependent`, `description`, `source`, `payment_method`, `voice_transcript` |
| Telegram Link | Telegram ↔ User mapping | `user`, `telegram_user_id`, `telegram_username`, `first_name`, `last_name`, `language_code`, `is_active`, `linked_on` |

All DocTypes are restricted to **System Manager** role only in Desk.
Ownership is enforced at the service layer (every service method takes
`owner_user` or `guardian` as its first parameter and validates ownership
before any database operation).

## 3. APIs

Seven whitelisted REST endpoint modules:

| Module | Key Methods |
|---|---|
| `api/expenses.py` | `create_expense`, `get_expense`, `update_expense`, `delete_expense`, `list_expenses`, `get_recent_expenses`, `get_expenses_by_category`, `get_expenses_by_date_range` |
| `api/budgets.py` | `create_budget`, `get_budget`, `update_budget`, `delete_budget`, `list_budgets`, `get_budget_usage` |
| `api/categories.py` | `create_category`, `get_category`, `update_category`, `delete_category`, `list_categories`, `archive_category`, `restore_category` |
| `api/dependents.py` | `create_dependent`, `get_dependent`, `update_dependent`, `delete_dependent`, `list_dependents`, `archive_dependent`, `restore_dependent` |
| `api/pocket_money.py` | `create_allocation`, `get_allocation`, `update_allocation`, `delete_allocation`, `list_allocations`, `get_balance`, `rollover` |
| `api/reports.py` | `get_expense_summary`, `get_budget_summary`, `get_category_breakdown`, `get_monthly_report`, `get_dashboard` |
| `api/telegram.py` | `generate_link_code` (POST), `get_link_status` (GET), `unlink` (POST) |

All methods are scoped to `frappe.session.user` via `_current_user()`.

## 4. Reports

Five Frappe Query Reports:

| Report | Purpose |
|---|---|
| `budget_utilization` | Budget spent vs. allocated per category |
| `category_breakdown` | Expense totals grouped by category |
| `dependent_expenses` | Expenses filtered by dependent |
| `monthly_expense_summary` | Monthly expense totals |
| `pocket_money_history` | Pocket money allocation history |

## 5. Hooks

`hooks.py` has one active hook:

```python
scheduler_events = {
    "daily": [
        "expense_manager.jobs.monthly_rollover.run_monthly_rollover",
        "expense_manager.jobs.budget_alerts.run_budget_alerts",
        "expense_manager.jobs.reminders.run_reminders",
    ],
}
```

Also active: `doctype_js = {"User": "public/js/user.js"}` for Desk integration.

## 6. Scheduled Jobs

Three daily jobs:

| Job | Purpose |
|---|---|
| `budget_alerts.run_budget_alerts` | Scans all active budgets, refreshes spent amounts, sends Telegram notifications when threshold is crossed or overspend detected |
| `reminders.run_reminders` | Sends daily nudges: no-expenses-today reminder, weekly/monthly summary, pocket money low-balance alerts |
| `monthly_rollover.run_monthly_rollover` | Rolls over expired Pocket Money Allocations (any period: weekly, monthly, quarterly, yearly) with carry-forward if allowed |

## 7. Permission System

- All six DocTypes grant permissions only to **System Manager** role
- Desk access to data is admin-only
- End-user access is exclusively through Telegram or the REST API
- Every service method takes `owner_user`/`guardian` as first parameter
- `frappe.get_doc`/`insert`/`save`/`delete` all use `ignore_permissions=True`
  because ownership is validated at the service layer
- `PocketMoneyService.refresh_balance` validates guardian ownership before
  modifying allocations
- `TelegramService._require_guardian()` blocks dependents from guardian-only
  actions (reports, budget view, expense mutation)

## 8. Telegram Integration

Fully implemented:

- **Webhook**: `telegram/webhook.py` — guest POST endpoint, secret token
  verification, Redis-based `update_id` deduplication, background enqueue
- **Router**: `telegram/router.py` — command/voice dispatch to 15 handlers
- **Handlers**: 12 handler files covering start, help, link, unlink, voice,
  expenses, categories, budgets, balance, report, dependents, pocketmoney,
  savings, rollover, profile, settings, unknown
- **TelegramService**: Orchestrator that resolves Telegram identity, enforces
  persona checks, and delegates to business services
- **AI Pipeline**: Voice note → Sarvam STT → Groq LLM → ExpenseService

## 9. Test Suite

290 tests across 16 test modules:

| Module | Tests | Coverage |
|---|---|---|
| `test_expense_service.py` | 85 | CRUD, validation, convenience methods, owner checks |
| `test_category_service.py` | 14 | CRUD, existence, archive/restore, defaults |
| `test_dependent_service.py` | 22 | CRUD, telegram ID resolution, validation |
| `test_budget_service.py` | 18 | CRUD, usage, overspend, alerts, archive/restore |
| `test_pocket_money_service.py` | 18 | CRUD, balance, rollover, low-balance messages |
| `test_report_service.py` | 30 | Summaries, breakdowns, trends, message builders |
| `test_telegram_link_service.py` | 28 | Link/unlink, token lifecycle, uniqueness |
| `test_ai_service.py` | 30 | Voice → expense creation, category resolution |
| `test_integration.py` | 21 | Cross-service workflows (voice, linking, rollover, budget alerts) |
| `test_reminders.py` | 16 | Reminder collection, dispatch, failure handling |
| `test_router.py` | 4 | Command routing, update type classification |
| `test_webhook.py` | 9 | Secret verification, deduplication, enqueue |
| `test_webhook_management.py` | 2 | Webhook registration/deregistration |
| `test_telegram_service.py` | 2 | sendMessage field handling |
| `test_telegram_config.py` | 5 | Config reading, env override, mock mode |
| `base.py` | — | Shared fixtures, Frappe mocks, `_make_doc` helper |

## 10. Current Status

All core features are implemented and tested:
- ✅ Six DocTypes with validation and ownership scoping
- ✅ Eight business services with typed exceptions
- ✅ REST API (7 modules, all whitelisted methods)
- ✅ Telegram bot (webhook, router, 15 commands, voice processing)
- ✅ AI pipeline (Sarvam STT + Groq LLM)
- ✅ Scheduled jobs (budget alerts, reminders, rollover)
- ✅ Five Query Reports
- ✅ 290 passing tests
- ✅ Security audit (ignore_permissions, guardian cross-checks, allow_rename fix)
