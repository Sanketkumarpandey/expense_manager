# Architecture

## 1. High-Level Layers

```
Telegram
   ↓
Webhook (Frappe whitelisted method)
   ↓
bot.py (entry point / update dispatcher)
   ↓
Router  (telegram/handlers/router.py)
   ↓
Handler (telegram/handlers/*.py)   — parses the update, calls a Service, replies
   ↓
Service (services/*.py)            — business logic, talks to DocTypes
   ↓
AI layer (ai/*.py)                 — Sarvam AI (speech→text), OpenAI GPT (text→JSON)
   ↓
API layer (api/*.py)               — whitelisted Frappe methods, reusable outside Telegram
   ↓
DocType (doctype/*)                — Expense, Budget, Dependent, Category, ...
   ↓
MariaDB
```

**Rule: a Handler never touches the database directly.** It only calls a
Service. This keeps Telegram fully swappable — the same Services could be
called from a web UI, a mobile app, or WhatsApp later without change.

## 2. Module Responsibilities

| Module | Responsibility | Must NOT do |
|---|---|---|
| `telegram/bot.py` | Receives raw Telegram `Update` JSON, hands to router | Business logic, DB access |
| `telegram/handlers/` | One file per command/flow (`start.py`, `link.py`, `voice.py`, `report.py`) | DB access, AI calls |
| `telegram/middleware/` | Cross-cutting concerns: auth/linking check, rate limiting, logging | Business logic |
| `telegram/services/` (bot-local) | Formats Telegram-specific replies (keyboards, message templates) | Core business rules |
| `services/` (app-level) | `expense_service.py`, `budget_service.py`, `dependent_service.py`, `report_service.py` | Talking to Telegram directly |
| `ai/speech_to_text.py` | Calls Sarvam AI, returns plain text | Business logic, expense parsing |
| `ai/ai_parser.py` | Calls OpenAI GPT, returns structured Expense JSON | DB writes |
| `api/` | Whitelisted `@frappe.whitelist()` methods for REST access (used by Telegram services and, later, a web/mobile client) | Direct Telegram formatting |
| `doctype/` | Data model + field-level validation (`validate`, `before_save` hooks) | AI calls, Telegram calls |

## 3. Voice-Note Flow (Sarvam AI → GPT → Expense)

```
1. User sends Telegram voice note
2. Webhook receives Update → bot.py → router → handlers/voice.py
3. handlers/voice.py:
     - downloads the .ogg file via Telegram File API
     - saves to a temp path
     - calls services/expense_service.create_from_voice(file_path, telegram_id)
4. expense_service.create_from_voice():
     a. calls ai/speech_to_text.transcribe(file_path)      → Sarvam AI → text
     b. calls ai/ai_parser.parse_expense(text)             → OpenAI GPT → JSON
     c. resolves telegram_id → linked User/Dependent
     d. calls api.expense.create_expense(**json, user=...)  → Expense DocType
     e. deletes temp audio file
     f. returns a summary object
5. handlers/voice.py formats the summary and replies in Telegram
```

Full detail: `docs/ai.md`, `docs/prompts.md`, `docs/webhook.md`.

## 4. Design Principles

1. **Telegram is just an interface.** No `TelegramExpense` DocType — there is
   one `Expense` DocType regardless of how it was created (`source` field
   records `web` vs `telegram`).
2. **AI output is never trusted blindly.** `ai_parser.py` returns JSON that is
   validated (types, required keys, category must exist) before being handed
   to `expense_service`. Low-confidence or malformed output triggers a
   clarifying reply instead of a bad Expense record.
3. **Idempotency.** Each Telegram `update_id` is logged; duplicate webhook
   deliveries (Telegram retries on timeout) are detected and ignored.
4. **Everything reuses Frappe's permission system.** A Dependent's Telegram
   account is linked to a restricted Frappe User with role `Dependent`, so
   the same `frappe.has_permission` checks apply whether the request comes
   from Telegram or the desk.
5. **Reports are computed once.** `report_service.py` wraps the existing
   Frappe Query Reports; the Telegram `/report` handler renders the same
   data as a chart image instead of duplicating query logic.

## 5. Sequence Diagram — Voice Expense Logging

```
User        Telegram        Webhook        Router      VoiceHandler   ExpenseService   SarvamAI   OpenAI   Expense(DocType)
 |  voice      |               |              |             |              |              |          |            |
 |------------>|               |              |             |              |              |          |            |
 |             | POST update   |              |             |              |              |          |            |
 |             |-------------->|              |             |              |              |          |            |
 |             |               | dispatch()   |             |              |              |          |            |
 |             |               |------------->|             |              |              |          |            |
 |             |               |              | route(voice)|              |              |          |            |
 |             |               |              |------------>|              |              |          |            |
 |             |               |              |             | download file|              |          |            |
 |             |               |              |             |------------->|              |          |            |
 |             |               |              |             |              | transcribe() |          |            |
 |             |               |              |             |              |------------->|          |            |
 |             |               |              |             |              |   text       |          |            |
 |             |               |              |             |              |<-------------|          |            |
 |             |               |              |             |              | parse()      |          |            |
 |             |               |              |             |              |------------------------->|            |
 |             |               |              |             |              |   JSON                   |            |
 |             |               |              |             |              |<-------------------------|            |
 |             |               |              |             |              | create_expense()          |            |
 |             |               |              |             |              |-------------------------------------->|
 |             |               |              |             |              |          Expense saved                |
 |             |               |              |             |<-------------|                                       |
 |  reply      |<--------------------------------------------|                                                      |
 |<------------|               |              |             |                                                      |
```

## 6. Non-Goals (for now)

- Multi-currency support
- Multi-language GPT parsing beyond what Sarvam AI transcribes (English +
  Hindi initially — confirm with `docs/environment.md` language config)
- A standalone mobile app (web/desk UI via Frappe is sufficient for now)
