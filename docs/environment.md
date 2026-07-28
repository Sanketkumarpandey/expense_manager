# Environment & Configuration Variables

All configuration is read via `frappe.conf.get("<key>")`, which resolves
from the site's `site_config.json` (set via `bench set-config`) or, if
absent there, from the process environment. **Never hardcode any of these
in source code.**

## Required

| Key | Description | Example |
|---|---|---|
| `sarvam_api_key` | Sarvam AI Speech-to-Text API key | `sk_...` |
| `groq_api_key` | Groq API key for LLM expense parsing | `gsk_...` |
| `telegram_bot_token` | Bot token from @BotFather | `123456:ABC-...` |
| `telegram_webhook_secret` | Random string, verified against Telegram's `X-Telegram-Bot-Api-Secret-Token` header | any long random string |

## Optional (with defaults)

| Key | Description | Default |
|---|---|---|
| `groq_model` | Groq model used for expense parsing | `llama-3.3-70b-versatile` |
| `otp_expiry_minutes` | How long a `/link` token stays valid | `5` |
| `budget_alert_threshold_pct` | Default overspend alert threshold if not set per-Budget | `90` |

## Setting Values

```bash
bench --site expense.local set-config sarvam_api_key "your-key-here"
bench --site expense.local set-config groq_api_key "your-groq-key"
bench --site expense.local set-config groq_model "llama-3.3-70b-versatile"
```

For values that shouldn't be world-readable in `site_config.json` on a
shared machine, prefer environment variables at the process level instead,
and make sure `get_config()` helpers check the environment first:

```python
def get_sarvam_api_key() -> str:
    return os.environ.get("SARVAM_API_KEY") or frappe.conf.get("sarvam_api_key")
```

(Precedence: environment variable wins over site config, so the same
codebase works locally and in any future hosted environment without
code changes.)

## Configuration Getters

All config getters are centralized in `telegram/config.py`:

- `get_telegram_bot_token()` — required
- `get_telegram_webhook_secret()` — required
- `get_sarvam_api_key()` — required
- `get_groq_api_key()` — required
- `get_groq_model()` — optional, defaults to `llama-3.3-70b-versatile`
- `get_use_mock_ai_apis()` — optional, defaults to `False`

All raise `ConfigurationError` if a required value is missing.

## Never Commit

- `sites/*/site_config.json` (already gitignored by Frappe by default —
  verify this stays true)
- Any `.env` file
- Any of the keys above, in any form, anywhere in the repo history

## Test/Mock Mode

For running tests and for Codex development without live keys, support a
`use_mock_ai_apis` config flag (`0`/`1`). When `1`, `ai/speech_to_text.py`
and `ai/ai_parser.py` return canned fixture responses instead of calling
Sarvam AI / Groq. See `docs/testing_strategy.md`.
