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
| `create_budget(category, allocated_amount, period, start_date, end_date, alert_threshold_pct=90, notes=None, dependent=None)` | Creates a budget for the logged-in user. `dependent` unset ⇒ household budget; set ⇒ dependent-scoped budget for that dependent. |
| `get_budget(budget, dependent=None)` | Single budget by name. |
| `update_budget(budget, allocated_amount=None, period=None, start_date=None, end_date=None, alert_threshold_pct=None, notes=_API_UNSET, dependent=None)` | Updates budget fields. `notes` uses `_API_UNSET` to distinguish "not supplied" from "explicitly cleared". |
| `delete_budget(budget, dependent=None)` | Deletes a budget. |
| `list_budgets(category=None, active_only=0, dependent=None)` | All budgets for the logged-in user. `dependent` set ⇒ only that dependent's budgets (guardian list always has `dependent` unset). |
| `search_budgets(search_text=None, active_only=1, dependent=None)` | Search by notes text. |
| `get_budget_usage(category, dependent=None)` | Returns `{budget, allocated_amount, spent_amount, remaining_amount, pct_used, is_overspent, alert_threshold_pct}`. Returns `{success: false, message: "No active budget for this category."}` when none matches. A dependent with no dependent-scoped budget falls back to the household (guardian) budget, so dependent spend still counts toward family usage. |
| `archive_budget(budget, dependent=None)` / `restore_budget(budget, dependent=None)` | Toggle active status. |

> A household (guardian-level, `dependent` unset) budget counts **every** expense
> for the category — including dependent-attached ones — as "spent". A
> dependent-scoped budget counts only that dependent's expenses. `refresh_budget`
> recomputes the cached `spent_amount` from Expense records on every expense
> create/update/delete.

## Dependent

| Method | Description |
|---|---|
| `create_dependent(dependent_name, relationship, default_monthly_allowance, ...)` | Creates a dependent for the logged-in guardian. |
| `get_dependent(dependent)` | Single dependent by name. |
| `update_dependent(dependent, ...)` | Updates dependent fields. |
| `delete_dependent(dependent)` | Deletes a dependent (fails if referenced). |
| `list_dependents(active_only=False)` | All dependents for the logged-in guardian. |
| `list_allowed_categories(dependent, active_only=True)` | GET. Categories the dependent may use — ALL guardian active categories when `allowed_categories` is empty, else exactly the allowed rows. |
| `add_allowed_category(dependent, category)` | POST. Allow a guardian-owned category for a dependent. `category` = Category doc name or category name; idempotent. |
| `remove_allowed_category(dependent, category)` | POST. Revoke an allowed category. Idempotent. |
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

## Guardian / User provisioning

| Method | Description |
|---|---|
| `register_guardian(email, first_name, last_name=None, send_welcome_email=True)` | POST. Admin-only guardian onboarding: creates (or upgrades) a Frappe User, assigns the `Expense Manager User` role, and seeds the 13 default categories. |

`register_guardian` is **admin-only** — the caller must be `Administrator` or have the
`System Manager` role. The guard runs first, before any input validation, so Guest
sessions and any `Expense Manager User` caller are rejected with
`frappe.PermissionError` (including self-elevation attempts). This is the only
guardian-provisioning path that auto-grants the role.

- **New user** → creates the `User` with the role pre-assigned and seeds default
  categories in the same request. Returns `{"success": true, "user": <email>, "created": true}`.
- **Existing user** → idempotent: ensures the role via `add_roles` when missing
  and seeds default categories (skipping any that already exist). Returns
  `{"success": true, "user": <email>, "created": false}`.
- Email is trimmed and lowercased before validation. `first_name` is required.
- The response never includes a password or any other `User` field beyond
  `email`/`name`.
- **Dependents are out of scope**: dependents never get a Frappe User, so this
  endpoint provisions guardians only.

## Conventions

- All whitelisted methods are called via `/api/method/...`; Frappe wraps the
  return value in `{"message": <result>}`. Success payloads return a bare doc /
  dict; expected failures return `{"success": false, "message": "..."}` as the
  `message` value (the REST layer catches `ExpenseManagerError`).
- All methods raise `frappe.ValidationError` (via service exceptions) on bad input.
- Amounts are always Indian Rupees (₹) as `Currency` fieldtype.
- Every whitelisted method has matching unit tests.
- The Telegram voice path creates expenses through `TelegramService`,
  not through `api/expenses.py`.
