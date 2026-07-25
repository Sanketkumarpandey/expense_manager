# Telegram Webhook — Lifecycle, Security, Retries

## 1. Registration

One-time (or on config change) setup, done via a bench console command or
a small setup script — not on every server start:

```
POST https://api.telegram.org/bot<TOKEN>/setWebhook
  ?url=https://<site>/api/method/expense_manager.telegram.webhook.handle
  &secret_token=<a random string stored in site config>
```

`secret_token` is Telegram's built-in mechanism for verifying that an
incoming POST really came from Telegram — Telegram echoes it back in the
`X-Telegram-Bot-Api-Secret-Token` header on every webhook call.

## 2. Endpoint

```python
# expense_manager/telegram/webhook.py

@frappe.whitelist(allow_guest=True, methods=["POST"])
def handle():
    verify_secret_token(frappe.request.headers)   # reject if mismatched
    update = frappe.request.get_json()
    log_update(update)                             # persist update_id + payload
    if is_duplicate(update["update_id"]):
        return {"ok": True}                        # idempotent no-op
    enqueue_processing(update)                       # background job, see below
    return {"ok": True}                                # respond fast, always
```

**Must return HTTP 200 quickly** (Telegram times out and retries
otherwise). Actual processing (routing, AI calls) happens in a background
job (`frappe.enqueue`), not inline in the webhook response.

## 3. Security

- Verify `X-Telegram-Bot-Api-Secret-Token` on every request; reject with
  403 if missing/mismatched.
- `allow_guest=True` is required (Telegram isn't a logged-in Frappe user),
  but the secret token substitutes for authentication.
- Never trust `chat.id`/`from.id` alone for authorization — always resolve
  through the `Telegram Link` DocType before allowing any data access.
- Rate-limit per `telegram_id` (see `telegram/middleware/rate_limit.py`) to
  prevent abuse of the AI pipeline (each voice note costs Sarvam AI + GPT
  API calls).

## 4. Idempotency

Telegram may re-send an update if it doesn't get a fast-enough 200. Store
every seen `update_id` (e.g. in a lightweight "Telegram Update Log"
DocType or a Redis set with TTL) and short-circuit duplicates before
enqueuing processing again.

## 5. File Downloads (Voice Notes)

```
1. Update contains message.voice.file_id
2. GET https://api.telegram.org/bot<TOKEN>/getFile?file_id=<file_id>
   → returns file_path
3. Download from
   https://api.telegram.org/file/bot<TOKEN>/<file_path>
4. Save to a temp directory (e.g. /tmp/expense_manager_voice/<uuid>.ogg)
5. Process (transcribe → parse → create expense)
6. Delete the temp file in a `finally` block — always, even on error
```

Max file size: Telegram voice notes are capped by Telegram itself (~20MB
via Bot API); no additional size handling needed beyond a sanity check.

## 6. Retry Policy Summary

| Failure point | Retry behavior |
|---|---|
| Telegram → our webhook | Telegram retries automatically if we don't 200 fast; we must respond within a few seconds regardless of processing time |
| Our webhook → Sarvam AI | 2 retries, exponential backoff, only on network/5xx errors |
| Our webhook → OpenAI GPT | 1 retry on network/5xx; malformed JSON triggers a stricter re-prompt, not a raw retry |
| Background job failure | Logged via `frappe.logger`; user gets a friendly failure reply; job is not silently dropped |

Full error-to-user-message mapping: `docs/error_handling.md`.

## 7. Logging

Every webhook call logs: `update_id`, `telegram_id` (if resolvable),
command/type (voice/text/command), processing outcome (success/failure +
reason), and latency. No raw audio or full transcript in logs beyond what's
needed for debugging (transcript may be logged at debug level only, guarded
by a config flag, since it can include personal spending details).
