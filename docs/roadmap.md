# Roadmap

Tracks what's built vs. planned. See `docs/codex_workflow.md` for the
original phase-by-phase prompts.

## Completed

| Phase | Description | Date |
|---|---|---|
| 1 | Project analysis (read-only) | 2026-07-22 |
| 2 | Telegram architecture doc | 2026-07-22 |
| 3 | Folder skeleton (empty modules) | 2026-07-22 |
| 4 | Telegram configuration (secrets, environment) | 2026-07-22 |
| 5 | Webhook receive + verify + log + enqueue | 2026-07-22 |
| 6 | Command routing (/start, /help, /link, /unlink, unknown) | 2026-07-22 |
| 7 | Account linking (token-based flow) | 2026-07-22 |
| 8 | Voice message receive/download | 2026-07-22 |
| 9 | Sarvam AI speech-to-text integration | 2026-07-22 |
| 10 | Groq LLM expense parsing (text → JSON) | 2026-07-22 |
| 11 | Expense creation from parsed JSON | 2026-07-22 |
| 12 | Reports (Query Reports, Telegram rendering) | 2026-07-22 |
| 13 | Budget alerts (daily scheduled job) | 2026-07-22 |
| 14 | Full service layer (8 services, typed exceptions) | 2026-07-23 |
| 15 | REST API (7 whitelisted endpoint modules) | 2026-07-23 |
| 16 | Dependent management + pocket money allocation | 2026-07-23 |
| 17 | Pocket money rollover (daily scheduled job) | 2026-07-23 |
| 18 | Daily reminders (no-expenses, weekly/monthly summary, low balance) | 2026-07-24 |
| 19 | Extended Telegram commands (expenses, categories, budgets, balance, dependents, pocketmoney, savings, rollover, profile, settings) | 2026-07-24 |
| 20 | Five Frappe Query Reports | 2026-07-24 |
| 21 | Service unit tests (269 tests) | 2026-07-25 |
| 22 | Integration tests (21 cross-service workflow tests, 290 total) | 2026-07-25 |
| 23 | Security audit (ignore_permissions, guardian cross-checks, allow_rename fix) | 2026-07-27 |

## In Progress

_(none)_

## Planned

- Production deployment (VPS, Nginx, Supervisor, TLS)
- Webhook management UI in Desk
- Bulk expense import
- Export to CSV/PDF
- Multi-currency support
- Non-Telegram bot channels (WhatsApp, etc.)
- Mobile app
- Chart image generation for Telegram (PNG reports)
- Dependent-specific role permissions (currently admin-only Desk access)

## Explicitly Out of Scope (for now)

- Multi-currency
- Non-Telegram bot channels (WhatsApp, etc.)
- Production/VPS deployment (deferred — current target is local bench only)
- Mobile app
