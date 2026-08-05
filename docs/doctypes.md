# DocTypes — Full Specification

Conventions: `Link` fields reference another DocType by name. `Select`
fields list their options. Required fields are marked **(required)**.
All DocTypes are restricted to **System Manager** role only in Desk.
Ownership is enforced at the service layer.

---

## 1. Category

Represents an expense category (Food, Medical, Travel, ...). Categories form
a **single, guardian-owned shared pool** — a category is never scoped to a
dependent. Dependents are restricted via `Dependent.allowed_categories`
(see below); an empty allowed list means the dependent may use every
guardian-owned active category.

| Field | Type | Notes |
|---|---|---|
| `category_name` | Data | **(required)**, unique per `owner_user` (case-insensitive) |
| `owner_user` | Link → User | **(required)** — the Individual who created it |
| `icon` | Data | optional, emoji or icon key |
| `is_active` | Check | default 1 |
| `dependent` | Link → Dependent | **legacy, unused** — kept for backward compatibility only; never read by the services |

**Validation**: `category_name` unique per `owner_user` (case-insensitive,
whitespace-normalized, title-cased). Cannot delete if referenced by an
Expense or Budget.

**Seed data**: Default categories created via
`CategoryService.create_default_categories()`: Food, Travel, Medical,
Utilities, Shopping, Entertainment, Uncategorized.

**Authorization**: `CategoryService.get_category(owner_user, ...)` /
`list_categories(owner_user, ...)` authorize solely on `owner_user`; no
dependent-scoped lookups exist anymore.

---

## 2. Budget

Monthly allocation per Category.

| Field | Type | Notes |
|---|---|---|
| `owner_user` | Link → User | **(required)** |
| `category` | Link → Category | **(required)** |
| `allocated_amount` | Currency | **(required)**, > 0 |
| `spent_amount` | Currency (read-only) | recomputed by `BudgetService.refresh_budget()` |
| `period` | Select | Weekly / Monthly / Quarterly / Yearly |
| `start_date` | Date | **(required)** |
| `end_date` | Date | **(required)**, must be >= start_date |
| `alert_threshold_pct` | Int | default 90 |
| `notes` | Small Text | optional |
| `is_active` | Check | default 1 |
| `last_alert_sent_on` | Date | tracks last alert sent to avoid duplicates |

**Validation**: one active Budget per (`category`, `owner_user`). Period
dates validated for correct order. Threshold 0–100.

**Hooks**: `BudgetService.refresh_budget()` recomputes `spent_amount` from
Expense records and checks overspend threshold. Because categories are a
shared pool, a dependent's expense on a guardian-owned category counts
toward the guardian-level (family) Budget: when no dependent-scoped Budget
exists, `refresh_budget()` and `get_budget_usage()` fall back to the
`dependent = NULL` budget so dependent spend feeds `spent_amount`.

---

## 3. Dependent

A family member without desk access.

| Field | Type | Notes |
|---|---|---|
| `guardian` | Link → User | **(required)** — the Individual responsible |
| `dependent_name` | Data | **(required)**, unique per guardian |
| `relationship` | Select | Son / Daughter / Spouse / Parent / Other |
| `default_monthly_allowance` | Currency | **(required)**, >= 0 |
| `telegram_username` | Data | optional |
| `telegram_user_id` | Data | optional, for Telegram identity resolution |
| `allow_carry_forward` | Check | default 1 — whether unused pocket money rolls over |
| `allowed_categories` | Table → **Dependent Category** | optional allow-list of categories the dependent may use |
| `is_active` | Check | default 1 |

**Validation**: `dependent_name` unique per `guardian`. Relationship must
be a valid enum value. Allowance must be numeric and >= 0. Cannot delete
if referenced by an Expense or Pocket Money Allocation.

**Category scoping**: Categories are a shared, guardian-owned pool.
`Dependent.allowed_categories` is the allow-list: an **empty table means the
dependent may use ALL of the guardian's active categories** (the default),
while non-empty restricts the dependent to exactly those rows.
`DependentService.list_allowed_categories()` is the single source of truth
for this "empty = all allowed" fallback; the AI vocabulary loader and the
Telegram category listing both delegate to it.

---

## 3a. Dependent Category (child DocType)

One row of `Dependent.allowed_categories`. Child table (istable), no own
permissions.

| Field | Type | Notes |
|---|---|---|
| `category` | Link → Category | **(required)** — a guardian-owned category |
| `is_active` | Check | default 1 — inactive rows are ignored |

Rows are managed via `DependentService.add_allowed_category()` /
`remove_allowed_category()` (idempotent; accepts a Category doc name or a
case-insensitive category name).

---

## 4. Pocket Money Allocation

| Field | Type | Notes |
|---|---|---|
| `dependent` | Link → Dependent | **(required)** |
| `allocation_period` | Select | Weekly / Monthly / Quarterly / Yearly |
| `allocated_amount` | Currency | **(required)**, > 0 |
| `allocation_date` | Date | **(required)**, defaults to today |
| `carry_forward_amount` | Currency | default 0 |
| `total_available_amount` | Currency (read-only) | recomputed by `PocketMoneyService.refresh_balance()` |
| `remarks` | Small Text | optional |
| `is_active` | Check | default 1 |

**Validation**: one active allocation per dependent. Period validated
against allowed values. Allocation date validated as a real date.

**Rollover**: `PocketMoneyService.rollover_allocation()` deactivates the
current allocation and creates a new one with carry-forward if
`allow_carry_forward` is enabled on the Dependent.

---

## 5. Expense

The single source of truth for all spending.

| Field | Type | Notes |
|---|---|---|
| `owner_user` | Link → User | **(required)** — the Individual |
| `category` | Link → Category | **(required)** |
| `amount` | Currency | **(required)**, > 0 |
| `expense_date` | Date | **(required)**, cannot be in the future |
| `dependent` | Link → Dependent | optional — set when a Dependent logs the expense |
| `description` | Small Text | optional |
| `source` | Select | Manual / Telegram |
| `payment_method` | Data | optional |
| `voice_transcript` | Small Text | optional — raw transcript from voice input |

**Validation**: `category` must belong to the same `owner_user`. `amount`
> 0. `expense_date` not in the future. `source` must be a valid enum value.

**Hooks**: `ExpenseService.create_expense()` calls `BudgetService.refresh_budget()`
and `PocketMoneyService.refresh_balance()` after every create/update/delete.

---

## 6. Telegram Link

Maps a Telegram numeric ID to a Frappe User.

| Field | Type | Notes |
|---|---|---|
| `user` | Link → User | **(required)** |
| `telegram_user_id` | Data | **(required)**, unique across active links |
| `telegram_username` | Data | optional |
| `first_name` | Data | optional |
| `last_name` | Data | optional |
| `language_code` | Data | optional |
| `is_active` | Check | default 1, set to 0 on unlink |
| `linked_on` | Datetime | auto-set |

**Validation**: one active link per `telegram_user_id`. One active link
per `user`. Tokens are stored in Redis (not the database) with a 10-minute
TTL.

**Permissions**: system-managed. Desk users interact via the linking flow,
not by editing records directly.

---

## Relationships Recap

```
User (Individual/Guardian) 1───N Category
User (Individual/Guardian) 1───N Budget            (via Category)
User (Individual/Guardian) 1───N Dependent
Dependent                  1───N Pocket Money Allocation
Dependent                  N───N Category           (via allowed_categories allow-list)
User                       1───N Expense           (owner_user)
Dependent                  1───N Expense           (dependent, optional)
User                       1───1 Telegram Link     (active)
```
