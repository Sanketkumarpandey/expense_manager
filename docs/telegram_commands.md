# Telegram Commands — Detailed Flows

## `/start`

```
User sends /start
  → handlers/start.py
    → TelegramService.get_link_status(telegram_user_id)
      → if linked: "Welcome back! You are linked as a Individual/Dependent."
      → if not linked: "Hi! I'm your Expense Manager bot. Send /help to see the available commands."
```

## `/help`

Returns a static list of 15 available commands (account, expenses/budgets,
dependents sections). No identity lookup required.

## `/link <code>`

```
1. User obtains a link code from the Desk (POST /api/method/...generate_link_code)
2. User sends /link <code> to the bot
3. handlers/link.py calls TelegramService.complete_link(telegram_user_id, token, ...)
4. TelegramLinkService.verify_and_link() validates token, creates Telegram Link record
5. Returns "Your account is now linked! Send /help to get started."
```

**Edge cases**: Token expired → "This link code has expired."
Token invalid → "This link code is invalid or has already been used."
Telegram ID already linked → "This user already has a linked Telegram account."

## `/unlink`

```
User sends /unlink
  → handlers/unlink.py
    → TelegramService.unlink_account(telegram_user_id)
      → TelegramLinkService.unlink_account(owner_user)
      → Returns "Telegram account unlinked."
```

Idempotent: unlinking an already-unlinked user is a no-op.

## Voice Note

```
1. handlers/voice.py receives the Update
2. Resolves telegram_user_id
3. Downloads .ogg via Telegram File API → temp file
4. Calls TelegramService.create_expense_from_voice(telegram_user_id, file_path)
   a. Resolves identity (Individual or Dependent)
   b. AIService.create_expense_from_audio(owner_user, file_path, dependent)
      - speech_to_text.transcribe(file_path) → Sarvam AI → text
      - ai_parser.parse_expense(transcript, known_categories) → Groq → JSON
      - ExpenseService.create_expense(...) → Expense DocType
   c. BudgetService.refresh_budget() + PocketMoneyService.refresh_balance()
   d. Returns formatted message with optional overspend warning
5. Temp file deleted in finally block
6. Reply: "Logged ₹<amount> under <category>."
```

## `/expenses`

```
User sends /expenses
  → TelegramService.list_expenses(telegram_user_id)
    → ExpenseService.get_recent_expenses(owner_user, dependent, limit=10)
    → Returns formatted list
```

## `/categories`

```
User sends /categories
  → TelegramService.list_categories(telegram_user_id)
    → CategoryService.list_categories(owner_user, active_only=True)
    → Returns formatted list
```

## `/budgets`

```
User sends /budgets
  → TelegramService.get_budget(telegram_user_id)
    → ReportService.get_budget_summary(owner_user)
    → Returns budget usage per category
```

Guardian only — dependents are blocked.

## `/balance`

```
User sends /balance
  → TelegramService.get_budget(telegram_user_id)
    → ReportService.get_budget_summary(owner_user)
    → Returns remaining amounts
```

## `/report`

```
User sends /report
  → TelegramService.get_monthly_report(telegram_user_id)
    → ReportService.get_monthly_report(owner_user)
    → Returns monthly totals
```

Guardian only.

## `/dependents`

```
User sends /dependents
  → TelegramService.list_dependents(telegram_user_id)
    → DependentService.list_dependents(owner_user, active_only=True)
    → Returns formatted list
```

Guardian only.

## `/pocketmoney`

```
User sends /pocketmoney
  → TelegramService.get_pocket_money(telegram_user_id)
    → If Dependent: PocketMoneyService.get_balance(owner_user, dependent) → own balance
    → If Guardian: PocketMoneyService.list_allocations(owner_user, active_only=True) → all allocations
```

## `/savings`

```
User sends /savings
  → handlers/dependent.py → TelegramService.get_pocket_money(telegram_user_id)
    → PocketMoneyService.get_balance(owner_user, dependent)
    → Returns remaining amount info
```

Dependent only.

## `/rollover`

```
User sends /rollover
  → handlers/dependent.py → TelegramService.rollover_pocket_money(telegram_user_id)
    → PocketMoneyService.rollover_allocation(owner_user, dependent)
      → Archives current allocation
      → Creates new allocation with carry-forward
    → Returns "Rolled over! New balance: ₹<amount>."
```

Dependent only. Fails if `allow_carry_forward` is disabled or no active
allocation exists.

## `/profile`

```
User sends /profile
  → TelegramService.get_link_status(telegram_user_id)
    → Returns role (Individual/Dependent), owner, dependent info
```

## `/settings`

```
User sends /settings
  → Returns configuration info
```

## Unknown Input

Any text that doesn't match a command falls through to `handlers/unknown.py`,
which returns the `/help` text plus a hint.

## Budget Overspend Notification (system-triggered)

```
Expense created/updated
  → ExpenseService.create_expense() calls BudgetService.refresh_budget()
    → BudgetService._check_overspend(budget)
      → If spent > allocated: logs overspend
      → If pct_used >= alert_threshold_pct: logs threshold warning
  → Daily job run_budget_alerts():
    → Scans all active budgets
    → Refreshes spent amounts
    → Sends Telegram notification to linked guardian if threshold crossed
    → Marks alert sent (idempotent: once per day per budget)
```
