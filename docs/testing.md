# Testing (Quick Reference)

For the full strategy (unit/integration/webhook/AI/e2e breakdown), see
`docs/testing_strategy.md`. This file is the quick "how do I run tests"
reference.

## Running Tests

```bash
bench --site mysite.local run-tests --app expense_manager
```

Run a single test module:

```bash
bench --site mysite.local run-tests --module expense_manager.tests.test_expense_service
```

## Test Layout

```
expense_manager/
└── tests/
    ├── test_doctypes/
    │   ├── test_expense.py
    │   ├── test_budget.py
    │   └── test_dependent.py
    ├── test_services/
    │   ├── test_expense_service.py
    │   ├── test_budget_service.py
    │   └── test_report_service.py
    ├── test_api/
    │   └── test_expense_api.py
    ├── test_telegram/
    │   ├── test_router.py
    │   ├── test_handlers_voice.py
    │   └── test_webhook.py
    └── test_ai/
        ├── test_speech_to_text.py   # mocked Sarvam AI responses
        └── test_ai_parser.py         # mocked OpenAI responses
```

## Mocking External APIs

Never call live Sarvam AI or OpenAI APIs in tests. Use `unittest.mock.patch`
on the HTTP client call inside `ai/speech_to_text.py` and `ai/ai_parser.py`,
returning canned JSON fixtures stored under `tests/fixtures/`.

## Minimum Bar Before Marking a Phase Done

- All new/changed code has at least one passing test.
- `bench run-tests` passes with zero failures.
- No test depends on network access or live API keys.
