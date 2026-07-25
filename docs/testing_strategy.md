# Testing Strategy

Five layers, each with a distinct purpose. See `docs/testing.md` for the
quick "how to run" reference and file layout.

## 1. Unit Tests — DocTypes & Services

Scope: validation logic, computed fields, business rules in isolation.

Examples:
- `Category` name uniqueness per owner
- `Budget` overspend detection at threshold %
- `Expense` requires `category` to belong to the same Individual as the
  Dependent's guardian
- `Pocket Money Allocation` rollover math (unused amount → savings_balance)

Run against a test site's DB (Frappe's standard test framework), no
external HTTP calls.

## 2. Integration Tests — API Layer

Scope: whitelisted methods in `api/*`, exercised end-to-end against the
test database (create → read → assert side effects), still no external AI
calls.

Example: `api.expense.create_expense(...)` → assert `Budget.spent_amount`
updates and an overspend notification job is enqueued when threshold is
crossed.

## 3. Webhook Tests

Scope: `telegram/webhook.py` in isolation.

- Valid secret token → 200 + job enqueued
- Invalid/missing secret token → 403, nothing enqueued
- Duplicate `update_id` → 200, no second job enqueued
- Malformed JSON body → handled gracefully, logged, 200 returned (never
  let Telegram see a 500 or it will keep retrying aggressively)

Use Frappe's test client to POST synthetic Telegram update payloads
(fixtures under `tests/fixtures/telegram_updates/`).

## 4. AI Module Tests (Mocked)

Scope: `ai/speech_to_text.py`, `ai/ai_parser.py` — **never** call live
Sarvam AI / OpenAI in automated tests.

- `speech_to_text.transcribe()`: mock the HTTP response for success,
  timeout, and empty-transcript cases; assert correct return value / raised
  exception in each.
- `ai_parser.parse_expense()`: mock OpenAI responses for a valid extraction,
  an invalid-category extraction (must fall back to "Uncategorized"), a
  null-amount case (must trigger clarification), and malformed JSON (must
  raise `ExpenseParseError`).

Fixtures live in `tests/fixtures/sarvam_responses/` and
`tests/fixtures/openai_responses/`.

## 5. End-to-End Tests (Local, Manual + Scripted)

Scope: the full voice-note-to-Expense flow, run against a local bench with
`use_mock_ai_apis=1` (see `docs/environment.md`) so it's deterministic and
free to run repeatedly.

Scripted E2E test:
1. Construct a synthetic Telegram `Update` with a `voice.file_id`
2. Mock Telegram's `getFile`/file download to return a fixture audio file
3. Mock Sarvam AI to return a fixed transcript
4. Mock OpenAI to return a fixed JSON extraction
5. POST to the webhook endpoint
6. Assert: an `Expense` record was created with the expected fields, and
   the expected reply text was "sent" (capture outbound `sendMessage`
   calls via a mock instead of hitting real Telegram)

Manual E2E (pre-demo checklist):
- Real voice note through the real bot, real Sarvam AI + OpenAI keys, on
  local bench + ngrok tunnel (see `docs/deployment.md`)
- Confirm reply arrives, Expense appears in the desk, budget/report reflect
  it

## Coverage Expectations by Phase

Per `docs/codex_workflow.md`, each phase should add tests before being
marked complete in `docs/roadmap.md`. A phase is not done if
`bench run-tests` doesn't pass cleanly.

## What's Explicitly Not Tested Automatically

- Actual Sarvam AI / OpenAI accuracy (that's a manual/product-quality
  concern, not a CI concern)
- Telegram's own delivery guarantees
- Load/performance testing (out of scope for this phase — revisit if/when
  moving beyond local bench, see `docs/deployment.md`)
