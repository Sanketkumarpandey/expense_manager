# Database Overview

This is a summary view. For the authoritative, field-by-field spec (types,
validations, permissions), see `docs/doctypes.md`.

## Entity-Relationship Summary

```
User (Frappe core)
  └── 1:N ── Category
  └── 1:N ── Budget            (per Category, per month/period)
  └── 1:N ── Dependent
  │            └── 1:N ── Pocket Money Allocation
  │            └── 1:N ── Expense (created_by = Dependent)
  └── 1:N ── Expense           (created_by = Individual)
  └── 1:1 ── Telegram Link      (telegram_user_id ↔ User)

Expense
  ├── Link → Category
  ├── Link → User (owner_user)
  ├── Link → Dependent (optional, set when dependent logs expense)
  └── fields: source (Manual/Telegram), voice_transcript

Budget
  ├── Link → Category
  ├── fields: allocated_amount, spent_amount (computed), period, dates

Pocket Money Allocation
  ├── Link → Dependent
  ├── fields: allocated_amount, carry_forward_amount, total_available (computed)
```

## Table-Level Notes

- **Expense** is the single source of truth for all spending, regardless of
  who logged it or how (voice, text, desk form). The `source` field distinguishes
  Manual vs Telegram origin. `dependent` is optional (set when a dependent logs).
- **Budget** and **Pocket Money Allocation** are separate DocTypes because
  their business rules differ (budgets trigger category overspend alerts;
  pocket money tracks a spendable balance with period-end rollover).
- **Telegram Link** is its own DocType (not a field on User) so both
  `User` and `Dependent` can link a `telegram_user_id` through the same
  mechanism, and so unlink/relink history is retained.
- No raw SQL joins are needed for the reports in scope — Frappe's Query
  Report + `frappe.db.get_list` with filters covers weekly/monthly
  aggregation by category and by owner.
- **Category** uniqueness is scoped per `owner_user` (case-insensitive).
- **Dependent** uniqueness is scoped per `guardian`.
- All DocType record operations in the service layer use `ignore_permissions=True`
  because system-triggered operations (webhooks, jobs, bot commands) bypass
  the standard Desk permission model.

## Indexes to Add

- `Expense.telegram_id` (if stored) — fast lookup during webhook processing
- `Expense.(owner_user, expense_date)` — report queries
- `Telegram Link.telegram_user_id` — unique index, used on every incoming update
- `Budget.(owner_user, category)` — uniqueness check

See `docs/doctypes.md` for the full field list per DocType.
