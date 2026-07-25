# Database Overview

This is a summary view. For the authoritative, field-by-field spec (types,
validations, permissions), see `docs/doctypes.md`.

## Entity-Relationship Summary

```
User (Frappe core)
  └── 1:1 ── Individual Profile (extends User via child table / linked doctype)
                 ├── 1:N ── Category
                 ├── 1:N ── Budget            (per Category, per month)
                 ├── 1:N ── Dependent
                 │            └── 1:N ── Expense (created_by = Dependent)
                 ├── 1:N ── Expense           (created_by = Individual)
                 └── 1:1 ── Telegram Link      (telegram_id ↔ User)

Dependent
  ├── 1:1 ── Telegram Link (telegram_id ↔ Dependent)
  ├── 1:N ── Pocket Money Allocation (per month)
  └── 1:N ── Expense

Expense
  ├── Link → Category
  ├── Link → User or Dependent (owner)
  └── field: source (web | telegram)

Budget
  ├── Link → Category
  └── fields: month, allocated_amount, spent_amount (computed)

Pocket Money Allocation
  ├── Link → Dependent
  └── fields: month, allocated_amount, spent_amount (computed), rolled_over_from
```

## Table-Level Notes

- **Expense** is the single source of truth for all spending, regardless of
  who logged it or how (voice, text, desk form). A `source` field and an
  `owner_type` (`Individual` / `Dependent`) distinguish context.
- **Budget** and **Pocket Money Allocation** are separate DocTypes because
  their business rules differ (budgets trigger category overspend alerts;
  pocket money tracks a spendable balance with month-end rollover).
- **Telegram Link** is its own lightweight DocType (not a field on User)
  so both `User` and `Dependent` can link a `telegram_id` through the same
  mechanism, and so unlink/relink history can be kept.
- No raw SQL joins are needed for the reports in scope — Frappe's Query
  Report + `frappe.db.get_list` with filters covers weekly/monthly
  aggregation by category and by owner.

## Indexes to Add

- `Expense.telegram_id` (if stored) — fast lookup during webhook processing
- `Expense.(owner, date)` — report queries
- `Telegram Link.telegram_id` — unique index, used on every incoming update

See `docs/doctypes.md` for the full field list per DocType.
