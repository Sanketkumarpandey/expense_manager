# Error Handling, Logging & Recovery

## Guiding Principle

No raw exception, stack trace, or API error string ever reaches a Telegram
reply. Every known failure mode maps to a specific, friendly message, and
every failure is logged with enough context to debug it later.

## Exception Hierarchy

Defined in `services/exceptions.py`:

```
ExpenseManagerError (base)
├── ValidationError
├── CategoryError
│   ├── CategoryAlreadyExistsError
│   ├── CategoryNotFoundError
│   ├── CategoryInUseError
│   └── CategoryInactiveError
├── BudgetError
│   ├── BudgetAlreadyExistsError
│   ├── BudgetNotFoundError
│   ├── BudgetExceededError
│   ├── InvalidBudgetPeriodError
│   ├── InvalidBudgetAmountError
│   ├── InvalidBudgetDateRangeError
│   └── InvalidAlertThresholdError
├── ExpenseError
│   ├── ExpenseNotFoundError
│   ├── InvalidExpenseAmountError
│   ├── InvalidExpenseSourceError
│   ├── InvalidExpenseDateError
│   ├── ExpenseModificationError
│   └── ExpenseDeletionError
├── DependentError
│   ├── DependentAlreadyExistsError
│   ├── DependentNotFoundError
│   ├── DependentInactiveError
│   ├── DependentInUseError
│   ├── InvalidRelationshipError
│   └── InvalidAllowanceError
├── PocketMoneyError
│   ├── PocketMoneyNotAllocatedError
│   ├── PocketMoneyExceededError
│   ├── InsufficientBalanceError
│   ├── SavingsRolloverError
│   ├── PocketMoneyAllocationNotFoundError
│   ├── PocketMoneyAllocationAlreadyExistsError
│   ├── InvalidAllocationAmountError
│   ├── InvalidAllocationPeriodError
│   ├── InvalidAllocationDateError
│   └── InvalidCarryForwardAmountError
├── TelegramError
│   ├── TelegramLinkRequiredError
│   ├── TelegramAlreadyLinkedError
│   ├── TelegramNotLinkedError
│   ├── InvalidTelegramLinkCodeError
│   ├── ExpiredTelegramLinkCodeError
│   └── TelegramUserNotFoundError
├── ReportError
│   └── InvalidReportDateRangeError
├── TelegramServiceError
│   └── UnauthorizedTelegramActionError
└── AIError (in ai/exceptions.py)
    ├── SpeechToTextError
    └── ExpenseParseError
```

Handlers catch `ExpenseManagerError` (the base class) and map it to a
friendly message. `TelegramService` wraps all service calls and returns
`{"success": False, "message": str(exc)}`.

## Retry Policy

| Call | Retries | Backoff | Retry on |
|---|---|---|---|
| Sarvam AI transcribe | 2 | exponential (1s, 3s) | network, timeout, 5xx |
| Groq LLM parse | 1 | fixed 2s | network, timeout, 5xx |
| Groq malformed JSON | 1 re-prompt | n/a | schema validation failure |
| Telegram sendMessage | direct | none | n/a (raises on failure) |
| Frappe background job | Frappe queue config | n/a | job exceptions |

Never retry on 4xx errors — those indicate bad input, not transient failure.

## User-Facing Message Mapping

| Internal error | Telegram reply |
|---|---|
| `TelegramNotLinkedError` | "This Telegram account is not linked." |
| `UnauthorizedTelegramActionError` | "This action is only available to the account guardian." |
| `ExpenseManagerError` (generic) | The exception message itself (always user-friendly) |
| Unknown/unexpected exception | "Sorry, I couldn't process that voice note. Please try again or type your expense instead." |

## Logging Standards

- Use `frappe.logger("expense_manager")` everywhere outside HTTP requests.
- Log at minimum: operation name, outcome, relevant IDs (owner_user, telegram_user_id).
- Never log: API keys/tokens, raw voice audio, full transcripts at info level.
- Structured key=value format for grep-ability.

## Recovery / Idempotency

- Telegram webhook retries absorbed via Redis `update_id` deduplication (24h TTL).
- Background job failures logged via `frappe.logger`; user gets friendly failure reply.
- If both AI providers are unavailable, system is usable via manual commands.
- Budget alerts are idempotent: `can_send_budget_alert()` checks if already sent today.
- Pocket money rollover checks period end before rolling over.
