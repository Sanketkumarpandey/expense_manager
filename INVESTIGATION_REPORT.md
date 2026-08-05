# Investigation Report — Dependent Overspend Warning & Guardian Budget Miscount

- **Date**: 2026-08-03
- **Site**: `expense.local` (`/home/korecent/frappe/my-bench/sites`), bench 5.31.0, Frappe v16, Python 3.14.6
- **App**: `expense_manager` at `/home/korecent/frappe/my-bench/apps/expense_manager/expense_manager`
- **Mode**: read-only. No source files were modified. The only DB writes are the clearly-labeled reproduction rows described in Part A (names/descriptions prefixed `schemaTest`). No git operations were performed.

---

## Part A — Reproduction and Diagnosis

### 1. Reproduction setup

Seeded, using the app's own services (not raw SQL): a guardian (`Administrator`) Food category, a dependent (seeded 13 default categories via `dependent_after_insert`, including its own Food copy), a guardian-level budget and a dependent-scoped budget (both ₹100, threshold 10%), and a pocket-money allocation (₹500) to satisfy the dependent's balance hard-block. Then two spend paths were exercised via `TelegramService.create_expense`.

| Entity | Id | Notes |
|---|---|---|
| Guardian Food category | `k1rqjg3hno` | `dependent=None` (guardian scope) |
| Dependent | `k1rnccjvvm` | `SchemaTestDependent`, `telegram_user_id=1999123456` |
| Dependent Food copy | `k1rohiag4p` | `dependent=k1rnccjvvm` — **different Category doc** for the same name |
| Guardian budget | `k1rftmfcec` | on `k1rqjg3hno`, `dependent=None`, ₹100 / thr 10% |
| Dependent budget | `k1r4n2uoit` | on `k1rohiag4p`, `dependent=k1rnccjvvm`, ₹100 / thr 10% |
| Pocket money allocation | `k1rsuv4mt5` | ₹500, `total_available_amount` = 480 after spends |

### 2. Observed behavior

**Scenario A — dependent logs ₹20 on its OWN Food copy** (`TelegramService.create_expense`, `telegram_service.py:120-159`):

- Reply returned to the dependent:
  `{"success": true, "message": "Expense created successfully.⚠️ You've used 20.0% of your Food budget (₹20.0 of ₹100.0).", "expense": ...}`
- Budgets after the call:

| Budget | category | dependent | spent | result |
|---|---|---|---|---|
| `k1r4n2uoit` (dep-scoped) | `k1rohiag4p` | dep | **20.0** | updated |
| `k1rftmfcec` (guardian) | `k1rqjg3hno` | None | **0.0** | untouched |

- `get_budget_usage(owner, dep_cat, dependent=dep)` → `{budget: k1r4n2uoit, allocated: 100, spent: 20, pct_used: 20, is_overspent: False, alert_threshold_pct: 10}`.
- `get_budget_usage(owner, guardian_cat, dependent=dep)` → **found the guardian budget** (`k1rftmfcec`, spent 0) because the queried category id *is* the guardian's.

**Original bug scenario — no dependent-scoped budget exists** (this is the guardian's normal state: they create one budget on their own Food):

- `get_budget_usage(owner, dep_cat, dependent=dep)` → `None`
- `build_inline_overspend_warning(...)` → `""` — **no warning is ever shown to the dependent**.
- `BudgetService.refresh_budget(owner, dep_cat, dependent=dep)` → no budget matched → no-op → **guardian budget `spent_amount` stays 0 forever** while the dependent spends.

**Scenario B — expense on the GUARDIAN's Food id with `dependent` set (raw insert equivalent):**

- Guardian budget `spent_amount` remains 0.0 at insert (raw insert has no auto-refresh).
- After `BudgetService.refresh_budget(owner, guardian_food)` → **spent = 20.0**. `_calculate_spent_amount` (budget_service.py:424-451) sums `owner_user` + `category` + date range **without a dependent filter** when the budget is guardian-level (lines 439-449) — i.e. a guardian-level budget *does* absorb dependent expenses *when they land on the guardian's category id*.

**Scenario C — reports (owner-user wide):**

- `ReportService.get_expense_summary(owner)` after A + B → `{total_amount: 40.0, expense_count: 2}`. Both the dependent's own-copy expense and the guardian-id expense count toward the guardian's totals.
- `_build_dashboard` (report_service.py) sums `_get_expenses(owner_user)` with no dependent filter; `total_expense` therefore includes every dependent's spend.

### 3. Code path

`TelegramService.create_expense` → `_resolve_identity_or_error` → `ExpenseService.create_expense(owner, category, ..., dependent=...)` (expense_service.py:35-68) → inserts Expense, then `BudgetService.refresh_budget(owner_user, category, dependent=dependent)` (expense_service.py:61). Back in the Telegram service, the reply appends `_get_overspend_warning(owner, expense.category, dependent=dependent)` (telegram_service.py:153, 706) which calls `BudgetService.build_inline_overspend_warning` (budget_service.py:291-323) → `get_budget_usage` (budget_service.py:257-288) → `_get_active_budget_for_category` (budget_service.py:396-422).

Key lookups (all keyed on the **exact Category doc id + scope**):

| Function | Line | Behaviour |
|---|---|---|
| `_get_active_budget_for_category` | budget_service.py:396-422 | `owner_user` + `category` (exact doc) + `is_active` + `dependent` scope |
| `get_budget_usage` fallback | budget_service.py:265-268 | if dep-scoped budget missing, retry **same category id** with `dependent=None` |
| `refresh_budget` fallback | budget_service.py:333-337 | same — retry **same category id** with `dependent=None` |
| `_calculate_spent_amount` | budget_service.py:424-451 | dep budget → `dependent=dep` filter; guardian budget → owner_user-wide sum |
| `build_inline_overspend_warning` | budget_service.py:291-323 | `""` when usage is `None`; also requires `CategoryService.get_category(owner, cat, dependent=dependent)` (budget_service.py:310) |

`CategoryService` enforces scope identity in `_get_category` (category_service.py:118-150): a guardian-scope query refuses a dep-scoped doc and vice-versa, and `list_categories`/`search_categories`/`category_exists`/`create_category` all filter or set the `dependent` field (category_service.py:101-115, 265-269, 308-311). Duplicate names are legal across scopes (`category_exists` scoped per dependent). Uniqueness is enforced only within a scope (category.py:32-37).

### 4. Root cause

**Category identity is duplicated per dependent scope, but budgets are keyed to the exact Category doc.** A dependent is shown and spends against its *own* Food copy (`CategoryService.list_categories(..., dependent=dep)` — telegram_service.py:223-226, 549-562), which is a **different Category doc** from the one the guardian attaches a budget to. Therefore:

1. `refresh_budget(owner, dep_cat, dependent=dep)` matches no budget (guardian's budget is on `guardian_cat`), and the fallback at budget_service.py:333-337 re-queries the **same** `dep_cat` id with `dependent=None`, which still matches nothing.
2. The inline warning falls back the same way (budget_service.py:265-268) → `""`.
3. Guardian-budget `spent_amount` never increments for dependent spends → the "guardian spend miscount".
4. Reports aggregate by `owner_user` without a dependent filter, so the same dependent spend **is** reflected in the guardian's totals → the guardian sees ₹ spent in reports but ₹0 on the budget.

The fallback code and its comments (budget_service.py:266-268 *"dependent expenses still count toward usage"*, 334-336 *"the budget may be guardian-level … covers the whole household"*) describe a **shared category pool** semantics (one category id, budgets keyed by scope on that id). Under the current duplicated-category design the fallback is effectively **dead code**, because the guardian's and dependent's budgets never share a category id.

### 5. Documented vs. genuine bug — verdict

- **Documented/intended**: per-dependent default category seeding (dependent_after_insert → `CategoryService.create_default_categories(..., dependent=doc.name)`, doctype/dependent/hooks.py:5-7; 13 defaults from constants/default_categories.py); guardian-level budgets are household-wide by design (docs/doctypes.md:31-53, docs/roadmap.md completed phases; env default `budget_alert_threshold_pct=90`, docs/environment.md:23).
- **Genuine bug (gap between coded behavior and expressed intent)**: the dependent-overspend warning **fails to fire** and the guardian budget **miscounts** whenever the guardian creates a budget on their own (guardian-scoped) category and the dependent spends on its own copy — which is the normal, UI-supported flow. The mechanism (budget ⇢ exact category doc) is internally consistent, so this is not a crash or an exception; it is a correctness/UX defect caused by the duplicated `Category.dependent` design, and it is precisely the divergence the scheduled job and the API both inherit (see Part B inventory).

Confirmed live numbers: dep-scoped budget + guardian budget on the dep's own spend → dep budget 20.0 / guardian budget 0.0; guardian reports total 40.0. When the spend lands on the guardian's category id instead (shared-pool behavior), `refresh_budget` correctly pushes the guardian budget to 20.0 — **empirically validating the planned shared-pool redesign**.

### 6. Live data on `expense.local` (sanctioned, labeled)

Current counts: Category 14 (1 guardian + 13 dependent-scoped), Dependent 1, Budget 2, Expense 2, Pocket Money Allocation 1. All rows carry `schemaTest` in notes/descriptions (see table in §1). Cleanup command if desired:

```
bench --site expense.local execute "frappe.db.sql('DELETE FROM `tabExpense` WHERE description LIKE \\'schemaTest%\\''); frappe.db.sql('DELETE FROM `tabBudget` WHERE notes LIKE \\'schemaTest%\\''); frappe.db.sql('DELETE FROM `tabPocket Money Allocation` WHERE remarks LIKE \\'schemaTest%\\''); frappe.db.sql('DELETE FROM `tabCategory` WHERE icon=\\'schemaTest\\''); frappe.db.sql('DELETE FROM `tabDependent` WHERE telegram_user_id=\\'1999123456\\''); frappe.db.commit()"
```

---

## Part B — Schema / Linkage Report for the Category↔Dependent Redesign

### 1. Current schema (relevant fields)

- **Category** (`doctype/category/category.json`): `owner_user`, `category_name`, `icon`, `is_active`, **`dependent` (optional Link → Dependent, no `fetch_from`)**; autoname hash; uniqueness per `(owner_user, category_name, dependent-scope)`.
- **Budget** (`doctype/budget/budget.json`): `owner_user`, `category` (Link → Category), **`dependent` (optional)**, `allocated_amount`, `spent_amount`, `period`, `start_date`, `end_date`, `alert_threshold_pct`, `is_active`, `last_alert_sent_on`, `notes`. "One active Budget per (category, owner_user)" (docs/doctypes.md:49).
- **Expense** (`doctype/expense/expense.json`): `owner_user`, `category` (Link → Category), **`dependent` (optional)**, `amount`, `expense_date`, `source`, `payment_method`, `description`, `voice_transcript`.
- **Dependent** (`doctype/dependent/dependent.json`): `dependent_name`, `guardian`, `relationship`, `default_monthly_allowance`, `telegram_username`, `telegram_user_id`, `allow_carry_forward`, `is_active`, `total_savings`, `pending_allocation_since`, `last_allocation_reminder_on`.

### 2. Every place the dependent scope / duplication is wired (file:line)

**Category seeding (the duplication source):**
- `expense_manager/expense_manager/doctype/dependent/hooks.py:5-7` — `dependent_after_insert` seeds a full 13-category default set **per dependent** (`create_default_categories(doc.guardian, dependent=doc.name)`).
- `services/category_service.py:355-383` — `create_default_categories(owner_user, dependent=None)`; seeded for guardian on install (`install.py`) and when "Expense Manager User" role is granted (`doctype/user/hooks.py`).
- `constants/default_categories.py` — 13 default tuples; the shared-pool source list.

**Category service scoping (guard vs. mutate `dependent`):**
- `category_service.py:101-115` `category_exists` (filters `dependent = dep` or `["is","not set"]`)
- `category_service.py:118-150` `_get_category` (strict scope match → CategoryNotFoundError)
- `category_service.py:265-269` `list_categories` (scope filter unless `include_all`)
- `category_service.py:308-311` `search_categories`
- `category_service.py:160-214` `update_category` (incl. `dependent` param)
- `category_service.py:217-246` `archive_category` / `restore_category`
- `category_service.py:329-352` `delete_category` + `_validate_delete` (blocks delete while used by Expense/Budget, category_service.py:417-443)

**Budget service (keyed on category doc + scope):**
- `budget_service.py:42,48` `create_budget` validates category with `dependent` and checks duplicate budget by scope
- `budget_service.py:73` refresh after create; `budget_service.py:133` refresh after update
- `budget_service.py:190-194, 235-239` `list_budgets` / `search_budgets` scope filter
- `budget_service.py:257-288` `get_budget_usage` (+ same-id fallback at 265-268)
- `budget_service.py:291-323` `build_inline_overspend_warning` (catches `CategoryNotFoundError`)
- `budget_service.py:326-362` `refresh_budget` (+ same-id fallback at 333-337)
- `budget_service.py:364-393` `_get_budget` strict `dependent` equality
- `budget_service.py:396-422` `_get_active_budget_for_category` (the core scope match)
- `budget_service.py:424-451` `_calculate_spent_amount` (dep filter vs owner-wide sum)
- `budget_service.py:568-579` `list_all_active_budgets` (system job; returns `dependent`)
- `budget_service.py:589-618` alert claim/cooldown helpers (`dependent` param)

**Expense service (propagates scope + refresh):**
- `expense_service.py:41-42, 53, 61-62` create (validate dep-cat, set `dependent`, refresh budget + pocket balance)
- `expense_service.py:89-128` update (re-validates and refreshes old & new category/dependent)
- `expense_service.py:147-153` delete (refresh)
- `expense_service.py:164-175, 209-214, 222-239, 280-290` queries + `_validate_category`/`_validate_dependent`

**AI parsing (scoped vocabulary — depends on the duplicated copies):**
- `ai_service.py:45-66` `_load_known_categories(owner, dependent)` — builds vocabulary from the dependent-scoped copies; `create_default_categories(..., dependent=dependent)` on empty
- `ai_service.py:74-110` `create_expense_from_text` → `_derive_dependent(category_id, known_categories, dependent)` (221-229) infers the dependent **from the category row's `dependent` field**
- `ai_service.py:130-160` `create_expense_from_audio`
- `ai_service.py:180-215` category matching + fallback category scoped to dependent

**Telegram layer (who sees what):**
- `telegram/services/telegram_service.py:120-159` `create_expense` (dep forced from identity; warning per category/dependent)
- `telegram_service.py:153, 706` `_get_overspend_warning`
- `telegram_service.py:217-226, 253-260` `list_expenses` / category listing scoped to identity
- `telegram_service.py:276, 284, 297` guardian views across dependents (`include_all=True`, `dependent=["is","not set"]`)
- `telegram_service.py:363-412` text/voice creation paths passing `dependent`
- `telegram_service.py:549-562` `list_categories(telegram_user_id)` → dependent-scoped list for the dep, guardian list for the guardian
- `telegram/handlers/expense.py:21` entry point

**REST API (scope passthrough):**
- `api/utils.py:20-44` `resolve_category_id(owner_user, category, dependent)` — resolves against `CategoryService.list_categories(owner, dependent=dependent)`
- `api/categories.py`, `api/budgets.py` (`create_budget` line 22-35, `get_budget_usage` 152-156), `api/expenses.py:55`, `api/reports.py` (all read-only, `dependent` optional param)

**Scheduled jobs:**
- `jobs/budget_alerts.py:28-29` — `refresh_budget(..., dependent=dependent)` + `get_budget_usage(..., dependent=dependent)` per active budget (budgets already carry the dep link)
- `jobs/monthly_rollover.py`, `jobs/pending_allocation_reminders.py` — dependent-keyed, category-independent (unaffected by redesign)

**DocType-side validation:** `doctype/category/category.py:32-37` (duplicate check scoped by dependent), `doctype/expense/expense.py`, `doctype/budget/budget.py`.

**Query Reports (present in DB, some deleted from disk):** `expense_summary`, `category_breakdown`, `dependent_expenses`, `pocket_money_summary` filter by `dependent` (report/*.json). Working-tree `git status` shows the `report/` Query Reports (`budget_utilization`, `category_breakdown`, `dependent_expenses`, `monthly_expense_summary`, `pocket_money_history`) deleted on disk — consistent with a prior decision to move report logic into `services/report_service.py`; `report_service.py` is the canonical aggregation layer.

### 3. Redesign implications (shared pool + child table)

Moving off `Category.dependent` toward a **shared category pool** (one Category row per name per owner) plus a per-dependent child table means every `dependent=`-scoped lookup above must be re-pointed. The linkage map:

1. **`_get_active_budget_for_category` / `get_budget_usage` / `refresh_budget`** (budget_service.py:396-422, 257-288, 326-362) become the **primary beneficiaries**: the existing `dependent=None` fallbacks (already present at 265-268 and 333-337) will actually fire, making dep spends count against the guardian budget and enabling the warning — this is the fix for Part A with no behavioral change to the shared pool.
2. **`CategoryService._get_category` scope guard** (category_service.py:140-148) and `category_exists`/`list_categories`/`search_categories` scope filters (101-115, 265-269, 308-311) become the definition of "dependent access" instead of doc identity; dependent access control (which dependents may see/use which categories) must move to the new child-table membership.
3. **`ai_service._derive_dependent`** (ai_service.py:221-229) infers the dependent from the Category row's `dependent` field — with a shared pool this inference **breaks** and must switch to identity/context or the child-table membership.
4. **Seeding**: `dependent_after_insert` (doctype/dependent/hooks.py:5-7) currently creates 13 duplicate rows per dependent → becomes a link/child-row grant instead of row duplication (data volume goes from `1 + 13×N` to `13 + N×links`).
5. **Unique-name rule**: `validate_duplicate_category` (category.py:32-37) and `category_exists` currently allow the same name across scopes — a shared pool restores the simple `(owner_user, category_name)` uniqueness, which is what docs/doctypes.md:49 already implies for budgets.
6. **Budgets**: `Budget.dependent` can stay as-is (a budget bound to the shared category id with an optional dependent link) — the budget model is already compatible with a shared pool; only category identity changes.
7. **Expense**: `Expense.category` keeps pointing at the shared category id; `Expense.dependent` stays for attribution/reporting. No schema change to Expense required.
8. **Reports**: no change — aggregation is already owner_user-wide.
9. **Migration**: `Category` rows with `dependent` set must be merged into the guardian-scope row (name/icon collision resolution) and Expenses/Budgets re-pointed to the survivor; dependent-category membership materialized into the new child table.

### 4. Risks / open questions for the redesign

- **Budget per dependent**: with a shared pool, a dep-scoped budget and the guardian budget share a category id. `get_budget_usage`/`refresh_budget` pick the dep-scoped budget first (they already do), falling back to the guardian one — precedence must be defined explicitly (current code: dep budget wins, budget_service.py:263-268).
- **`_get_budget` strict equality** (budget_service.py:383-391) treats `dependent` mismatch as NotFound — fine, but callers must pass the right scope.
- **Category rename/deactivation ripple** to dependent visibility via the child table (currently implicit per-copy).
- **Archived categories**: per-copy archives (category_service.py:217-246) need per-dependent override semantics in the shared pool.
- Add any further open questions to `OPEN_QUESTIONS.md` per AGENTS.md rule 8.

### 5. Supporting evidence files
- `services/budget_service.py`, `services/category_service.py`, `services/expense_service.py`, `services/ai_service.py`, `telegram/services/telegram_service.py`, `api/utils.py`, `jobs/budget_alerts.py`, `doctype/dependent/hooks.py`, `doctype/category/category.py`.
- Docs: `docs/doctypes.md:31-53`, `docs/database.md`, `docs/architecture.md`, `docs/api.md`, `docs/environment.md:23`, `docs/roadmap.md`.
- Working tree is dirty (modified services/doctypes/api + deleted `report/*`) — untouched by this investigation.
