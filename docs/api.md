# API Surface

All endpoints are Frappe `@frappe.whitelist()` methods under
`expense_manager.api.*`, reachable at
`/api/method/expense_manager.api.<module>.<method>`.

They are called both by the Telegram services layer and (later) by any
web/mobile client, so **no Telegram-specific logic lives here.**

## Expense

| Method | Description |
|---|---|
| `expense.create_expense(amount, category, merchant=None, date=None, notes=None, owner=None, source="web")` | Creates an Expense. `owner` defaults to the logged-in user; Telegram services pass the resolved User/Dependent explicitly. |
| `expense.list_expenses(owner=None, from_date=None, to_date=None, category=None)` | Filtered list for reports. |
| `expense.get_expense(name)` | Single record. |
| `expense.delete_expense(name)` | Owner or Individual-of-dependent only. |

## Budget

| Method | Description |
|---|---|
| `budget.set_budget(category, month, amount)` | Individual only. |
| `budget.get_budget_status(month=None)` | Allocated vs. spent per category, with overspend flags. |

## Dependent

| Method | Description |
|---|---|
| `dependent.add_dependent(name, relation)` | Creates a Dependent + linked restricted User. |
| `dependent.allocate_pocket_money(dependent, month, amount)` | |
| `dependent.get_pocket_money_status(dependent, month=None)` | Remaining balance. |
| `dependent.rollover_pocket_money(dependent, from_month, to_month)` | Moves unused balance into "savings". |

## Reports

| Method | Description |
|---|---|
| `report.weekly_summary(owner=None)` | Returns totals by category for the current week + a chart-ready dataset. |
| `report.monthly_summary(owner=None, month=None)` | Same, monthly. |
| `report.generate_chart_png(dataset)` | Renders a PNG (used by the Telegram `/report` handler to send an image). |

## Telegram Linking

| Method | Description |
|---|---|
| `telegram_link.generate_otp(telegram_id)` | Returns OTP, stores it with a 5-minute expiry. |
| `telegram_link.verify_otp(otp, user)` | Called from the desk/linking page, not from Telegram. |
| `telegram_link.unlink(telegram_id)` | |

## Conventions

- All list-returning methods support standard Frappe `filters`/`limit`/`order_by`
  kwargs where practical.
- All methods raise `frappe.ValidationError` (or a subclass) on bad input;
  callers are responsible for translating that into a user-facing message
  (see `docs/error_handling.md`).
- Amounts are always Indian Rupees (₹) as `Currency` fieldtype; no
  multi-currency support in this phase.
- Every whitelisted method must have a matching unit test — see
  `docs/testing_strategy.md`.
