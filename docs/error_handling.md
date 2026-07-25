# Error Handling, Logging & Recovery

## Guiding Principle

No raw exception, stack trace, or API error string ever reaches a Telegram
reply. Every known failure mode maps to a specific, friendly message, and
every failure is logged with enough context to debug it later.

## Exception Types (define in `ai/exceptions.py`, `services/exceptions.py`)

```python
class SpeechToTextError(Exception): ...
class ExpenseParseError(Exception): ...
class TelegramLinkRequiredError(Exception): ...
class BudgetNotFoundError(Exception): ...
```

Handlers catch these specifically; anything else is caught by a generic
top-level handler in `telegram/bot.py` that logs the full traceback and
replies with a generic "something went wrong, please try again" message —
never surfaced details.

## Retry Policy (summary — full detail in `docs/webhook.md` and `docs/ai.md`)

| Call | Retries | Backoff | Retry on |
|---|---|---|---|
| Sarvam AI transcribe | 2 | exponential (1s, 3s) | network error, 5xx, timeout |
| OpenAI GPT parse | 1 | fixed 2s | network error, 5xx, timeout |
| OpenAI malformed JSON | 1 re-prompt (not a raw retry) | n/a | schema validation failure |
| Telegram sendMessage | 2 | fixed 1s | network error, 5xx |
| Webhook → background job | handled by Frappe's queue retry config | n/a | job exceptions |

Never retry on 4xx errors (bad input) — those indicate a code/data problem,
not a transient failure, and retrying wastes API cost.

## User-Facing Message Mapping

| Internal error | Telegram reply |
|---|---|
| `SpeechToTextError` (Sarvam AI failed) | "Couldn't understand that voice note — try again, or type `/addexpense <amount> <category>`." |
| `ExpenseParseError` (bad GPT output) | "I heard you, but couldn't tell the amount/category — could you clarify? e.g. '200 for food'" |
| `TelegramLinkRequiredError` | "You'll need to link your account first — send /link." |
| `BudgetNotFoundError` | "No budget set for that category yet. Use /budget set <category> <amount>." |
| Unknown/unexpected exception | "Something went wrong on my end — please try again in a moment." |

## Logging Standards

- Use `frappe.logger("expense_manager")` everywhere outside request/response
  cycles (webhooks, background jobs, AI calls).
- Log at minimum: timestamp (automatic), `telegram_id` (if resolvable),
  operation name, outcome, latency, and — on failure — the exception type
  and message (not necessarily the full stack trace at info level; full
  traceback at error level).
- Never log: API keys/tokens, raw voice audio, full transcript at
  info-level (transcript only at debug level, gated by
  `enable_debug_transcript_logging` — see `docs/environment.md`, since
  transcripts can contain personal spending details).

## Recovery / Idempotency

- Telegram webhook retries are absorbed via `update_id` deduplication (see
  `docs/webhook.md`) — a retried webhook call never creates a duplicate
  Expense.
- Background job failures (e.g. Sarvam AI down mid-processing) do not
  silently vanish — Frappe's job queue records the failure, and the user
  still gets a reply (the friendly failure message above) rather than
  waiting indefinitely.
- If both Sarvam AI and OpenAI are unavailable, the system remains usable
  via the `/addexpense` manual text command (see `docs/telegram_commands.md`)
  — voice logging is an enhancement, not the only path.

## Alerting (for the developer, not the end user)

For local/dev phase: failures are visible via `bench` logs and the Frappe
Error Log doctype (`frappe.log_error`). No external alerting (PagerDuty,
etc.) is in scope until a production deployment phase exists — see
`docs/deployment.md`.
