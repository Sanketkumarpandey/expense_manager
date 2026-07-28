# Telegram Architecture

## 1. Overall Telegram Architecture

Telegram is an interface to the Expense Manager domain, not a separate source
of financial data. A Telegram update enters through a Frappe webhook, is
acknowledged immediately, and is processed by a background worker. The bot
routes the normalized update to a handler; handlers coordinate one use case
and format replies, while services own business rules and DocTypes remain the
source of truth.

```text
Telegram user
  → Telegram Bot API
  → Frappe webhook
  → update validation, logging, deduplication, enqueue
  → background bot dispatcher and router
  → handler → TelegramService → domain services → API/DocType/Report
                    ↘ AI adapters (voice only)
  → Telegram API client → Telegram user
```

The webhook is the only public bot ingress. The system uses Telegram's
`update_id` for idempotency and a Telegram Link record or Dependent.telegram_user_id
to map a Telegram identity to an Individual or Dependent before allowing
protected operations.

## 2. Complete Folder Structure

```text
expense_manager/
├── api/
│   ├── expenses.py              # Whitelisted expense operations
│   ├── budgets.py               # Whitelisted budget operations
│   ├── categories.py            # Whitelisted category operations
│   ├── dependents.py            # Whitelisted dependent operations
│   ├── pocket_money.py          # Whitelisted pocket money operations
│   ├── reports.py               # Summary data operations
│   └── telegram.py              # Link code generation and status
├── ai/
│   ├── __init__.py
│   ├── exceptions.py            # SpeechToTextError, ExpenseParseError
│   ├── speech_to_text.py        # Sarvam audio-to-text adapter only
│   └── ai_parser.py             # OpenAI text-to-expense JSON adapter only
├── services/
│   ├── exceptions.py            # Domain-facing service exceptions (15 classes)
│   ├── expense_service.py       # Expense creation, retrieval, deletion
│   ├── budget_service.py        # Budget CRUD, refresh, overspend checks
│   ├── category_service.py      # Category CRUD, default creation
│   ├── dependent_service.py     # Dependent CRUD, validation
│   ├── pocket_money_service.py  # Allocation CRUD, balance, rollover
│   ├── report_service.py        # Weekly/monthly summary, message builders
│   └── telegram_link_service.py # Link CRUD, token-based linking
├── telegram/
│   ├── __init__.py
│   ├── config.py                # Telegram/AI configuration getters
│   ├── webhook.py               # Guest POST ingress, validation, enqueue
│   ├── webhook_management.py    # Webhook register/deregister utilities
│   ├── bot.py                   # Background update dispatcher
│   ├── router.py                # Update type/command to handler mapping
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py             # /start — welcome message
│   │   ├── help.py              # /help — command list (15 commands)
│   │   ├── link.py              # /link — account linking
│   │   ├── unlink.py            # /unlink — account unlinking
│   │   ├── voice.py             # Voice note → expense
│   │   ├── expense.py           # /expenses, /categories
│   │   ├── budget.py            # /budgets, /balance
│   │   ├── report.py            # /report — spending report
│   │   ├── dependent.py         # /dependents, /pocketmoney, /savings, /rollover
│   │   ├── account.py           # /profile, /settings
│   │   └── unknown.py           # Fallback for unrecognized input
│   ├── services/
│   │   └── telegram_service.py  # Identity resolution + domain orchestration
│   ├── middleware/
│   │   ├── auth.py              # Link resolution
│   │   └── logging.py           # Update lifecycle logging
│   └── utils/
│       ├── helpers.py            # get_telegram_user_id, etc.
│       └── file_download.py      # Voice file download + temp storage
├── jobs/
│   ├── budget_alerts.py          # Daily budget overspend alerts
│   ├── reminders.py              # Daily reminders (no-expenses, summary, low balance)
│   ├── monthly_rollover.py       # Monthly pocket money rollover
│   └── reports.py                # Scheduled report generation
├── doctype/                       # 6 Frappe DocTypes
├── report/                        # 5 Frappe Query Reports
├── templates/                     # Frappe templates
├── public/                        # Client-side assets
├── hooks.py                       # Active scheduler_events, whitelisted methods
├── config.py                      # App configuration
├── pyproject.toml                 # Dependencies (matplotlib, openai, requests)
└── tests/
    ├── base.py                    # Shared test fixtures, Frappe mocks, _make_doc
    ├── test_expense_service.py    # 85 tests
    ├── test_telegram_link_service.py # 28 tests
    ├── test_ai_service.py         # 30 tests
    ├── test_report_service.py     # 30 tests
    ├── test_dependent_service.py  # 22 tests
    ├── test_category_service.py   # 14 tests
    ├── test_budget_service.py     # 18 tests
    ├── test_pocket_money_service.py # 18 tests
    ├── test_integration.py        # 21 tests (cross-service workflows)
    ├── test_reminders.py          # 16 tests
    ├── test_router.py             # 4 tests
    ├── test_webhook.py            # 9 tests
    ├── test_webhook_management.py # 2 tests
    ├── test_telegram_service.py   # 2 tests
    └── test_telegram_config.py    # 5 tests
```

**Total: 290 tests.**

`telegram/services/` is intentionally limited to Telegram presentation
concerns. It must not duplicate the app-level business services in
`services/`.

## 3. Component Responsibilities

| Component | Responsibility | Explicitly excluded |
|---|---|---|
| `telegram/webhook.py` | Verify a Telegram delivery, deduplicate it, enqueue it, return quickly. | Routing, AI work, expense writes, reply formatting. |
| `telegram/bot.py` | Dispatch one queued update via router. | Domain rules and direct persistence. |
| `telegram/router.py` | Select a handler based on command, voice, callback, or fallback. | Database access and AI calls. |
| Handlers | Parse Telegram input, call one TelegramService method, format reply. | Direct DocType/DB access and AI calls. |
| `telegram/services/telegram_service.py` | Resolve identity, orchestrate domain services, format messages. | Business logic (delegates to services/). |
| App services | Business workflows, ORM/DocType interaction, permission-aware validation. | Telegram message layout and raw update parsing. |
| API modules | Whitelisted reusable boundary over services. | Telegram-specific presentation. |
| AI adapters | Provider calls and normalization only. | Database writes and expense-policy decisions. |
| DocTypes/Reports | Schema validation, Frappe permissions, and report data. | Telegram and external AI transport. |
| Jobs | Scheduled tasks (budget alerts, reminders, rollover). | Real-time user interaction. |

All new modules and public functions must use type hints and docstrings,
Frappe conventions, `frappe.logger("expense_manager")` outside normal request
handling, and ORM/Frappe primitives rather than raw SQL.

## 4. Incoming Webhook Flow

1. Telegram POSTs an update to
   `/api/method/expense_manager.telegram.webhook.handle`.
2. The guest, POST-only Frappe method compares
   `X-Telegram-Bot-Api-Secret-Token` with configured
   `telegram_webhook_secret`. A missing or mismatched value returns 403 and
   performs no processing.
3. The endpoint parses the JSON body. A malformed payload is logged and
   acknowledged with HTTP 200 so Telegram does not repeatedly retry it.
4. It records operational metadata and checks `update_id` idempotency via
   Redis (24h TTL). Duplicate updates return `{"ok": true}` without another job.
5. A unique update is passed to `frappe.enqueue` for background dispatch.
6. The endpoint returns `{"ok": true}` immediately. It never transcribes
   audio, calls OpenAI, creates an Expense, or sends a reply inline.

This separation keeps webhook latency below Telegram's retry threshold and
prevents duplicate processing when Telegram re-delivers an update.

## 5. Outgoing Telegram API Flow

Handlers use `bot.send_message()` for text replies. The transport reads the
bot token from configuration and sends via Telegram's Bot API.

The caller supplies a chat target and formatted text. The wrapper returns/raises
a transport failure for the top-level error strategy. It does not decide
whether a user is authorized or whether an expense is valid.

## 6. Authentication Strategy

There are two distinct controls:

1. **Webhook authenticity:** Telegram's secret-token header protects the
   guest ingress endpoint. It is mandatory for every delivery.
2. **User authorization:** `telegram_user_id` is resolved through either:
   - An active `Telegram Link` (Individual), or
   - A `Dependent.telegram_user_id` field (Dependent)

The resolved identity determines `owner_user` and permissions.

Unlinked users may use `/start`, `/help`, and `/link`; protected commands,
voice processing, reports, budgets, and pocket-money access require a valid
link. Persona checks occur after link resolution: only Individuals may manage
budgets and request the documented household report view, while
`/pocketmoney` is limited to Dependents.

## 7. Telegram Account Linking Lifecycle

```text
Unlinked Telegram ID
  └─ /link <token> → token obtained from Desk API
                      └─ TelegramLinkService.verify_and_link()
                           └─ active Telegram Link to Individual or Dependent
                                └─ protected Telegram operations allowed
                                     └─ /unlink → link marked inactive
                                          └─ Unlinked Telegram ID
```

An active Telegram ID may map to only one Individual or Dependent. A Telegram
ID already linked elsewhere must be unlinked before a new link can be created.

## 8. Linking Flow

1. Desk user calls `POST /api/method/expense_manager.api.telegram.generate_link_code`
   → generates short-lived token, returns `{token, expires_at}`
2. User sends `/link <token>` to the bot
3. `handlers/link.py` calls `TelegramService.complete_link(telegram_user_id, token, ...)`
4. `TelegramLinkService.verify_and_link()` validates token, creates Telegram Link record
5. Next interaction resolves as linked
6. `/unlink` deactivates the link (idempotent)

## 9. Voice Processing Pipeline

1. The router recognizes `message.voice`; authentication happens before processing.
2. `handlers/voice.py` calls `file_download.download_voice_file(file_id)` to get temp path.
3. `TelegramService.create_expense_from_voice(telegram_user_id, file_path)`:
   a. Resolves identity (Individual or Dependent)
   b. `AIService.create_expense_from_audio(owner_user, file_path, dependent)`
      - `speech_to_text.transcribe(file_path)` → Sarvam AI → text
      - `ai_parser.parse_expense(transcript, known_categories)` → OpenAI → JSON
      - `ExpenseService.create_expense(...)` → Expense DocType
   c. `BudgetService.refresh_budget()` + `PocketMoneyService.refresh_balance()`
   d. Returns formatted message with optional overspend warning
4. Temp file deleted in `finally` block
5. Reply: "Logged ₹<amount> under <category>."

## 10. Command Routing Architecture

The router performs deterministic classification in this order: voice note,
recognized command, then unknown input. It extracts the command and arguments,
but does not interpret business meaning or access the database.

| Input | Handler | Required persona |
|---|---|---|
| `/start` | `start.py` | Either; persona-aware when linked |
| `/help` | `help.py` | Either |
| `/link <token>` | `link.py` | Either (unlinked preferred) |
| `/unlink` | `unlink.py` | Guardian |
| Voice message | `voice.py` | Either (linked) |
| `/expenses` | `expense.py` | Guardian |
| `/categories` | `expense.py` | Either |
| `/budgets` | `budget.py` | Guardian |
| `/balance` | `budget.py` | Guardian |
| `/report` | `report.py` | Guardian |
| `/dependents` | `dependent.py` | Guardian |
| `/pocketmoney` | `dependent.py` | Either (Dependent sees own balance) |
| `/savings` | `dependent.py` | Dependent |
| `/rollover` | `dependent.py` | Dependent |
| `/profile` | `account.py` | Either |
| `/settings` | `account.py` | Guardian |
| Unsupported text/command | `unknown.py` | Either |

## 11. Service Layer Responsibilities

- `TelegramService` (`telegram/services/telegram_service.py`): Identity
  resolution, delegates to domain services, formats Telegram-specific messages.
  Does NOT contain business logic.
- `ExpenseService`: Expense CRUD, voice orchestration (via AIService).
- `BudgetService`: Budget CRUD, refresh, overspend checks.
- `CategoryService`: Category CRUD, default creation.
- `DependentService`: Dependent CRUD, validation.
- `PocketMoneyService`: Allocation CRUD, balance, rollover.
- `ReportService`: Weekly/monthly summaries, message builders.
- `TelegramLinkService`: Link CRUD, token-based linking.

Each service uses Frappe's ORM and permission model, not raw SQL.
All service operations use `ignore_permissions=True` for system-triggered actions.

## 12. AI Integration

### Sarvam AI Speech-to-Text

`ai/speech_to_text.py` accepts a temporary file path and optional language
hint, reads `sarvam_api_key`, `sarvam_stt_model`, and timeout configuration,
and returns only a transcript. It retries network/timeouts/5xx twice with
exponential backoff (1s, then 3s), never retries 4xx responses, and raises
`SpeechToTextError` on final failure or empty transcription.

### OpenAI GPT Expense Parsing

`ai/ai_parser.py` receives a transcript and the owner's known categories. It
uses the configured OpenAI model (default `gpt-4o-mini`) to return normalized
expense data. It makes one retry for transient network/5xx failures. Malformed
JSON receives one stricter re-prompt, not an unbounded retry.

AI modules do not create records.

## 13. Expense Creation Workflow

For either manual or voice input, the canonical operation is
`ExpenseService.create_expense()`:

1. Resolve the linked Individual or Dependent owner.
2. Validate amount, date, category, and owner relationship.
3. For a Dependent, ensure the selected category belongs to their guardian.
4. Create one Expense with its documented source and optional AI audit fields.
5. Recompute relevant Budget or Pocket Money Allocation spending.
6. Evaluate the budget overspend threshold and enqueue/send a notification
   only when appropriate.
7. Return a summary object to the calling handler.

## 14. Budget Notification Workflow

An Expense create/update invokes `BudgetService.refresh_budget()` for its
category and owner. `BudgetService._check_overspend(budget)` compares computed
spend with the Budget's `alert_threshold_pct` (default 90 when not set).

Daily job `run_budget_alerts()` scans all active budgets, refreshes spent
amounts, and sends Telegram notifications to linked guardians when thresholds
are crossed. Alerts are idempotent: once per day per budget.

## 15. Background Job Architecture

The HTTP webhook has exactly one job responsibility: enqueue processing of a
validated, non-duplicate update. The worker executes `telegram.bot.process_update`
dispatch, including network-bound voice download, transcription, parsing,
persistence, and response delivery.

Scheduled work runs via Frappe scheduler (registered in `hooks.py`):
- `expense_manager.jobs.budget_alerts.run_budget_alerts` — daily
- `expense_manager.jobs.reminders.run_reminders` — daily
- `expense_manager.jobs.monthly_rollover.run_monthly_rollover` — daily

## 16. Retry Policy

| Boundary | Policy |
|---|---|
| Telegram delivery to webhook | Telegram retries when it does not receive a fast 200; webhook acknowledgement and `update_id` deduplication make this safe. |
| Sarvam transcription | Two retries with 1s/3s exponential backoff for network, timeout, and 5xx only. |
| OpenAI parse | One retry after 2s for network, timeout, and 5xx only; malformed JSON gets one stricter re-prompt. |
| Frappe background job | Use Frappe queue failure/retry configuration; always log an exhausted failure. |

No boundary retries 4xx failures.

## 17. Error Handling Strategy

Known exceptions cross layers in typed form: `SpeechToTextError`,
`ExpenseParseError`, `TelegramLinkRequiredError`, `BudgetNotFoundError`, and
the base `ExpenseManagerError` class. The handler maps them to documented friendly
messages. The bot dispatcher catches unexpected exceptions, logs a traceback,
and sends only the generic retry-later reply.

An unlinked user is directed to `/link`; an AI failure offers manual entry;
malformed or low-confidence parsing asks for clarification. No exception
message, token, provider response, or stack trace is sent to Telegram.

## 18. Logging Strategy

Use `frappe.logger("expense_manager")` for webhook, queue, AI, and transport
events. Each update lifecycle records `update_id`, resolvable Telegram ID,
update type/command, operation, outcome, reason/error type, and latency.

Logs must never contain bot/API tokens or raw audio. Full transcripts are
excluded from normal logs; debug-level transcript logging is permitted only
when `enable_debug_transcript_logging` is enabled.

## 19. Security Considerations

- Restrict the webhook to POST and verify Telegram's secret header on every
  guest request.
- Resolve every protected update through an active Telegram Link or Dependent identity.
- Enforce Individual/Dependent permissions through Frappe and service-layer checks.
- Treat callback payloads, command arguments, provider output, and downloaded
  files as untrusted input.
- Store files in a unique temporary location and delete them in all outcomes.
- Never hardcode, log, or commit secrets; use site configuration/environment.
- Ensure duplicate update handling and notification logic are idempotent.
- All DocType operations in service layer use `ignore_permissions=True` for
  system-triggered actions (webhook, jobs, bot commands).
- Guardian cross-checks verify dependent ownership before fetching allocations.

## 20. Configuration Management

Configuration getters are centralized in `telegram/config.py`. Required values
are `telegram_bot_token`, `telegram_webhook_secret`, `sarvam_api_key`, and
`openai_api_key`. All raise `frappe.ValidationError` if missing.

Supported optional values and defaults:

| Key | Default |
|---|---|
| `openai_model` | `gpt-4o-mini` |
| `sarvam_stt_model` | `saarika:v2` |
| `expense_parse_language_hint` | `unknown` |
| `otp_expiry_minutes` | `5` |
| `budget_alert_threshold_pct` | `90` |
| `ai_request_timeout_seconds` | `30` |
| `enable_debug_transcript_logging` | `0` |

## 21. Sequence Diagrams (Text-Based)

### Webhook and command processing

```text
Telegram → Webhook: POST update + secret header
Webhook → Webhook: verify secret, parse, log, deduplicate update_id
Webhook → Frappe Queue: enqueue validated update
Webhook → Telegram: HTTP 200 {ok: true}
Frappe Queue → Bot: dispatch update
Bot → Router: classify update
Router → Handler: invoke selected flow
Handler → TelegramService: resolve identity + call service
TelegramService → Domain Service: business logic
Domain Service → DocType: ORM operations
Handler → Telegram: send formatted reply
```

### Account linking

```text
User → Desk: POST /api/method/...generate_link_code
Desk API → Redis: store token with TTL
Desk API → User: {token, expires_at}
User → Telegram: /link <token>
Telegram → LinkHandler → TelegramService → TelegramLinkService
TelegramLinkService → Redis: fetch and validate token
TelegramLinkService → Telegram Link DocType: create active link
TelegramLinkService → User: "Account linked!"
```

### Voice expense

```text
User → Telegram: voice note
Telegram → Webhook → Queue → Router → VoiceHandler
VoiceHandler → TelegramService: create_expense_from_voice(telegram_user_id, file_path)
TelegramService → Identity: resolve Individual or Dependent
TelegramService → AIService: create_expense_from_audio(owner_user, file_path, dependent)
AIService → Sarvam: transcribe audio
Sarvam → AIService: transcript
AIService → OpenAI: parse transcript + known categories
OpenAI → AIService: structured expense JSON
AIService → ExpenseService: create_expense(...)
ExpenseService → Expense DocType: validate and create
TelegramService → BudgetService: refresh_budget()
TelegramService → PocketMoneyService: refresh_balance()
VoiceHandler → Telegram: "Logged ₹200 under Food"
VoiceHandler → Temp storage: delete file in finally
```

### Budget alert

```text
Daily Scheduler → BudgetAlerts: run_budget_alerts()
BudgetAlerts → Budget: get all active budgets
BudgetAlerts → BudgetService: refresh_budget() for each
BudgetService → Expense: recompute spent_amount
BudgetService → Budget: check overspend threshold
BudgetAlerts → TelegramLink: find active link for guardian
BudgetAlerts → Telegram: send alert message
```

## 22. Future Extensibility

The handler/service/API separation makes Telegram replaceable without changing
the financial domain. A future channel can translate its own messages into
the existing service/API contracts, while reports and permissions remain
Frappe-native.

Within the documented roadmap, later additions include production deployment
infrastructure. Multi-currency, non-Telegram bot channels, a mobile app,
and production/VPS concerns remain out of scope. Any new DocType, field,
command, or route must first be added to the authoritative documentation
and follow the phased workflow with mocked external-service tests and
Frappe integration tests.
