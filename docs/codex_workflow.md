# Codex Workflow — Phase-by-Phase Prompts

Run these one at a time, in order. **Do not skip ahead.** Each phase ends
in a working, testable state — verify with `bench run-tests` before moving
to the next. After each phase, update `docs/roadmap.md`'s "Completed"
checklist.

Give the agent access to this whole `docs/folder` and `AGENTS.md` before
Phase 1.

---

### Phase 1 — Project Analysis (read-only)

```
You are working inside an existing Frappe v16 application named Expense
Manager. Review the complete repository before making changes.

Your responsibilities:
- Understand all existing doctypes
- Understand hooks.py
- Understand the API structure
- Understand reports
- Understand naming conventions
- Understand coding style

Do not modify any files.

Produce a document named PROJECT_ANALYSIS.md containing:
1. Repository structure
2. Existing doctypes
3. Existing APIs
4. Existing reports
5. Existing hooks
6. Existing scheduled jobs
7. Existing permission system
8. Suggestions for Telegram integration
9. Missing infrastructure
10. Risks

Only create PROJECT_ANALYSIS.md.
```

### Phase 2 — Telegram Architecture Design (docs only)

```
Using PROJECT_ANALYSIS.md and docs/architecture.md, design the Telegram
architecture in more implementation-level detail than the existing docs.

Do not implement anything.

Create telegram_architecture.md including:
- Folder structure
- Webhook flow
- Authentication
- Account linking
- Voice processing pipeline
- Command routing
- Error handling
- Retry policy
- Security
- Logging
- AI integration (Sarvam AI + OpenAI GPT)
- Frappe integration
- Sequence diagrams
```

### Phase 3 — Folder Skeleton (no logic)

```
Implement only the folder structure described in docs/architecture.md and
telegram_architecture.md. Create empty modules with docstrings only — no
logic.

Create:
telegram/
  handlers/
  services/
  middleware/
  utils/
  bot.py
  router.py
  __init__.py
ai/
  speech_to_text.py
  ai_parser.py
  exceptions.py
  __init__.py
services/
  expense_service.py
  budget_service.py
  dependent_service.py
  report_service.py
  exceptions.py

All files should contain proper docstrings explaining their purpose, per
docs/coding_guidelines.md. No implementation logic yet.
```

### Phase 4 — Telegram Configuration

```
Implement configuration reading per docs/environment.md.

Requirements:
- Store bot token, Sarvam AI key, OpenAI key securely (site config /
  environment variables, never hardcoded)
- Support a use_mock_ai_apis flag for tests/dev
- Never hardcode secrets

Create telegram/config.py (or extend config.py) with getter functions:
get_telegram_bot_token(), get_telegram_webhook_secret(),
get_sarvam_api_key(), get_openai_api_key(), get_openai_model().

Update hooks.py if required. Do not implement handlers yet.
```

### Phase 5 — Webhook (receive, verify, log only)

```
Implement the Telegram webhook per docs/webhook.md.

Requirements:
- Receive updates (allow_guest whitelisted POST method)
- Verify the secret token header
- Log every update (update_id, type, timestamp)
- Deduplicate by update_id
- Return HTTP 200 quickly; enqueue actual processing as a background job
- No command handling yet — just receive, verify, log, enqueue a no-op job

Create the webhook endpoint, a webhook registration utility script, a
webhook testing utility, and unit tests per docs/testing_strategy.md §3.
```

### Phase 6 — Command Routing

```
Implement command routing per docs/telegram_commands.md.

Support /start, /help, /link, /unlink, and unknown-command fallback.
Only routing and reply text — no OTP generation, no DB writes to
Telegram Link yet (stub those calls).

Write tests per docs/testing.md.
```

### Phase 7 — Account Linking

```
Implement Telegram account linking per docs/telegram_commands.md and
docs/doctypes.md (Telegram Link).

Flow: /link generates a short-lived token (via POST /api/method/...generate_link_code)
→ user sends /link <token> to bot → Telegram Link record created.
Support /unlink (idempotent). Write tests.
```

### Phase 8 — Voice Message Receive (no transcription yet)

```
Implement voice message handling per docs/webhook.md §5.

Receive the Telegram Voice message, download the file via getFile, store
it as a temp file, and delete it after processing (which is a no-op stub
for now). Do not perform speech recognition yet. Write tests.
```

### Phase 9 — Sarvam AI Integration

```
Integrate Sarvam AI speech-to-text per docs/ai.md §1.

Implement ai/speech_to_text.py: transcribe(file_path, language_hint) → str.
Include retry/backoff per docs/error_handling.md. Support
use_mock_ai_apis for tests. Unit tests against mocked HTTP responses only
— never call the live API in tests.
```

### Phase 10 — OpenAI GPT Expense Parsing

```
Integrate OpenAI GPT per docs/ai.md §2 and docs/prompts.md.

Implement ai/ai_parser.py: parse_expense(text, known_categories) → dict,
using the exact prompt and JSON schema in docs/prompts.md, plus
validate_expense_json() per that doc's validation table. Only JSON out.
Unit tests against mocked responses covering: valid extraction, invalid
category, null amount, malformed JSON.
```

### Phase 11 — Expense Creation

```
Using the parsed JSON from Phase 10, create Expense records via
services/expense_service.create_from_voice(), reusing the existing
Expense DocType and its validation (docs/doctypes.md §5). Do not
duplicate business logic elsewhere. Return a summary object for the
Telegram reply. Wire this into handlers/voice.py end to end. Write
integration tests per docs/testing_strategy.md §5.
```

### Phase 12 — Reports

```
Implement /report weekly and /report monthly per docs/telegram_commands.md,
reusing services/report_service.py. Generate PNG charts
(api.report.generate_chart_png). Send via Telegram sendPhoto. Write tests.
```

### Phase 13 — Budget Alerts

```
Implement budget overspend notifications per docs/telegram_commands.md
("Budget Overspend Notification") and docs/doctypes.md §2 (Budget). When
spent_amount crosses alert_threshold_pct of allocated_amount, push a
Telegram notification to the Individual. Reuse existing validation. Write
tests.
```

### Phase 14+ — Future Phases (not yet detailed)

- Full service layer (8 services, typed exceptions)
- REST API (7 whitelisted endpoint modules)
- Dependent management + pocket money allocation
- Pocket money rollover (daily scheduled job)
- Daily reminders (no-expenses, weekly/monthly summary, low balance)
- Extended Telegram commands (expenses, categories, budgets, balance, etc.)
- Five Frappe Query Reports
- Service unit tests (269 tests)
- Integration tests (21 cross-service workflow tests, 290 total)
- Security audit (ignore_permissions, guardian cross-checks, allow_rename fix)
- Documentation updates

Write the detailed prompt for each future phase only once the prior phase
is complete and verified — don't pre-write prompts for work whose
prerequisites might change.

---

## Running Each Phase

1. Paste the phase prompt into Codex (`codex --yolo` or equivalent —
   see below).
2. Let it run to completion.
3. Run `bench --site expense.local run-tests --app expense_manager`.
4. Review the diff.
5. Check off the phase in `docs/roadmap.md`.
6. Move to the next phase — in a fresh Codex invocation if the CLI doesn't
   retain context well across a long session.

## Running Codex in Autonomous Mode

```bash
cd ~/frappe-bench
codex --yolo .
```

Check `codex --help` for the current flag names (`--yolo`,
`--approval-mode never`, `--dangerously-bypass-approvals`, etc.) since
these can change between CLI versions.
