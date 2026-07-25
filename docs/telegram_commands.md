# Telegram Commands — Detailed Flows

## `/start`

```
User sends /start
  → handlers/start.py
    → middleware/auth.py checks Telegram Link
      → if linked: "Welcome back, <name>! Send a voice note to log an expense, or /help."
      → if not linked: "Hi! Send /link to connect your account."
```

## `/help`

Returns a static list of available commands, persona-aware (Individual sees
`/budget`, `/report`; Dependent sees `/pocketmoney`).

## `/link`

```
1. User sends /link
2. handlers/link.py calls api.telegram_link.generate_otp(telegram_id)
3. Bot replies: "Your code is 384920. Enter it in the Expense Manager
   linking page within 5 minutes."
4. User opens the Frappe desk (or a simple /telegram-link web page),
   enters the OTP against their logged-in User (or selects which
   Dependent it's for, if the Individual is linking on their behalf)
5. api.telegram_link.verify_otp(otp, user_or_dependent) creates the
   Telegram Link record, marks OTP used
6. Bot (next interaction, or via a push if feasible) confirms: "✅ Linked!"
```

**Edge cases**: OTP expired → "That code expired, send /link again."
OTP already used → same message. Telegram ID already linked to someone
else → must `/unlink` first.

## `/unlink`

```
User sends /unlink
  → confirms with an inline Yes/No keyboard ("Unlink this Telegram account?")
  → on Yes: api.telegram_link.unlink(telegram_id)
  → reply: "Unlinked. Send /link to reconnect."
```

## Voice Note (no explicit command — message.voice present)

```
1. handlers/voice.py receives the Update
2. middleware/auth.py resolves telegram_id → owner (User or Dependent);
   if unlinked, reply asking the user to /link first — no processing.
3. Downloads the .ogg file via Telegram's getFile + file download URL
4. Calls services/expense_service.create_from_voice(file_path, owner)
   (see docs/architecture.md §3 for the internal AI pipeline)
5. On success: "✅ ₹<amount> logged under <category>" (+ merchant if present)
6. On ambiguous parse: "🤔 I heard '<transcript>' — which category:
   [Food] [Travel] [Other]" (inline keyboard); user's tap creates the
   Expense with the chosen category.
7. On failure (AI down, bad audio): friendly fallback message suggesting
   "/addexpense <amount> <category>" as a manual alternative.
```

## `/addexpense <amount> <category> [merchant] [notes]` (text fallback)

Simple positional-argument command, no AI involved — a direct path to
`services/expense_service.create_expense()`. Exists so the system remains
usable if Sarvam AI or OpenAI are unavailable.

## `/report weekly` / `/report monthly`

```
1. handlers/report.py resolves owner (Individual: self + all Dependents
   sequentially; Dependent: self only)
2. Calls services/report_service.weekly_summary() or monthly_summary()
3. Calls api.report.generate_chart_png(dataset)
4. Sends the PNG via Telegram sendPhoto, with a short text summary
   ("This week: ₹3,200 total — Food ₹1,400, Travel ₹900, ...")
```

## `/budget` (Individual only)

```
/budget                → shows current month's allocated vs. spent per category
/budget set <category> <amount>  → calls api.budget.set_budget()
```

Dependents attempting `/budget` get: "Only the account owner can manage
budgets. Ask <guardian_name>."

## `/pocketmoney` (Dependent only)

```
/pocketmoney → calls api.dependent.get_pocket_money_status()
             → "You have ₹450 left this month (of ₹1,000)."
```

Individual attempting `/pocketmoney` for themselves gets a clarifying
reply, since Individuals don't have pocket money allocations.

## Unknown Input

Any text that doesn't match a command and isn't a voice note falls through
to `handlers/unknown.py`, which replies with the `/help` text plus a hint:
"Not sure what you mean — try sending a voice note, or /help for commands."

## Budget Overspend Notification (system-triggered, not user-initiated)

```
Expense created/updated
  → services/budget_service.check_overspend(category, month)
    → if spent_amount >= alert_threshold_pct% of allocated_amount:
         push a Telegram message to the Individual (and, if configured,
         the Dependent who caused it) via utils/telegram_api.send_message()
```
