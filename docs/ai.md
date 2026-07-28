# AI Integration — Sarvam AI + Groq LLM

Two separate AI calls, kept in two separate modules, each with one job:

```
ai/
├── speech_to_text.py   # Sarvam AI: audio → text
└── ai_parser.py        # Groq LLM: text → structured Expense JSON
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
    and returns plain transcribed text. Raises SpeechTranscriptionError on
    failure. Does NOT do any expense parsing.
    """
```

### Requirements

- Timeout: 30s, with 2 retries (exponential backoff) on network errors only
  — not on 4xx (bad audio) errors.
- Input: Telegram voice notes arrive as `.ogg` (OPUS). Sarvam AI accepts
  `.ogg` directly.
- Never log the raw audio content; log only file size, duration, and
  success/failure + latency.
- Config: `sarvam_api_key` read from site config / environment — see
  `docs/environment.md`. Never hardcoded.

## 2. Expense Parsing — Groq LLM

**Why a separate step:** transcription and understanding are different
problems. Keeping them separate means either provider can be swapped
independently (e.g. Sarvam AI for Hindi transcription, Groq for structured
extraction).

### Responsibility of `ai_parser.py`

```python
def parse_expense(text: str, known_categories: list[str]) -> dict:
    """
    Sends transcribed text + the user's known categories to Groq LLM
    and returns a dict matching the Expense JSON schema (see
    docs/prompts.md). Raises ExpenseParsingError on malformed output.
    Does NOT write to the database.
    """
```

### Model & Call Shape

- Default model: `llama-3.3-70b-versatile` (fast, capable structured
  extraction). Configurable via `groq_model` in site config — see
  `docs/environment.md`.
- Uses Groq's structured output / JSON mode so the response is guaranteed
  parseable JSON (no markdown fences, no extra prose).
- Full prompt template and JSON schema: `docs/prompts.md`.

```python
from groq import Groq

client = Groq(api_key=get_groq_api_key())

def parse_expense(text: str, known_categories: list[str]) -> dict:
    response = client.chat.completions.create(
        model=get_groq_model(),               # default "llama-3.3-70b-versatile"
        response_format={"type": "json_object"},
        messages=build_expense_extraction_prompt(text, known_categories),
        timeout=20,
    )
    raw = response.choices[0].message.content
    return validate_expense_json(raw)         # schema + category check
```

### Validation Before Trusting LLM Output

`validate_expense_json()` must check, before anything is written to the DB:

1. Output is valid JSON with exactly the expected keys.
2. `amount` is a positive number.
3. `category` is either one of `known_categories` or explicitly `"Uncategorized"`
   — never a category the LLM invented that doesn't exist in the DocType.
4. `date` defaults to "today" if the LLM couldn't infer one; never a future date.
5. If validation fails, raise `ExpenseParsingError` — the Telegram handler then
   sends a clarifying question instead of creating a bad record (see
   `docs/telegram_commands.md` and `docs/error_handling.md`).

### Cost & Rate Considerations

- Both Sarvam AI and Groq calls happen once per voice note — no batching
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
| Groq returns invalid JSON | Retry once with a stricter prompt; if it still fails, ask user to clarify amount/category via text |
| Groq infers an unknown category | Falls back to "Uncategorized", flagged in the reply so the user can correct it |
| Both APIs down | Expense creation falls back to a manual `/addexpense amount category` text command |

Full retry/backoff policy: `docs/error_handling.md`.
