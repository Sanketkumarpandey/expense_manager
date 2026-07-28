# API Surface

All endpoints are Frappe `@frappe.whitelist()` methods under
`expense_manager.api.*`, reachable at
`/api/method/expense_manager.api.<module>.<method>`.

Every method is scoped to `frappe.session.user` via `_current_user()`.
**No Telegram-specific logic lives here** — these are the desk/REST path.

## Expense

| Method | Description |
|---|---|
| `create_expense(category, amount, expense_date, dependent=None, description=None, source=None, payment_method=None, voice_transcript=None)` | Creates an Expense for the logged-in user. |
| `get_expense(expense)` | Single expense record by name. |
| `update_expense(expense, category=None, amount=None, expense_date=None, dependent=None, description=None, payment_method=None)` | Updates an expense. Uses `_API_UNSET` sentinel to distinguish "not supplied" from "explicitly cleared". |
| `delete_expense(expense)` | Deletes an expense. |
| `list_expenses(dependent=None, category=None, date_from=None, date_to=None, limit=None)` | Filtered list with optional date range and limit. |
| `get_recent_expenses(dependent=None, limit=10)` | Convenience: last N expenses. |
| `get_expenses_by_category(category, dependent=None)` | Expenses for one category. |
| `get_expenses_by_date_range(date_from, date_to, dependent=None)` | Expenses within a date range. |

## Category

| Method | Description |
|---|---|
| `create_category(category_name, icon=None)` | Creates a category for the logged-in user. |
| `get_category(category)` | Single category by name. |
| `update_category(category, category_name=None, icon=None, is_active=None)` | Updates a category. |
| `delete_category(category)` | Deletes a category (fails if in use). |
| `list_categories(active_only=False)` | All categories for the logged-in user. |
| `archive_category(category)` / `restore_category(category)` | Toggle active status. |

## Budget

| Method | Description |
|---|---|
| `create_budget(category, allocated_amount, period, start_date, end_date, alert_threshold_pct=90, notes=None)` | Creates a budget for the logged-in user. |
| `get_budget(budget)` | Single budget by name. |
| `update_budget(budget, ...)` | Updates budget fields. |
| `delete_budget(budget)` | Deletes a budget. |
| `list_budgets(category=None, active_only=False)` | All budgets for the logged-in user. |
| `get_budget_usage(category)` | Returns allocated, spent, remaining, pct_used, is_overspent. |
| `archive_budget(budget)` / `restore_budget(budget)` | Toggle active status. |

## Dependent

| Method | Description |
|---|---|
| `create_dependent(dependent_name, relationship, default_monthly_allowance, ...)` | Creates a dependent for the logged-in guardian. |
| `get_dependent(dependent)` | Single dependent by name. |
| `update_dependent(dependent, ...)` | Updates dependent fields. |
| `delete_dependent(dependent)` | Deletes a dependent (fails if referenced). |
| `list_dependents(active_only=False)` | All dependents for the logged-in guardian. |
| `archive_dependent(dependent)` / `restore_dependent(dependent)` | Toggle active status. |

## Pocket Money

| Method | Description |
|---|---|
| `create_allocation(dependent, allocated_amount, allocation_period, ...)` | Creates a pocket money allocation. |
| `get_allocation(allocation)` | Single allocation by name. |
| `update_allocation(allocation, ...)` | Updates allocation fields. |
| `delete_allocation(allocation)` | Deletes an allocation. |
| `list_allocations(dependent=None, active_only=False)` | All allocations for the logged-in guardian. |
| `get_balance(dependent)` | Returns allocated, spent, carry_forward, remaining. |
| `rollover(dependent)` | Rolls over expired allocation with carry-forward. |

## Reports

| Method | Description |
|---|---|
| `get_expense_summary(dependent=None, date_from=None, date_to=None)` | Total amount, count, average for a date range. |
| `get_budget_summary(category=None)` | Budget usage per category. |
| `get_category_breakdown(dependent=None, date_from=None, date_to=None)` | Expense totals grouped by category. |
| `get_monthly_report(dependent=None, year=None)` | Monthly totals for a year. |
| `get_dashboard()` | High-level dashboard: total, monthly, active budgets, over-budget count, dependents. |

## Telegram Linking

| Method | Description |
|---|---|
| `generate_link_code()` | POST. Generates a short-lived token for the logged-in user. Returns `{token, expires_at}`. |
| `get_link_status()` | GET. Returns `{linked: bool}` for the logged-in user. |
| `unlink()` | POST. Deactivates the current link. Idempotent. |

## Conventions

- All methods raise `frappe.ValidationError` (via service exceptions) on bad input.
- Amounts are always Indian Rupees (₹) as `Currency` fieldtype.
- Every whitelisted method has matching unit tests.
- The Telegram voice path creates expenses through `TelegramService`,
  not through `api/expenses.py`.
