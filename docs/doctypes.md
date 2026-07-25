# DocTypes — Full Specification

Conventions: `Link` fields reference another DocType by name. `Select`
fields list their options. Required fields are marked **(required)**.
Every DocType listed here needs a matching entry in `docs/testing.md`.

---

## 1. Category

Represents an expense category (Food, Medical, Travel, ...).

| Field | Type | Notes |
|---|---|---|
| `category_name` | Data | **(required)**, unique per owner |
| `owner_user` | Link → User | **(required)** — the Individual who created it |
| `icon` | Data | optional, emoji or icon key for Telegram replies |
| `is_active` | Check | default 1 |

**Validation**: `category_name` unique per `owner_user` (case-insensitive).

**Permissions**: Individual: full CRUD on their own Categories. Dependent:
read-only, scoped to their linked Individual's categories.

---

## 2. Budget

Monthly allocation per Category.

| Field | Type | Notes |
|---|---|---|
| `category` | Link → Category | **(required)** |
| `month` | Data (YYYY-MM) | **(required)** |
| `allocated_amount` | Currency | **(required)**, > 0 |
| `spent_amount` | Currency (read-only, computed) | sum of linked Expenses this month |
| `owner_user` | Link → User | **(required)** |
| `alert_threshold_pct` | Int | default 90 — trigger a warning before full overspend |

**Validation**: one Budget per (`category`, `month`, `owner_user`) — no
duplicates. `allocated_amount` must be positive.

**Hooks**: `on_update` of a linked Expense recomputes `spent_amount` and
triggers `services/budget_service.check_overspend()`.

**Permissions**: Individual only (Dependents cannot view/edit budgets).

---

## 3. Dependent

A family member without desk access.

| Field | Type | Notes |
|---|---|---|
| `dependent_name` | Data | **(required)** |
| `relation` | Select | Child / Spouse / Parent / Other |
| `guardian_user` | Link → User | **(required)** — the Individual responsible |
| `linked_user` | Link → User | auto-created restricted User for permission scoping |
| `is_active` | Check | default 1 |

**Validation**: creating a Dependent auto-creates a restricted Frappe `User`
with role `Dependent`, used purely for permission checks (no desk login
needed — Telegram is the interface).

**Permissions**: Individual: full CRUD on their own Dependents. Dependent:
read-only on their own record.

---

## 4. Pocket Money Allocation

| Field | Type | Notes |
|---|---|---|
| `dependent` | Link → Dependent | **(required)** |
| `month` | Data (YYYY-MM) | **(required)** |
| `allocated_amount` | Currency | **(required)** |
| `spent_amount` | Currency (computed) | sum of Dependent's Expenses this month |
| `rolled_over_from` | Link → Pocket Money Allocation | optional, previous month's leftover |
| `savings_balance` | Currency | accumulated rollover total |

**Validation**: one record per (`dependent`, `month`). Rollover logic lives
in `services/dependent_service.rollover_pocket_money()`, not in a DocType
hook, to keep it testable and explicit.

**Permissions**: Individual: full CRUD for their own Dependents. Dependent:
read-only on their own record.

---

## 5. Expense

The single source of truth for all spending.

| Field | Type | Notes |
|---|---|---|
| `amount` | Currency | **(required)**, > 0 |
| `category` | Link → Category | **(required)** |
| `merchant` | Data | optional, free text (e.g. "Zomato") |
| `date` | Date | **(required)**, defaults to today |
| `notes` | Small Text | optional |
| `owner_type` | Select | Individual / Dependent — **(required)** |
| `owner` | Dynamic Link (User or Dependent) | **(required)** |
| `source` | Select | web / telegram — **(required)** |
| `raw_transcript` | Small Text | optional — the original transcribed text, kept for audit/debugging |
| `ai_confidence` | Float | optional, 0-1, set when created via voice |

**Validation**: `category` must belong to the same owning Individual (a
Dependent's Expense uses their guardian's Categories). `amount` > 0.

**Permissions**: Individual: full CRUD on their own + their Dependents'
Expenses. Dependent: create + read on their own Expenses only; no delete
(ask guardian) — confirm this rule with the user before Phase 11 if it's
ambiguous (see `AGENTS.md` rule 8).

---

## 6. Telegram Link

Maps a Telegram numeric ID to a User or Dependent.

| Field | Type | Notes |
|---|---|---|
| `telegram_id` | Data | **(required)**, unique |
| `linked_type` | Select | Individual / Dependent |
| `linked_name` | Dynamic Link | the User or Dependent |
| `linked_at` | Datetime | auto-set |
| `otp` | Data | transient, cleared after verification |
| `otp_expires_at` | Datetime | transient |
| `is_active` | Check | default 1, set to 0 on `/unlink` |

**Validation**: `telegram_id` unique across active links (a Telegram
account can only be linked to one Individual/Dependent at a time).

**Permissions**: system-managed; not directly editable via desk UI by
end users beyond linking/unlinking through the bot flow.

---

## Relationships Recap

```
User (Individual) 1───N Category
User (Individual) 1───N Budget            (via Category)
User (Individual) 1───N Dependent
Dependent         1───N Pocket Money Allocation
User / Dependent  1───N Expense           (via owner_type + owner)
User / Dependent  1───1 Telegram Link
```

## Seed Data (suggested defaults on install)

Default Categories to seed for a new Individual: Food, Travel, Medical,
Utilities, Shopping, Entertainment, Uncategorized. Confirm this list before
Phase 1 completes if the user wants a different starting set.
