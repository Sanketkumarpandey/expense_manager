---
description: Full read-only health check of the expense_manager frontend + backend contract. Reports only, no fixes.
---

Run a full health check on the expense_manager frontend codebase. Don't fix
anything yet — just report. Treat the git working tree at
`/home/korecent/frappe/my-bench/apps/expense_manager` as the source of truth
and the bench at `/home/korecent/frappe/my-bench` for live checks.

## 1. BUILD/COMPILE STATUS
   - Run `yarn build` in `frontend/` (or dev) and report any errors or warnings verbatim,
     not paraphrased.
   - Check for TypeScript/lint errors if applicable (note: this repo has no
     TS; eslint config lives at repo root `.eslintrc` — run `npx eslint frontend/src` if the toolchain allows).

## 2. RUNTIME ERRORS
   - Load the app in headless Chrome (guardian login flow), open every route
     in the sidebar, and report any JS console errors or uncaught exceptions
     per route.
   - Check the network tab for failed/4xx/5xx API calls during normal navigation.
   - A helper smoke script exists at `scratch/e2e_verify.js` — note it only
     covers login + route visits, NOT CRUD round trips. Do not treat its pass
     as proof that create/edit/archive/delete flows work.

## 3. ARCHITECTURE CONSISTENCY
   - Confirm frappe-ui@0.1.278 conventions are followed consistently:
     icon-only buttons use `#prefix` not `#icon`; `surface-gray-1`/`surface-white`
     used, no `surface-base` anywhere in the codebase.
   - Confirm `ResourceState.vue` / `createResource` + `resourceFetcher` pattern is
     used consistently for all list/detail data fetching (flag any page that
     rolled its own loading/error handling instead — e.g. `ReportsPage` and the
     raw `request()` usage in `BudgetsPage`/`DependentsPage`).
   - Confirm `CategoryPicker.vue` / `DependentPicker.vue` / `ConfirmDialog.vue` are
     reused, not duplicated or reimplemented elsewhere.
   - Confirm `no_cache = 1` is still intact on `www/expense_manager.py` (this was
     a real caching bug before — regression-check it).

## 4. BACKEND CONTRACT DRIFT
   - Spot-check that frontend API calls (method names + params) match the
     current backend API signatures in `expense_manager.api.*` — flag any
     mismatch, especially around the guardian/dependent budget-scoping
     migration. Also diff against `docs/api.md`: known drift is that it
     documents budget endpoints WITHOUT the `dependent` param the backend now has.
   - Check GET vs POST method matching (list methods are GET, mutations POST).

## 5. STATE OF THE SITE
   - `default_site` in `sites/common_site_config.json` MUST stay `expense.local`
      (the production Telegram bot site). Flag immediately if it is anything
      else — a past bug repeatedly left it pointing at `expense-test.localhost`
      after tests. NEVER flip it for tests; see `docs/roadmap.md` Phase 33.
   - The test site runs as a SEPARATE explicitly-pinned process, never via
      `default_site`:
      `bench --site expense-test.localhost serve --port 8001 --noreload`
      (test bench) + `FRAPPE_WEB_SERVER_PORT=8001 yarn dev` in `frontend/`
      (test vite on :8081). See `scripts/run-e2e.sh` at the bench root.
   - Verify `expense-test.localhost` resolves (it resolves via the
      `.localhost` TLD / systemd-resolved even without an `/etc/hosts` entry;
      both v4/v6 reach the test servers).
   - Report any test/fixture data left in a stale or inconsistent state:
      query `expense-test.localhost` (db `_4e44216a7dd66144`) for `tabCategory`,
      `tabBudget`, `tabExpense`, `tabDependent`, and `tabDependent Category`
      orphans (child rows whose `parent` has no matching `tabDependent` row).
   - Report which site the running bench (`honcho` → `bench serve --port 8000`)
      actually serves — it must serve `expense.local`, and the test site must
      be reached on :8001 (via `expense-test.localhost:8081` in the browser).

## 6. ROADMAP CHECK
   - Compare current code against `docs/roadmap.md` — list any phase marked
     complete that doesn't actually hold up under the checks above (Phase 31
     "Web Categories + Budgets pages ... live round-trip verified" is the
     prime suspect — its fixtures are NOT in the DB and its verification is not
     reproducible from `scratch/`), and any work-in-progress not yet reflected
     in the roadmap.

Output as a short status table (component/area → OK / broken / unverified)
followed by a plain list of concrete errors found, each with file/line or
route where relevant. No fixes yet — just the report.

$ARGUMENTS
