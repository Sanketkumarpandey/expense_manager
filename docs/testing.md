# Testing (Quick Reference)

For the full strategy, see `docs/testing_strategy.md`.

## Running Tests

```bash
bench --site mysite.local run-tests --app expense_manager
```

Run a single test module:

```bash
bench --site mysite.local run-tests --module expense_manager.tests.test_expense_service
```

## Test Layout

```
expense_manager/tests/
├── base.py                        # Shared fixtures, Frappe mocks, _make_doc helper
├── test_category_service.py       # 14 tests
├── test_dependent_service.py      # 22 tests
├── test_expense_service.py        # 85 tests
├── test_budget_service.py         # 18 tests
├── test_pocket_money_service.py   # 18 tests
├── test_report_service.py         # 30 tests
├── test_telegram_link_service.py  # 28 tests
├── test_ai_service.py             # 30 tests
├── test_integration.py            # 21 tests (cross-service workflows)
├── test_reminders.py              # 16 tests
├── test_router.py                 # 4 tests
├── test_webhook.py                # 9 tests
├── test_webhook_management.py     # 2 tests
├── test_telegram_service.py       # 2 tests
└── test_telegram_config.py        # 5 tests
```

**Total: 290 tests.**

## Test Architecture

All service tests inherit from `ServiceTestCase` (in `base.py`) which
provides:

- Patched `frappe` module (get_doc, get_all, db.exists, db.get_value,
  throw, commit, rollback, logger) for every service module
- Pre-built `self.mock_doc` that behaves like a Frappe Document
- `_make_doc(base, **overrides)` helper that creates docs from sample data
- Patched `frappe.utils.today` → `"2026-07-27"` for deterministic dates

## Mocking External APIs

Never call live Sarvam AI or OpenAI APIs in tests. The AI modules are
tested against mocked HTTP responses. Service-layer tests mock
`frappe.get_doc`, `frappe.db.exists`, `frappe.db.get_value` at the
module level.

## Minimum Bar Before Marking a Phase Done

- All new/changed code has at least one passing test.
- `bench run-tests` passes with zero failures (currently 290/290).
- No test depends on network access or live API keys.
