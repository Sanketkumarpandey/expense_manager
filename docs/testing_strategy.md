# Testing Strategy

Five layers, each with a distinct purpose. See `docs/testing.md` for the
quick reference.

## 1. Unit Tests — Services (269 tests)

Scope: business logic in `services/*`, validated against mocked Frappe ORM.

Every service method is tested for:
- Happy path
- Ownership validation (wrong owner → not found)
- Validation errors (invalid amounts, dates, periods, thresholds)
- Idempotency (archive/restore when already in target state)
- Edge cases (empty lists, None values, boundary conditions)

Tests use `ServiceTestCase` from `tests/base.py`, which patches
`frappe.get_doc`, `frappe.get_all`, `frappe.db.exists`,
`frappe.db.get_value`, `frappe.throw`, `frappe.commit`,
`frappe.rollback`, and `frappe.logger` at the module level.

## 2. Integration Tests — Cross-Service Workflows (21 tests)

Scope: multi-service interactions tested via `tests/test_integration.py`.

Workflows tested:
- **Voice → AI → Expense**: transcribe → parse → create expense → budget refresh
- **Telegram Linking**: link account → verify → unlink → status checks
- **Pocket Money Rollover**: create allocation → rollover → carry-forward
- **Budget Alerts**: create budget → overspend → threshold detection → alert message

## 3. Webhook Tests (11 tests)

Scope: `telegram/webhook.py` and `telegram/webhook_management.py`.

- Valid secret token → 200 + job enqueued
- Invalid/missing secret token → 403
- Duplicate `update_id` → 200, no second job
- Malformed JSON → 200 (never let Telegram see a 500)
- Missing `update_id` → 200, ignored
- Webhook registration/deregistration with mocked requests

## 4. Router Tests (4 tests)

Scope: `telegram/router.py`.

- Voice update dispatches to `handle_voice`
- `/start`, `/help`, `/link`, `/unlink` dispatch to correct handlers
- Unknown command dispatches to `handle_unknown`
- Non-message updates are ignored

## 5. Telegram Service Tests (2 tests)

Scope: `telegram/services/telegram_service.py`.

- `send_message` includes required fields
- `send_message` omits `parse_mode` when not supplied

## 6. Config Tests (5 tests)

Scope: `telegram/config.py`.

- All required credentials read from site config
- Environment variables override site config
- Missing required value raises descriptive error
- Mock mode flag validation (0/1/true/false)

## 7. Reminder Tests (16 tests)

Scope: `jobs/reminders.py`.

- Message builders return correct format or None
- Collection assembles multiple reminders
- Dispatch sends all messages
- Handles send failures gracefully
- Skips users with incomplete links

## Coverage Expectations

Each phase adds tests before being marked complete in `docs/roadmap.md`.
A phase is not done if `bench run-tests` doesn't pass cleanly.

## What's Explicitly Not Tested Automatically

- Actual Sarvam AI / Groq accuracy (manual/product concern)
- Telegram's own delivery guarantees
- Load/performance testing
- Production deployment concerns
