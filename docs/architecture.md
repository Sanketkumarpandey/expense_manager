# Architecture

## 1. High-Level Layers

```
Telegram user
  → Telegram Bot API
  → Frappe webhook (allow_guest, POST-only)
  → update validation, deduplication, enqueue
  → background bot dispatcher (bot.py)
  → Router (router.py)
  → Handler (telegram/handlers/*.py)
  → TelegramService (telegram/services/telegram_service.py)
  → Business Service (services/*.py)
  → DocType (doctype/*) → MariaDB
       ↘ AI adapters (ai/*.py) — voice only
       ↘ Scheduled jobs (jobs/*.py) — daily background jobs
```

**Rule: a Handler never touches the database directly.** It calls
`TelegramService`, which resolves identity and delegates to a business
service. The same services can be called from the REST API (`api/*.py`)
without change.

## 2. Module Responsibilities

| Module | Responsibility | Must NOT do |
|---|---|---|
| `telegram/webhook.py` | Verify secret token, deduplicate `update_id`, enqueue, return 200 | Business logic, DB access |
| `telegram/bot.py` | Dispatch one queued update, send text reply | Domain rules, direct persistence |
| `telegram/router.py` | Classify update type → select handler | Database access, AI calls |
| `telegram/handlers/*` | Parse Telegram input, call TelegramService, format reply string | Direct DB/AI access |
| `telegram/services/telegram_service.py` | Resolve Telegram identity, enforce persona, delegate to business services, return structured result | Direct DB persistence |
| `services/*.py` | Business logic, ORM operations, validation | Talking to Telegram directly |
| `ai/speech_to_text.py` | Sarvam AI: audio → text | Business logic, expense parsing |
| `ai/ai_parser.py` | Groq LLM: text → structured Expense JSON | DB writes |
| `api/*.py` | Whitelisted `@frappe.whitelist()` methods, scoped to `frappe.session.user` | Direct Telegram formatting |
| `jobs/*.py` | Scheduled background jobs (daily), orchestrate look-up and dispatch | Business rule reimplementation |
| `doctype/*` | DocType schema, field-level validation | AI calls, Telegram calls |
| `report/*` | Frappe Query Reports for Desk | Business logic |

## 3. Service Layer

All business logic lives in `services/`. Every service is a static-method
class. Every public method takes `owner_user` or `guardian` as its first
parameter and validates ownership before any database operation.

| Service | Responsibility |
|---|---|
| `CategoryService` | CRUD, uniqueness per owner, archive/restore, default creation |
| `DependentService` | CRUD, relationship validation, allowance validation, telegram ID lookup |
| `ExpenseService` | CRUD, amount/date/source validation, budget & pocket money refresh |
| `BudgetService` | CRUD, overspend detection, threshold alerts, period validation |
| `PocketMoneyService` | Allocation CRUD, balance computation, period rollover, low-balance messages |
| `ReportService` | Read-only summaries, breakdowns, trends, message builders for reminders |
| `TelegramLinkService` | Account linking lifecycle (token, verify, unlink), identity resolution |
| `AIService` | Voice → expense orchestration (transcribe → parse → create) |

## 4. Voice-Note Flow

```
1. User sends Telegram voice note
2. Webhook → bot.py → router → handlers/voice.py
3. handlers/voice.py:
     - resolves telegram_user_id
     - downloads .ogg via Telegram File API
     - calls TelegramService.create_expense_from_voice(telegram_user_id, file_path)
     - deletes temp file in finally block
4. TelegramService:
     - resolves identity (TelegramLink or Dependent via telegram_user_id)
     - calls AIService.create_expense_from_audio(owner_user, file_path, dependent)
5. AIService:
     - calls ai/speech_to_text.transcribe(file_path) → Sarvam AI → text
     - calls ai/ai_parser.parse_expense(transcript, known_categories) → Groq → JSON
     - resolves category (match or create "Uncategorized" fallback)
     - calls ExpenseService.create_expense(...) → Expense DocType
     - returns expense + message
6. ExpenseService.create_expense():
     - validates amount, date, category, source
     - creates Expense via frappe.get_doc + insert (ignore_permissions=True)
     - calls BudgetService.refresh_budget(owner_user, category)
     - calls PocketMoneyService.refresh_balance(owner_user, dependent)
7. TelegramService returns formatted message to handler
8. Handler returns string → bot.py → send_message(chat_id, text)
```

## 5. Design Principles

1. **Telegram is just an interface.** One `Expense` DocType regardless of
   source. `source` field records `Manual` vs `Telegram`.
2. **AI output is never trusted blindly.** Parsed JSON is validated (types,
   required keys, category membership) before any write.
3. **Idempotency.** Each Telegram `update_id` is cached in Redis with 24h
   TTL; duplicate deliveries are rejected before enqueueing.
4. **Service-layer ownership.** Every service method takes the acting user
   as its first argument and validates ownership. `frappe.get_doc` uses
   `ignore_permissions=True` because Frappe's role-based permissions are
   admin-only; business-level scoping is in the service layer.
5. **Fat service, thin everything else.** Handlers format replies. API
   methods are thin wrappers. Services contain all business rules.
6. **Typed exceptions.** `services/exceptions.py` defines a full exception
   hierarchy. No raw exceptions leak to Telegram replies.

## 6. Sequence Diagram — Voice Expense

```
User        Telegram        Webhook        Router      VoiceHandler   TelegramService  AIService   SarvamAI   Groq     ExpenseService
 |  voice      |               |              |             |              |              |          |          |            |
 |------------>|               |              |             |              |              |          |          |            |
 |             | POST update   |              |             |              |              |          |          |            |
 |             |-------------->|              |             |              |              |          |          |            |
 |             |               | enqueue()    |             |              |              |          |          |            |
 |             |               |------------->|             |              |              |          |          |            |
 |             |               |              | route(voice)|              |              |          |          |            |
 |             |               |              |------------>|              |              |          |          |            |
 |             |               |              |             | create_from_voice()         |          |          |            |
 |             |               |              |             |------------->|              |          |          |            |
 |             |               |              |             |              | create_from_audio()       |          |          |
 |             |               |              |             |              |------------->|          |          |            |
 |             |               |              |             |              |              | transcribe()         |          |
 |             |               |              |             |              |              |--------->|          |          |
 |             |               |              |             |              |              |   text   |          |          |
 |             |               |              |             |              |              |<---------|          |          |
 |             |               |              |             |              |              | parse()  |          |          |
 |             |               |              |             |              |              |-------------------->|          |
 |             |               |              |             |              |              |  JSON    |          |          |
 |             |               |              |             |              |              |<--------------------|          |
 |             |               |              |             |              | create_expense()          |          |          |
 |             |               |              |             |              |------------------------------------------>|
 |             |               |              |             |              |              |          |          | Expense saved
 |             |               |              |             |<-------------|              |          |          |            |
 |  reply      |<--------------------------------------------|              |              |          |          |            |
 |<------------|               |              |             |              |              |          |          |            |
```

## 7. Non-Goals (for now)

- Multi-currency support
- Multi-language beyond what Sarvam AI transcribes
- Standalone mobile app
- Production/VPS deployment (local bench only)
