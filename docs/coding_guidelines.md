# Coding Guidelines

## Python Style

- Follow Frappe's own conventions (snake_case for everything, `frappe.get_doc`
  over raw SQL, `frappe._()` for any user-facing string that might need
  translation).
- Type hints on all new function signatures (`def transcribe(file_path: str) -> str:`).
- Docstrings required on every module and every public function — one line
  minimum stating responsibility and what it explicitly does NOT do.
- Max function length: aim for under ~40 lines. If a handler grows past
  that, extract to a service.
- Use tabs for indentation (see `.editorconfig`).

## Module Boundaries (see `docs/architecture.md`)

- `telegram/handlers/*` — parse input, call one service method, format reply.
  No DB access, no AI calls.
- `services/*` — business logic, DB access via ORM, calls `ai/*` when needed.
  Use `ignore_permissions=True` for all `frappe.get_doc`, `insert()`, `save()`,
  `delete()` calls since operations are system-triggered (webhook, jobs).
- `ai/*` — one external API integration per file, no business logic.
- `api/*` — thin whitelisted wrappers around `services/*`, input validation.
- `telegram/services/` — Telegram-specific orchestration, resolves identities,
  calls domain services. Does NOT contain business logic.

## Error Handling

- Never let a raw exception reach the Telegram reply. Catch known error
  types (`ExpenseManagerError` base class) and map them to a friendly
  message (see `docs/error_handling.md`).
- Never swallow exceptions silently — always log with `frappe.logger`.

## Secrets & Config

- All API keys/tokens via `telegram/config.py` getters reading from
  site config or environment variables. Never a literal string in code,
  never committed to git. See `docs/environment.md`.

## Naming Conventions

- DocTypes: PascalCase display name, e.g. "Pocket Money Allocation" →
  module path `pocket_money_allocation`.
- Whitelisted API methods: `verb_noun`, e.g. `create_expense`, `get_budget_status`.
- Telegram handler files: named after the command/flow (`voice.py`, `link.py`).
- Service methods: descriptive names, e.g. `get_recent_expenses()`,
  `create_expense_from_voice()`.

## Git / Commits

- One phase (per `docs/codex_workflow.md`) = one logical commit or small set
  of commits. Commit messages reference the phase, e.g.
  `Phase 6: implement Telegram command routing`.
- No commented-out dead code left in commits.

## Testing Expectations

- Every new service method needs a unit test.
- Every new Telegram handler needs a test that feeds it a mocked Update
  object and asserts the service call + reply.
- AI modules (`ai/*`) are tested against mocked HTTP responses — never
  against the live Sarvam AI / OpenAI APIs in CI.
- All service tests inherit from `ServiceTestCase` in `tests/base.py`.
- See `docs/testing.md` and `docs/testing_strategy.md`.

## Documentation Expectations

- Any new DocType field, API method, or bot command must be reflected back
  into the relevant `docs/*.md` file in the same change — docs are treated
  as part of the deliverable, not an afterthought.

## Security Best Practices

- Use `ignore_permissions=True` in service layer for system-triggered operations
  (webhooks, background jobs, bot commands).
- Guard dependent cross-checks: verify the dependent belongs to the guardian
  owner before fetching allocations or expenses.
- Never commit secrets or API keys.
- All webhook calls verify Telegram's secret token header.
- User authorization always resolves through Telegram Link or Dependent.telegram_user_id.
