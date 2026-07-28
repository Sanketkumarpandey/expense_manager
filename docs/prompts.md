# Prompt Templates & JSON Schemas

All LLM calls use Groq's JSON mode (`response_format={"type": "json_object"}`)
so responses are guaranteed parseable JSON — no markdown fences to strip.

## 1. Expense Extraction Prompt

Used by `ai/ai_parser.py :: parse_expense()`.

**System message:**

```
You extract structured expense data from a short, informally spoken
sentence about a purchase. You must respond with ONLY a JSON object
matching this exact schema, no other text:

{
  "amount": <number>,
  "category": <string, must be one of the provided known categories,
              or "uncategorized" if none fit>,
  "merchant": <string or null>,
  "date": <string in YYYY-MM-DD format, or null if not mentioned>,
  "notes": <string or null, any extra detail that doesn't fit elsewhere>,
  "confidence": <number 0-1, your confidence this extraction is correct>
}

Rules:
- If no amount can be determined, set "amount" to null.
- Never invent a category that isn't in the provided list.
- If the sentence mentions a relative date ("yesterday", "this morning"),
  resolve it against the provided current_date.
- Respond with the JSON object only.
```

**User message (templated):**

```
current_date: {current_date}
known_categories: {known_categories_json_list}
transcript: "{transcript_text}"
```

**Example**

Input transcript: `"spent 200 on zomato"`
known_categories: `["Food", "Travel", "Medical", "Utilities", "Uncategorized"]`

Expected output:

```json
{
  "amount": 200,
  "category": "Food",
  "merchant": "Zomato",
  "date": null,
  "notes": null,
  "confidence": 0.92
}
```

`date: null` → `ai_parser.py` fills in today's date before returning, per
`docs/ai.md`.

## 2. Clarification Prompt (low-confidence / missing amount)

Used when `amount` is null or `confidence` < 0.5. Rather than a second GPT
call, this is handled entirely in `telegram/handlers/voice.py` with a
templated reply (see `docs/telegram_commands.md`) — no need to spend a
second API call asking GPT to ask a question.

## 3. Category Suggestion Prompt (optional, future)

For onboarding: given a list of merchant names or transcript history,
suggest a starter category list. Not required for the current phase —
listed here so the schema is decided in advance if it's built later.

```
System: Suggest up to 8 sensible personal-expense categories for a user
in India, as a JSON array of strings, e.g. ["Food", "Travel", ...].
```

## Validation Layer (`ai/ai_parser.py :: validate_expense_json`)

Every response is checked against this before being trusted:

| Check | Action on failure |
|---|---|
| Valid JSON, exact keys present | raise `ExpenseParseError` |
| `amount` is a positive number or null | null → trigger clarification flow |
| `category` in known_categories ∪ {"uncategorized"} | force to "Uncategorized" |
| `date` parses as ISO date and is not in the future | fallback to today |
| `confidence` between 0 and 1 | default to 0.5 if missing |

## Versioning

If the prompt wording changes, bump a `PROMPT_VERSION` constant in
`ai_parser.py` and note the change here with a date, so past `raw_transcript`
+ output pairs can be understood in context later.

- v1 (current) — schema and rules as above.
