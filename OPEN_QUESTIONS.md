# Open Questions

Items resolved or deferred with a conservative default. See `docs/codex_workflow.md`
and `docs/api.md` for the canonical API surface.

## Resolved with a conservative default

### `source` for web-created expenses (2026-08-04)

The Phase 3 prompt said quick-add free-text should be recorded with source
"Desk". There is no "Desk" value in `ExpenseSource` — the valid options are
`Telegram`, `Web`, `API`, `Manual`. The web/desk quick-add and create-expense
form therefore use `ExpenseSource.WEB` ("Web") and the manual form defaults to
`ExpenseSource.MANUAL` ("Manual"). If a distinct "Desk" value is required,
add it to `ExpenseSource` in `expense_manager/constants/expense.py` and update
`api/expenses.py` accordingly.
