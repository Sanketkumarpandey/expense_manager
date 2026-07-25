# AI Integration — Sarvam AI + OpenAI GPT

Two separate AI calls, kept in two separate modules, each with one job:

```
ai/
├── speech_to_text.py   # Sarvam AI: audio → text
└── ai_parser.py        # OpenAI GPT: text → structured Expense JSON
```

## 1. Speech-to-Text — Sarvam AI

**Why Sarvam AI:** strong accuracy for Indian-English and Hindi/Hinglish
speech, which is common in everyday spoken expense descriptions
("dukaan se 500 ka saaman liya").

### Responsibility of `speech_to_text.py`

```python
def transcribe(file_path: str, language_hint: str | None = None) -> str:
    """
    Sends the given audio file to Sarvam AI's speech-to-text endpoint
    and returns plain transcribed text. Raises SpeechToTextError on
    failure. Does NOT do any expense parsing.
    """
```

### Call Shape (reference — confirm exact request/response shape against
current Sarvam AI docs before implementation, since API details can change)

```python
import requests

def transcribe(file_path: str, language_hint: str | None = None) -> str:
    with open(file_path, "rb") as f:
        response = requests.post(
            "https://api.sarvam.ai/speech-to-text",
            headers={"API-Subscription-Key": get_sarvam_api_key()},
            files={"file": f},
            data={
                "model": "saarika:v2",       # confirm current model name
                "language_code": language_hint or "unknown",
            },
            timeout=30,
        )
    response.raise_for_status()
    data = response.json()
    return data["transcript"]
```

### Requirements

- Timeout: 30s, with 2 retries (exponential backoff) on network errors only
  — not on 4xx (bad audio) errors.
- Input: Telegram voice notes arrive as `.ogg` (OPUS). Confirm Sarvam AI
  accepts `.ogg` directly; if not, transcode to `.wav`/`.mp3` with `ffmpeg`
  as a pre-processing step in `telegram/utils/file_download.py`.
- Never log the raw audio content; log only file size, duration, and
  success/failure + latency.
- Config: `sarvam_api_key` read from site config / environment — see
  `docs/environment.md`. Never hardcoded.

## 2. Expense Parsing — OpenAI GPT

**Why a separate step:** transcription and understanding are different
problems. Keeping them separate means either provider can be swapped
independently (e.g. Sarvam AI for Hindi transcription, GPT for structured
extraction in English).

### Responsibility of `ai_parser.py`

```python
def parse_expense(text: str, known_categories: list[str]) -> dict:
    """
    Sends transcribed text + the user's known categories to OpenAI GPT
    and returns a dict matching the Expense JSON schema (see
    docs/prompts.md). Raises ExpenseParseError on malformed output.
    Does NOT write to the database.
    """
```

### Model & Call Shape

- Default model: `gpt-4o-mini` (cheap, fast, good enough for structured
  extraction). Configurable to `gpt-4o` via environment for higher accuracy
  if needed — see `docs/environment.md`.
- Uses OpenAI's structured output / JSON mode so the response is guaranteed
  parseable JSON (no markdown fences, no extra prose).
- Full prompt template and JSON schema: `docs/prompts.md`.

```python
from openai import OpenAI

client = OpenAI(api_key=get_openai_api_key())

def parse_expense(text: str, known_categories: list[str]) -> dict:
    response = client.chat.completions.create(
        model=get_gpt_model(),               # default "gpt-4o-mini"
        response_format={"type": "json_object"},
        messages=build_expense_extraction_prompt(text, known_categories),
        timeout=20,
    )
    raw = response.choices[0].message.content
    return validate_expense_json(raw)         # schema + category check
```

### Validation Before Trusting GPT Output

`validate_expense_json()` must check, before anything is written to the DB:

1. Output is valid JSON with exactly the expected keys.
2. `amount` is a positive number.
3. `category` is either one of `known_categories` or explicitly `"uncategorized"`
   — never a category GPT invented that doesn't exist in the DocType.
4. `date` defaults to "today" if GPT couldn't infer one; never a future date.
5. If validation fails, raise `ExpenseParseError` — the Telegram handler then
   sends a clarifying question instead of creating a bad record (see
   `docs/telegram_commands.md` and `docs/error_handling.md`).

### Cost & Rate Considerations

- Both Sarvam AI and OpenAI calls happen once per voice note — no batching
  needed at this scale.
- Track approximate cost per transcription/parse in logs (tokens used,
  audio duration) to make monthly cost estimation possible later.
- Free-tier / low-cost fallback: for local development, allow a mocked
  `ai/` module (returns canned responses) so Codex and tests don't need
  live API keys — see `docs/testing_strategy.md`.

## 3. Failure Modes & Fallbacks

| Failure | Handling |
|---|---|
| Sarvam AI timeout/5xx | Retry twice, then reply "couldn't understand the voice note, please try again or type it instead" |
| Sarvam AI returns empty transcript | Same as above |
| GPT returns invalid JSON | Retry once with a stricter prompt; if it still fails, ask user to clarify amount/category via text |
| GPT infers an unknown category | Falls back to "Uncategorized", flagged in the reply so the user can correct it |
| Both APIs down | Expense creation falls back to a manual `/addexpense amount category` text command |

Full retry/backoff policy: `docs/error_handling.md`.
