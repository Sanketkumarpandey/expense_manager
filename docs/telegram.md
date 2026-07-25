# Telegram Bot Design

## Why Webhook, Not Polling

Polling repeatedly asks Telegram "any new messages?" — wasteful and slow.
A webhook lets Telegram push updates the instant they happen:

```
User → Telegram servers → HTTPS POST → our webhook endpoint → bot.py
```

Endpoint (Frappe whitelisted method, no CSRF, method=POST):

```
https://<site>/api/method/expense_manager.telegram.webhook.handle
```

Registered once via Telegram's `setWebhook` API call with that public URL.
See `docs/webhook.md` for the full lifecycle, security, and retry handling.

## Folder Structure

```
telegram/
├── bot.py                 # entry point, receives Update dict, calls router
├── handlers/
│   ├── start.py            # /start
│   ├── help.py              # /help
│   ├── link.py               # /link, /unlink
│   ├── voice.py               # voice message → expense
│   ├── report.py               # /report weekly|monthly
│   ├── budget.py                 # /budget (view/set)
│   ├── pocket_money.py             # dependent-only commands
│   └── unknown.py                    # fallback for unrecognized input
├── middleware/
│   ├── auth.py             # resolves telegram_id → User/Dependent, blocks if unlinked
│   ├── rate_limit.py        # basic per-user throttling
│   └── logging.py            # logs every update_id + outcome
├── router.py               # maps update type/command → handler
├── services/
│   └── message_templates.py # reply text/keyboards, kept separate from business logic
├── utils/
│   ├── telegram_api.py      # thin wrapper over Bot API (sendMessage, getFile, etc.)
│   └── file_download.py      # download + temp-store voice files
└── __init__.py
```

## Command Set (summary — full flows in `docs/telegram_commands.md`)

| Command | Persona | Purpose |
|---|---|---|
| `/start` | both | greet, show linking instructions if not linked |
| `/link` | both | begin OTP-based account linking |
| `/unlink` | both | remove Telegram link |
| `/help` | both | list available commands |
| *(voice note)* | both | log an expense via speech |
| `/report weekly` \| `monthly` | Individual | chart + summary for self + dependents |
| `/budget` | Individual | view/set category budgets |
| `/pocketmoney` | Dependent | remaining pocket money for the month |
| *(unknown text/command)* | both | fallback help message |

## Account Linking (summary)

```
/link  →  bot generates a 6-digit OTP, valid 5 min  →
user enters OTP in the Frappe desk (or a linking page)  →
Telegram Link record created (telegram_id ↔ User/Dependent)
```

Full flow: `docs/telegram_commands.md#link`.

## Reply Style

- Confirmations are short: `✅ ₹200 logged under Food (Zomato)`.
- Ambiguous parses ask a clarifying question rather than guessing:
  `🤔 I heard "spent 200 on something" — which category: Food, Travel, Other?`
- Errors are user-friendly, never a raw stack trace or API error string
  (see `docs/error_handling.md`).
