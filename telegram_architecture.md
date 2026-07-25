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
  → handler → app service → API/DocType/Report
                         ↘ AI adapters (voice only)
  → Telegram API client → Telegram user
```

The webhook is the only public bot ingress. The system uses Telegram's
`update_id` for idempotency and a Telegram Link record to map a Telegram
identity to an Individual or Dependent before allowing protected operations.

## 2. Complete Folder Structure

The following is the intended application structure. It is an architecture
target; these modules do not exist in the current scaffold.

```text
expense_manager/
├── api/
│   ├── expense.py                 # Whitelisted expense operations
│   ├── budget.py                  # Whitelisted budget operations
│   ├── dependent.py               # Whitelisted dependent/pocket-money operations
│   ├── report.py                  # Summary data and PNG-chart operations
│   └── telegram_link.py           # OTP and link lifecycle operations
├── ai/
│   ├── __init__.py
│   ├── exceptions.py              # SpeechToTextError, ExpenseParseError
│   ├── speech_to_text.py          # Sarvam audio-to-text adapter only
│   └── ai_parser.py               # OpenAI text-to-expense JSON adapter only
├── services/
│   ├── exceptions.py              # Domain-facing service exceptions
│   ├── expense_service.py         # Expense creation and voice orchestration
│   ├── budget_service.py          # Budget status and overspend checks
│   ├── dependent_service.py       # Dependent and pocket-money operations
│   └── report_service.py          # Weekly/monthly summary orchestration
├── telegram/
│   ├── __init__.py
│   ├── config.py                  # Telegram/AI configuration getters
│   ├── webhook.py                 # Guest POST ingress, validation, enqueue
│   ├── bot.py                     # Background update dispatcher and top-level error boundary
│   ├── router.py                  # Update type/command to handler mapping
│   ├── handlers/
│   │   ├── start.py
│   │   ├── help.py
│   │   ├── link.py                # /link, /unlink, unlink callback confirmation
│   │   ├── voice.py               # Voice update and clarification callback flow
│   │   ├── report.py
│   │   ├── budget.py
│   │   ├── pocket_money.py
│   │   └── unknown.py
│   ├── middleware/
│   │   ├── auth.py                # Telegram Link resolution and persona checks
│   │   ├── rate_limit.py          # Per-Telegram-ID throttling
│   │   └── logging.py             # Update lifecycle logging/deduplication helpers
│   ├── services/
│   │   └── message_templates.py   # Telegram-specific text and keyboards
│   └── utils/
│       ├── telegram_api.py        # getFile, file download, sendMessage, sendPhoto wrapper
│       └── file_download.py       # Temporary voice-file lifecycle
├── doctype/                       # Planned Frappe DocType schemas/controllers
├── report/                        # Planned Frappe Query Reports
└── tests/
    ├── test_telegram/
    ├── test_ai/
    ├── test_services/
    └── fixtures/
```

`telegram/services/` is intentionally limited to Telegram presentation
concerns. It must not duplicate the app-level business services in
`services/`.

## 3. Component Responsibilities

| Component | Responsibility | Explicitly excluded |
|---|---|---|
| `telegram/webhook.py` | Verify a Telegram delivery, deduplicate it, enqueue it, return quickly. | Routing, AI work, expense writes, reply formatting. |
| `telegram/bot.py` | Dispatch one queued update and provide the final exception boundary. | Domain rules and direct persistence. |
| `telegram/router.py` | Select a handler based on command, voice, callback, or fallback. | Database access and AI calls. |
| Handlers | Parse Telegram input, require identity where appropriate, call one service path, send a formatted response. | Direct DocType/DB access and AI calls. |
| Middleware | Authentication/link resolution, rate limit, and operational update logging. | Business mutations. |
| `telegram/utils/telegram_api.py` | Narrow authenticated Bot API transport. | Domain decisions and authorization. |
| App services | Business workflows, ORM/DocType interaction, permission-aware validation, and AI orchestration where documented. | Telegram message layout and raw update parsing. |
| API modules | Whitelisted reusable boundary over services. | Telegram-specific presentation. |
| AI adapters | Provider calls and normalization only. | Database writes and expense-policy decisions. |
| DocTypes/Reports | Schema validation, Frappe permissions, and report data. | Telegram and external AI transport. |

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
4. It records operational metadata and checks `update_id` idempotency before
   enqueueing. A Redis-backed set with TTL is suitable because it avoids
   inventing an additional DocType; duplicate updates return `{"ok": true}`
   without another job.
5. A unique update is passed to `frappe.enqueue` for background dispatch.
6. The endpoint returns `{"ok": true}` immediately. It never transcribes
   audio, calls OpenAI, creates an Expense, or sends a reply inline.

This separation keeps webhook latency below Telegram's retry threshold and
prevents duplicate processing when Telegram re-delivers an update.

## 5. Outgoing Telegram API Flow

Handlers and system-triggered services use a single transport wrapper rather
than issuing Bot API requests directly. The wrapper reads the bot token from
configuration and exposes only the documented transport operations:

- `sendMessage` for command confirmations, prompts, and errors;
- `sendPhoto` for weekly/monthly report PNGs;
- `getFile` and the authenticated file-download URL for voice notes.

The caller supplies a chat target and presentation payload created by
`message_templates.py`. The wrapper retries only transient network/5xx
failures, logs outcome and latency without tokens or sensitive content, and
returns/raises a transport failure for the top-level error strategy. It does
not decide whether a user is authorized or whether an expense is valid.

## 6. Authentication Strategy

There are two distinct controls:

1. **Webhook authenticity:** Telegram's secret-token header protects the
   guest ingress endpoint. It is mandatory for every delivery.
2. **User authorization:** `from.id`/`chat.id` is resolved through an active
   Telegram Link. The link identifies an Individual Frappe User or a
   Dependent and drives the same Frappe permission checks used outside
   Telegram.

Unlinked users may use `/start`, `/help`, and `/link`; protected commands,
voice processing, reports, budgets, and pocket-money access require a valid
link. Persona checks occur after link resolution: only Individuals may manage
budgets and request the documented household report view, while
`/pocketmoney` is limited to Dependents.

## 7. Telegram Account Linking Lifecycle

```text
Unlinked Telegram ID
  └─ /link → short-lived OTP issued
              └─ authenticated Desk/linking action verifies OTP
                   └─ active Telegram Link to Individual or Dependent
                        └─ protected Telegram operations allowed
                             └─ /unlink confirmation → link marked inactive
                                  └─ Unlinked Telegram ID
```

An active Telegram ID may map to only one Individual or Dependent. A Telegram
ID already linked elsewhere must be unlinked before a new link can be created.
The Telegram Link DocType retains the documented OTP, expiry, active state,
linked type/name, and linking timestamp; OTP data is transient and cleared
after successful verification.

## 8. OTP Verification Flow

1. `/link` is routed to `handlers/link.py` without requiring an existing
   Telegram Link.
2. The handler calls the planned `api.telegram_link.generate_otp(telegram_id)`
   operation and sends the resulting six-digit code with its configured
   expiry (five minutes by default).
3. The user enters the code in the authenticated Frappe Desk/linking flow.
   An Individual may link their own User or select their Dependent as
   documented.
4. `api.telegram_link.verify_otp(otp, user_or_dependent)` validates that the
   OTP exists, is unused, is unexpired, and is not associated with a Telegram
   ID already actively linked to a different identity.
5. Verification creates/activates the Telegram Link, records its linked
   persona, and clears/marks the OTP used.
6. The next Telegram interaction resolves as linked; no unsolicited
   confirmation mechanism is required.

Expired or already-used codes produce the documented request to run `/link`
again. `/unlink` first asks for an inline Yes/No confirmation, then invokes
the documented unlink API and marks the link inactive.

## 9. Voice Processing Pipeline

1. The router recognizes `message.voice`; authentication and rate limiting
   happen before any billable processing.
2. `handlers/voice.py` asks the Telegram transport for the `file_id`, stores
   the `.ogg`/OPUS file in a unique temporary path, and delegates to
   `services.expense_service.create_from_voice` with the resolved owner.
3. The expense service calls `ai.speech_to_text.transcribe` to produce plain
   text, then retrieves the owner's valid category names.
4. It calls `ai.ai_parser.parse_expense(transcript, known_categories)` and
   validates the returned schema before any persistence.
5. A valid parse is passed through normal expense creation so DocType
   validation, category ownership, permissions, budget computation, and
   notification checks remain canonical.
6. The handler sends a concise confirmation. Missing amount/low confidence
   triggers the documented category clarification instead of an unsafe write;
   AI failures direct the user to `/addexpense`.
7. Temporary audio is deleted in a `finally` path regardless of outcome.

The implementation must confirm Sarvam's current acceptance of `.ogg` before
using it directly; if it is unsupported, conversion belongs in
`telegram/utils/file_download.py`, not in an AI or handler module.

## 10. Command Routing Architecture

The router performs deterministic classification in this order: callback
query associated with an existing interaction, voice note, recognized command,
then unknown input. It extracts the command and arguments, but does not
interpret business meaning or access the database.

| Input | Handler | Required persona |
|---|---|---|
| `/start` | `start.py` | Either; link state changes wording. |
| `/help` | `help.py` | Either; response is persona-aware when linked. |
| `/link`, `/unlink` | `link.py` | `/link` unlinked/linked; `/unlink` linked. |
| Voice message | `voice.py` | Linked Individual or Dependent. |
| `/addexpense ...` | Expense command path | Linked Individual or Dependent. |
| `/report weekly|monthly` | `report.py` | Individual for documented household report flow. |
| `/budget`, `/budget set ...` | `budget.py` | Individual. |
| `/pocketmoney` | `pocket_money.py` | Dependent. |
| Unsupported text/command | `unknown.py` | Either. |

Inline confirmation and category-selection callbacks return to the owning
link/voice handler. Their payload must be treated as input, with the linked
identity and pending workflow revalidated before a mutation.

## 11. Handler Responsibilities

Each handler has a narrow interaction responsibility:

- `start.py` and `help.py` choose the documented greeting/help text based on
  link state and persona.
- `link.py` starts OTP linking, renders unlink confirmation, and handles its
  confirmed cancellation/removal action.
- `voice.py` coordinates authenticated download delegation, renders success
  or clarification keyboards, and maps recognized errors to friendly text.
- The manual expense command parses its documented positional arguments and
  invokes normal expense service creation; it never duplicates AI or DocType
  validation.
- `report.py`, `budget.py`, and `pocket_money.py` enforce their persona gate,
  call their respective service/API operation, and render the result.
- `unknown.py` returns the fallback help hint.

Handlers do not call `frappe.db`, `frappe.get_doc`, the AI providers, or raw
Telegram HTTP endpoints. They must not expose provider errors, tracebacks, or
authorization internals to a user.

## 12. Service Layer Responsibilities

`expense_service` owns normal expense creation and the voice orchestration
path. It translates validated AI output to the documented Expense fields,
including `source="telegram"`, transcript, and confidence where applicable,
then relies on the Expense DocType's validation.

`budget_service` calculates/returns budget status and checks whether an
Expense update crosses the configured Budget threshold. `dependent_service`
owns dependent creation, monthly allocation, balance, and explicit rollover
rules. `report_service` obtains weekly/monthly category summaries and
chart-ready data without duplicating report logic. Each service uses Frappe's
ORM and permission model, not raw SQL.

## 13. AI Integration

### Sarvam AI Speech-to-Text

`ai/speech_to_text.py` accepts a temporary file path and optional language
hint, reads `sarvam_api_key`, `sarvam_stt_model`, and timeout configuration,
and returns only a transcript. It retries network/timeouts/5xx twice with
exponential backoff (1s, then 3s), never retries 4xx responses, and raises
`SpeechToTextError` on final failure or empty transcription. It logs metadata
such as size, duration, status, and latency—never raw audio.

### OpenAI GPT Expense Parsing

`ai/ai_parser.py` receives a transcript and the owner's known categories. It
uses the versioned prompt/schema in `docs/prompts.md`, JSON mode, and the
configured OpenAI model (default `gpt-4o-mini`) to return normalized expense
data only. It makes one retry for transient network/5xx failures. Malformed
JSON receives one stricter re-prompt, not an unbounded retry.

Before return, the adapter enforces exact expected keys, positive-or-null
amount, category membership or `uncategorized`, a non-future ISO date (falling
back to today), and confidence bounds. Invalid structure raises
`ExpenseParseError`; missing amount/low confidence is a clarification outcome,
not an Expense write. AI modules do not create records.

## 14. Expense Creation Workflow

For either manual or voice input, the canonical operation is the documented
`api.expense.create_expense(...)` / expense-service path:

1. Resolve the linked Individual or Dependent owner.
2. Validate amount, date, category, and owner relationship.
3. For a Dependent, ensure the selected category belongs to their guardian.
4. Create one Expense with its documented owner type, source, and optional
   AI audit fields.
5. Recompute relevant Budget or Pocket Money Allocation spending through the
   designed domain logic.
6. Evaluate the budget overspend threshold and enqueue/send a notification
   only when appropriate.
7. Return a summary object to the calling handler, which formats the Telegram
   confirmation.

The Telegram flow must reuse this path; it must not write an Expense directly
from the handler or treat AI output as trusted persistence input.

## 15. Budget Notification Workflow

An Expense create/update invokes the documented budget check for its category
and month. `budget_service.check_overspend` compares computed spend with the
Budget's `alert_threshold_pct` (default 90 when not set per record). On a
threshold crossing, it sends a Telegram notification to the Individual and,
only if configured by the documented policy, the Dependent who caused it.

The notification is system-triggered and uses the active Telegram Link plus
the outbound transport wrapper. It does not run in the webhook request. The
service must preserve idempotency so an update retry or repeated expense save
does not create repeated threshold alerts.

## 16. Weekly and Monthly Report Workflow

1. `report.py` resolves the linked owner and accepts only `weekly` or
   `monthly` arguments.
2. For the documented Individual flow, the report service obtains the
   Individual and Dependents' summaries; a Dependent is limited to their own
   data where that access is supported by the underlying permission model.
3. The service delegates to the planned weekly/monthly report/API functions
   for totals by category and chart-ready data rather than repeating queries.
4. `api.report.generate_chart_png(dataset)` renders the PNG.
5. The handler sends the PNG via `sendPhoto` and a compact totals summary via
   the Telegram transport.

Reports have no separate Telegram data store; their source is the same
Expense records and Frappe Query Report/ORM data as the Desk view.

## 17. Background Job Architecture

The HTTP webhook has exactly one job responsibility: enqueue processing of a
validated, non-duplicate update. The worker executes `telegram.bot` dispatch,
including network-bound voice download, transcription, parsing, persistence,
and response delivery. This avoids holding the public request open for AI
latency.

Scheduled work is separate from webhook jobs. The current design anticipates
the Frappe scheduler for month-end pocket-money rollover and any later
scheduled budget checks. No scheduler event is currently registered. Failed
jobs are recorded by Frappe's queue and logged; the user receives the relevant
friendly response when a reply can be sent.

## 18. Retry Policy

| Boundary | Policy |
|---|---|
| Telegram delivery to webhook | Telegram retries when it does not receive a fast 200; webhook acknowledgement and `update_id` deduplication make this safe. |
| Sarvam transcription | Two retries with 1s/3s exponential backoff for network, timeout, and 5xx only. |
| OpenAI parse | One retry after 2s for network, timeout, and 5xx only; malformed JSON gets one stricter re-prompt. |
| Telegram outbound message/photo | Two retries with a fixed one-second delay for network and 5xx only. |
| Frappe background job | Use Frappe queue failure/retry configuration; always log an exhausted failure. |

No boundary retries 4xx failures. Retry counts are bounded to prevent excess
cost and duplicate side effects; mutations remain protected by normal record
validation and webhook idempotency.

## 19. Error Handling Strategy

Known exceptions cross layers in typed form: `SpeechToTextError`,
`ExpenseParseError`, `TelegramLinkRequiredError`, `BudgetNotFoundError`, and
Frappe validation errors. The handler maps them to documented friendly
messages. The bot dispatcher catches unexpected exceptions, logs a traceback,
and sends only the generic retry-later reply.

An unlinked user is directed to `/link`; an AI failure offers the manual
`/addexpense <amount> <category>` path; malformed or low-confidence parsing
asks for clarification. No exception message, token, provider response, or
stack trace is sent to Telegram.

## 20. Logging Strategy

Use `frappe.logger("expense_manager")` for webhook, queue, AI, and transport
events. Each update lifecycle records `update_id`, resolvable Telegram ID,
update type/command, operation, outcome, reason/error type, and latency.

Logs must never contain bot/API tokens or raw audio. Full transcripts are
excluded from normal logs; debug-level transcript logging is permitted only
when `enable_debug_transcript_logging` is enabled. Error-level entries retain
tracebacks for unexpected failures. This supports diagnostics while minimizing
retention of personal spending data.

## 21. Security Considerations

- Restrict the webhook to POST and verify Telegram's secret header on every
  guest request.
- Resolve every protected update through an active Telegram Link; do not use a
  numeric Telegram ID as authorization by itself.
- Enforce Individual/Dependent permissions through Frappe and DocType logic,
  including guardian-owned category validation for Dependent expenses.
- Rate-limit per Telegram ID before AI or file work to control abuse and cost.
- Treat callback payloads, command arguments, provider output, and downloaded
  files as untrusted input.
- Store files in a unique temporary location, apply the documented size sanity
  check, and delete them in all outcomes.
- Never hardcode, log, or commit secrets; use site configuration/environment.
- Ensure duplicate update handling and notification logic are idempotent.

## 22. Configuration Management

Configuration getters centralize access to environment variables first and
`frappe.conf` second. Required values are `telegram_bot_token`,
`telegram_webhook_secret`, `sarvam_api_key`, and `openai_api_key`.

Supported optional values and defaults are:

| Key | Default |
|---|---|
| `openai_model` | `gpt-4o-mini` |
| `sarvam_stt_model` | `saarika:v2` (confirm provider support when implemented) |
| `expense_parse_language_hint` | `unknown` |
| `otp_expiry_minutes` | `5` |
| `budget_alert_threshold_pct` | `90` |
| `ai_request_timeout_seconds` | `30` |
| `enable_debug_transcript_logging` | `0` |
| `use_mock_ai_apis` | Test/development flag |

Webhook registration is an explicit setup/configuration action using
Telegram's `setWebhook`; it must not run at each application start.

## 23. Sequence Diagrams (Text-Based)

### Webhook and command processing

```text
Telegram → Webhook: POST update + secret header
Webhook → Webhook: verify secret, parse, log, deduplicate update_id
Webhook → Frappe Queue: enqueue validated update
Webhook → Telegram: HTTP 200 {ok: true}
Frappe Queue → Bot: dispatch update
Bot → Router: classify update
Router → Handler: invoke selected flow
Handler → Telegram API: send formatted reply
Telegram API → User: deliver reply
```

### Account linking

```text
User → Telegram: /link
Telegram → LinkHandler: queued command
LinkHandler → Telegram Link API: generate_otp(telegram_id)
LinkHandler → User: code and expiry instructions
User → Authenticated Desk/link page: submit OTP and target identity
Desk/link page → Telegram Link API: verify_otp(otp, user_or_dependent)
Telegram Link API → Telegram Link: activate link, clear/consume OTP
User → Telegram: next protected request
Auth middleware → Telegram Link: resolve active linked identity
```

### Voice expense

```text
User → Telegram: voice note
Telegram → Webhook → Queue → Router → VoiceHandler
VoiceHandler → Auth/RateLimit: resolve linked owner and permit work
VoiceHandler → Telegram API: getFile/download
VoiceHandler → ExpenseService: create_from_voice(temp_file, owner)
ExpenseService → Sarvam: transcribe audio
Sarvam → ExpenseService: transcript
ExpenseService → OpenAI: parse transcript + known categories
OpenAI → ExpenseService: structured expense JSON
ExpenseService → Expense DocType: validate and create canonical Expense
ExpenseService → BudgetService: recompute/check threshold
VoiceHandler → Telegram API: confirmation or clarification
VoiceHandler → Temp storage: delete file in finally
```

### Budget alert

```text
Expense DocType/service → BudgetService: expense created or updated
BudgetService → Budget: compute spent amount and compare threshold
BudgetService → Telegram Link: find active recipient link
BudgetService → Telegram API: send threshold notification
Telegram API → Individual (and configured Dependent): notification
```

## 24. Future Extensibility

The handler/service/API separation makes Telegram replaceable without changing
the financial domain. A future channel can translate its own messages into
the existing service/API contracts, while reports and permissions remain
Frappe-native.

Within the documented roadmap, later additions are pocket-money rollover
wiring, the Dependent `/pocketmoney` flow, and production deployment
infrastructure. Multi-currency, non-Telegram bot channels, a mobile app, and
production/VPS concerns remain out of scope. Any new DocType, field, command,
or route must first be added to the authoritative documentation and follow
the phased workflow with mocked external-service tests and Frappe integration
tests.
