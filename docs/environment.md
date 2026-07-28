# Environment & Configuration Variables

All configuration is read via `frappe.conf.get("<key>")`, which resolves
from the site's `site_config.json` (set via `bench set-config`) or, if
absent there, from the process environment. **Never hardcode any of these
in source code.**

## Required

| Key | Description | Example |
|---|---|---|
| `sarvam_api_key` | Sarvam AI Speech-to-Text API key | `sk_...` |
| `openai_api_key` | OpenAI API key | `sk-...` |
| `telegram_bot_token` | Bot token from @BotFather | `123456:ABC-...` |
| `telegram_webhook_secret` | Random string, verified against Telegram's `X-Telegram-Bot-Api-Secret-Token` header | any long random string |

## Optional (with defaults)

| Key | Description | Default |
|---|---|---|
| `openai_model` | GPT model used for expense parsing | `gpt-4o-mini` |
| `sarvam_stt_model` | Sarvam AI model name | `saarika:v2` |
| `expense_parse_language_hint` | Default language hint passed to Sarvam AI | `unknown` (auto-detect) |
| `otp_expiry_minutes` | How long a `/link` token stays valid | `5` |
| `budget_alert_threshold_pct` | Default overspend alert threshold if not set per-Budget | `90` |
| `ai_request_timeout_seconds` | Timeout for both Sarvam AI and OpenAI calls | `30` |
| `enable_debug_transcript_logging` | Whether raw transcripts are logged at debug level | `0` (off) |

## Setting Values

```bash
bench --site expense.local set-config sarvam_api_key "your-key-here"
bench --site expense.local set-config openai_model "gpt-4o-mini"
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
- `get_openai_api_key()` — required
- `get_openai_model()` — optional, defaults to `gpt-4o-mini`
- `get_sarvam_stt_model()` — optional, defaults to `saarika:v2`

All raise `frappe.ValidationError` if a required value is missing.

## Never Commit

- `sites/*/site_config.json` (already gitignored by Frappe by default —
  verify this stays true)
- Any `.env` file
- Any of the keys above, in any form, anywhere in the repo history

## Test/Mock Mode

For running tests and for Codex development without live keys, support a
`use_mock_ai_apis` config flag (`0`/`1`). When `1`, `ai/speech_to_text.py`
and `ai/ai_parser.py` return canned fixture responses instead of calling
Sarvam AI / OpenAI. See `docs/testing_strategy.md`.
