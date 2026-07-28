# Telegram Bot Design

## Why Webhook, Not Polling

Polling repeatedly asks Telegram "any new messages?" — wasteful and slow.
A webhook lets Telegram push updates the instant they happen:

```
User → Telegram servers → HTTPS POST → our webhook endpoint → bot.py
```

Endpoint (Frappe whitelisted method, POST-only, allow_guest):

```
https://<site>/api/method/expense_manager.telegram.webhook.handle
```

Registered once via Telegram's `setWebhook` API call with a secret token.
See `docs/webhook.md` for the full lifecycle.

## Folder Structure

```
telegram/
├── bot.py                    # Background dispatcher, sends text replies
├── router.py                 # Command/voice → handler routing
├── webhook.py                # Guest POST ingress, validation, enqueue
├── webhook_management.py     # Webhook register/deregister utilities
├── config.py                 # Secret/config getters (env → site_config)
├── handlers/
│   ├── start.py              # /start — welcome message
│   ├── help.py               # /help — command list (15 commands)
│   ├── link.py               # /link — account linking
│   ├── unlink.py             # /unlink — account unlinking
│   ├── voice.py              # Voice note → expense
│   ├── expense.py            # /expenses, /categories
│   ├── budget.py             # /budgets, /balance
│   ├── report.py             # /report — spending report
│   ├── dependent.py          # /dependents, /pocketmoney, /savings, /rollover
│   ├── account.py            # /profile, /settings
│   └── unknown.py            # Fallback for unrecognized input
├── services/
│   └── telegram_service.py   # Identity resolution + domain orchestration
├── middleware/
│   ├── auth.py               # Link resolution
│   └── logging.py            # Update lifecycle logging
└── utils/
    ├── helpers.py             # get_telegram_user_id, etc.
    └── file_download.py       # Voice file download + temp storage
```

## Command Set

| Command | Purpose | Persona Gate |
|---|---|---|
| `/start` | Welcome message (persona-aware when linked) | Either |
| `/help` | List available commands | Either |
| `/link <code>` | Link Telegram account via token | Either (unlinked) |
| `/unlink` | Deactivate Telegram link | Guardian |
| `/expenses` | View recent expenses | Guardian |
| `/categories` | View categories | Either |
| `/budgets` | View budget allocations | Guardian |
| `/balance` | Check budget balance | Guardian |
| `/report` | Spending report | Guardian |
| `/dependents` | Manage dependents | Guardian |
| `/pocketmoney` | Pocket money allocations | Either (Dependent sees own balance) |
| `/savings` | View savings | Dependent |
| `/rollover` | Roll over pocket money | Dependent |
| `/profile` | View profile | Guardian |
| `/settings` | View settings | Guardian |
| *(voice note)* | Log expense via speech | Either (linked) |
| *(unknown)* | Fallback help hint | Either |

## Reply Style

- Confirmations are short: `✅ ₹200 logged under Food`.
- Errors are user-friendly, never raw stack traces or API error strings.
- Budget overspend warnings are appended to expense confirmations.

## Authentication Strategy

1. **Webhook authenticity**: Telegram's secret-token header protects the
   guest ingress endpoint. Verified on every delivery.
2. **User authorization**: `telegram_user_id` is resolved through either:
   - An active `Telegram Link` (Individual), or
   - A `Dependent.telegram_user_id` field (Dependent)
   The resolved identity determines `owner_user` and permissions.
3. **Persona checks**: `TelegramService._require_guardian()` blocks
   dependents from guardian-only actions (reports, budget, expense mutation).

## Account Linking Flow

```
1. Desk user calls POST /api/method/expense_manager.api.telegram.generate_link_code
   → generates short-lived token, returns {token, expires_at}
2. User sends /link <token> to the bot
   → handlers/link.py calls TelegramService.complete_link(telegram_user_id, token, ...)
   → TelegramLinkService.verify_and_link() creates Telegram Link record
3. Next interaction resolves as linked
4. /unlink deactivates the link (idempotent)
```
