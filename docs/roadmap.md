# Roadmap

Tracks what's built vs. planned. See `docs/codex_workflow.md` for the
original phase-by-phase prompts.

## Completed

| Phase | Description | Date |
|---|---|---|
| 1 | Project analysis (read-only) | 2026-07-22 |
| 2 | Telegram architecture doc | 2026-07-22 |
| 3 | Folder skeleton (empty modules) | 2026-07-22 |
| 4 | Telegram configuration (secrets, environment) | 2026-07-22 |
| 5 | Webhook receive + verify + log + enqueue | 2026-07-22 |
| 6 | Command routing (/start, /help, /link, /unlink, unknown) | 2026-07-22 |
| 7 | Account linking (token-based flow) | 2026-07-22 |
| 8 | Voice message receive/download | 2026-07-22 |
| 9 | Sarvam AI speech-to-text integration | 2026-07-22 |
| 10 | Groq LLM expense parsing (text → JSON) | 2026-07-22 |
| 11 | Expense creation from parsed JSON | 2026-07-22 |
| 12 | Reports (Query Reports, Telegram rendering) | 2026-07-22 |
| 13 | Budget alerts (daily scheduled job) | 2026-07-22 |
| 14 | Full service layer (8 services, typed exceptions) | 2026-07-23 |
| 15 | REST API (7 whitelisted endpoint modules) | 2026-07-23 |
| 16 | Dependent management + pocket money allocation | 2026-07-23 |
| 17 | Pocket money rollover (daily scheduled job) | 2026-07-23 |
| 18 | Daily reminders (no-expenses, weekly/monthly summary, low balance) | 2026-07-24 |
| 19 | Extended Telegram commands (expenses, categories, budgets, balance, dependents, pocketmoney, savings, rollover, profile, settings) | 2026-07-24 |
| 20 | Five Frappe Query Reports | 2026-07-24 |
| 21 | Service unit tests (269 tests) | 2026-07-25 |
| 22 | Integration tests (21 cross-service workflow tests, 290 total) | 2026-07-25 |
| 23 | Security audit (ignore_permissions, guardian cross-checks, allow_rename fix) | 2026-07-27 |
| 24 | Savings ledger for pocket money rollover (unused balance → total_savings on Dependent, separate from spendable allocation) | 2026-07-30 |
| 25 | Bug fix pass: free-text/DependentNotFound (AI category scope), guardian /expenses dependent-leak, /pocketmoney ₹ formatting, REST API over-budget warning, pocket-money hard block for dependents (433 tests) | 2026-07-31 |
| 26 | Shared category pool redesign: `Dependent.allowed_categories` allow-list (empty = all guardian categories), removed dependent-scoped `CategoryService`, family-budget fallback so dependent spend feeds guardian Budgets, 3 new REST endpoints (439 tests) | 2026-08-03 |
| 27 | Vue 3 + frappe-ui frontend scaffold (`frontend/` Vite build, SPA served at `/expense_manager` via `website_route_rules`, Guest boot context without CSRF token) | 2026-08-04 |
| 28 | SPA authentication: LoginPage (`POST /login` + full-page reload), authenticated boot with `csrf_token`, route guard on `window.user != 'Guest'`, DashboardPage logout + authenticated POST test; round-trip verified live (login → reload → CSRF-authenticated POST → logout → reload) | 2026-08-04 |
| 29 | Dev-serve re-verification on expense-test.localhost: pinned `default_site` in common_site_config (dev server ignores `serve_default_site`; routes via `get_sites()` → `frappe.get_conf().default_site`), fixed stale-page bug — custom SPA `www/expense_manager.py` sets `no_cache = 1` because frappe's `@cache_html` caches rendered HTML under `website_page::<path>` for 30 min (the whole auth round trip was "failing" because the served boot was a cached Guest page, not a session bug); full round trip re-verified against the live route (127.0.0.1:8000) | 2026-08-04 |
| 30 | Web Expenses page: `ExpensesPage` (list via `list_expenses`, filters for dependent/category/date-range, quick-add free text via new `create_expense_from_text` REST endpoint wrapping `AIService`, create/edit `Dialog` form, delete with `ConfirmDialog`); shared `CategoryPicker`/`DependentPicker` components (frappe-ui `Combobox`); `create_expense_from_text` surfaces a friendly config message when Groq keys are unset; live round-trip verified (create ₹321 → edit ₹456 → delete) against fixture data plus the AI config-error message (444 tests) | 2026-08-04 |
| 31 | Web Categories + Budgets pages: `CategoriesPage` (Active/All toggle via `list_categories`, create/edit with icon preview, archive/restore, delete with in-use guard) and `BudgetsPage` (Active/All toggle, category/dependent filters, merged guardian + per-dependent rows via `list_dependents` + `list_budgets`, per-row usage bars from `get_budget_usage`, Household vs dependent scope chips, overspend/over-threshold red flags, archive/restore/delete); added `disabled` prop to `CategoryPicker`; live round-trip verified headless-Chrome (category create→edit→archive→restore→delete + in-use delete blocked; guardian budget shows pre-existing spend, dependent-scoped budget on same category tracks independently, dependent expense only moves its own budget, ₹80 budget over-spent at 125% flagged) | 2026-08-04 |
| 32 | Phase 4 close-out on `expense-test.localhost`: dev-server routing fixed (vite dev proxy on :8080 → pinned `default_site`; dev-mode `window.user` set before router gate; `optimizeDeps.include: ['feather-icons', 'socket.io-client', 'tippy.js']` pre-bundles the CJS deps frappe-ui pulls in, so the SPA mounts in dev); re-ran the 4-scenario e2e (`scratch/e2e_verify.js`, headless Chrome CDP): 45/45 checks green against fixtures (13 categories, Budget `frg3lsse7n` Food ₹5000, Expense Bills ₹250, Dependent Alex Junior) — category CRUD + delete guard, Bills budget shows pre-existing ₹250 of ₹1,000 at 25% (not flagged), Food household vs Alex-dependent budgets track independently (₹200/₹5000 vs ₹300/₹2000), Shopping ₹200 budget over-spent by ₹300 with red styling + API overspend warning; cleanup returns DB to baseline (spent_amount recomputed via `refresh_budget`); decided Category icon is a free-text emoji `Input` (placeholder "Pick an emoji, e.g. 🛒", maxlength 8) rather than an emoji picker | 2026-08-05 |
| 33 | Phase 5 Part 0 — site-pinning fix: `default_site` now permanently stays `expense.local` (production Telegram bot site). Audit found only historical/stale `default_site` references (`docs/roadmap.md` Phases 29/32 past pinning, `health-check.md` §5) — no live flipping code existed; the past "fixes" were manual `bench set-config` calls. Redesign: test site runs as an explicitly-pinned second process (`bench --site expense-test.localhost serve --port 8001 --noreload` + `FRAPPE_WEB_SERVER_PORT=8001 yarn dev` on :8081), never via default_site; new `scripts/run-e2e.sh` (bench root) pre/post-flights default_site and drives `scratch/e2e_verify.js` (APP_URL now `http://expense-test.localhost:8081/`); `expense-test.localhost` resolves via the `.localhost` TLD (systemd-resolved) so no /etc/hosts edit needed. Confirmed `default_site=expense.local` + Telegram bot round-trips on it. Also automated the tunnel/webhook: `scripts/telegram-tunnel.sh` (kill stale cloudflared via PID-file + pattern fallback, start Quick Tunnel to :8000, poll log for `*.trycloudflare.com` URL, read `scripts/.env` for `TELEGRAM_BOT_TOKEN`/`TELEGRAM_WEBHOOK_SECRET` (secrets not printed), setWebhook → getWebhookInfo verification → live 200/403 secret probe, fail-fast per step; re-run safe). Fixed a dead-tunnel incident: registered trycloudflare hostname had gone NXDOMAIN (Telegram stuck on "530", 3 pending updates); after re-registration pending drained to 0. `.env.example` added; bench root is NOT a git repo so `scripts/.env` cannot be committed (app `.gitignore` already ignores `.env`) | 2026-08-05 |
| 34 | Phase 5 Parts 1–3 — Dependents page + per-dependent allowed-categories (server-enforced) + pocket-money rollover. **Part 2 server-side fix**: allowed-category enforcement previously lived only in the Telegram service, so the REST path (`create_expense`) could bypass it. Added `CategoryNotAllowedError` and `ExpenseService._validate_dependent_category()` (no-op without a dependent; resolves the category id, builds the allow-list via `DependentService.list_allowed_categories(active_only=True)`, raises when the category isn't allowed), wired into `create_expense` and `update_expense` (update re-validates the post-mutation category/dependent pair). New `AllowedCategoriesSection.vue` on each Dependents-page card — collapsible, lazy-loads on expand (placement rationale: per-card keeps the scope obvious next to the dependent's allowance/savings/pocket-money, unlike a separate route; collapses by default so 13 category toggles don't bury the card). Toggle-off on an empty child table seeds the list with every other active category (preserves "empty = all allowed"); per-category busy lock prevents double-clicks mid-seed; "X of Y allowed" badge. Part 3 verified, not rebuilt: the Dependents page already ships Allocate/Update + balance card + manual Rollover per dependent, matching `create_allocation`/`rollover_allocation`; Scenario 6 proves the lifecycle (₹1000 Monthly → spend ₹300 → balance 700 remaining → rollover → fresh zero allocation + ₹700 → `total_savings`, carry-forward). Unit suite 449 OK. **Tooling hardening**: found the 8001 bench serve (`--noreload`) was serving pre-validation code while unit tests passed — `run-e2e.sh` now evicts any stale listener on :8001/:8081 before each run and tracks real listening PIDs (port-based) so cleanup kills the actual processes instead of orphaned subshells; harness adds `waitForApi` polling (switch toggles flip optimistically, so server-state waits replaced flaky fixed sleeps), waits for the busy guard to clear before clicking a switch twice, and self-heals by deleting a "blocked" expense that should never have been created (prevents ₹50 leak accumulation across runs; 4 leaked rows purged). Final e2e: **85 passed / 0 failed**, post-flight `default_site=expense.local` intact | 2026-08-05 |

## In Progress

_(none)_

## Planned

- Production deployment (VPS, Nginx, Supervisor, TLS)
- Webhook management UI in Desk
- Bulk expense import
- Export to CSV/PDF
- Multi-currency support
- Non-Telegram bot channels (WhatsApp, etc.)
- Mobile app
- Chart image generation for Telegram (PNG reports)
- Dependent-specific role permissions (currently admin-only Desk access)

## Explicitly Out of Scope (for now)

- Multi-currency
- Non-Telegram bot channels (WhatsApp, etc.)
- Production/VPS deployment (deferred — current target is local bench only)
- Mobile app
