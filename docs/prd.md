# Product Requirements Document — Expense Manager

## 1. Problem Statement

Tracking day-to-day personal and family expenses is tedious enough that most
people give up on it within weeks. Typing an expense into an app after every
purchase adds friction; a voice note to a chat app you already use (Telegram)
removes it.

## 2. Goals

- Let an Individual log an expense in under 5 seconds via a Telegram voice
  note, with automatic categorization.
- Let an Individual track a monthly budget per category and be warned before
  they overspend, not after.
- Let an Individual manage Dependents' pocket money without needing the
  Dependent to have desk access.
- Let both personas see where their money went, weekly and monthly, with
  visual reports.

## 3. Non-Goals

- Bank/UPI integration or automatic transaction import (manual/voice entry
  only, for now).
- Multi-currency.
- Any channel other than Telegram for logging expenses (web/desk form is a
  secondary path, not the primary one).

## 4. Personas

### 4.1 Individual

The account owner. Has full desk access to Frappe.

**User Stories**

- As an Individual, I can create expense categories (Food, Medical, Travel,
  Utilities, ...) so my spending is organized the way I think about it.
- As an Individual, I can set a monthly budget per category and get notified
  when I'm close to or over it.
- As an Individual, I can send a Telegram voice note describing an expense
  and have it automatically logged with the right amount and category, with
  a confirmation reply.
- As an Individual, I can add a Dependent and allocate them monthly pocket
  money.
- As an Individual, I can view weekly and monthly expense reports, with
  charts, for myself and each Dependent.

### 4.2 Dependent

A family member (e.g. a child) without desk access, interacting purely
through Telegram.

**User Stories**

- As a Dependent, I can record my own expenses (voice or text) via Telegram.
- As a Dependent, I can ask the bot how much pocket money I have left this
  month.
- As a Dependent, I can roll over unused pocket money at month-end into a
  "savings" balance instead of losing it.

## 5. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Create/edit/delete expense categories | Must |
| FR-2 | Set a per-category monthly budget | Must |
| FR-3 | Overspend notification (Telegram) when a category exceeds budget | Must |
| FR-4 | Voice note → transcription (Sarvam AI) → structured parse (OpenAI GPT) → Expense record | Must |
| FR-5 | Text-based manual expense entry as a fallback | Must |
| FR-6 | Add/manage Dependents, each with their own Telegram link | Must |
| FR-7 | Allocate & track monthly pocket money per Dependent | Must |
| FR-8 | Pocket money rollover to savings at month-end | Should |
| FR-9 | Weekly/monthly report with chart, for self and dependents | Must |
| FR-10 | Telegram account linking via OTP | Must |
| FR-11 | Graceful fallback when AI providers fail | Must |

## 6. Non-Functional Requirements

- **Latency**: voice note → confirmation reply should complete in under
  ~10 seconds under normal conditions (dominated by Sarvam AI + GPT round
  trips).
- **Reliability**: webhook must handle Telegram's retry-on-timeout behavior
  without creating duplicate Expense records (idempotency by `update_id`).
- **Security**: bot tokens and AI API keys never hardcoded or logged; OTP
  linking prevents an unauthorized Telegram account from posting expenses
  against someone else's budget.
- **Privacy**: raw voice audio is deleted immediately after transcription;
  only the transcript and resulting Expense record are retained.

## 7. Success Criteria (for this assignment/phase)

- A working end-to-end flow: voice note → Expense record → confirmation,
  running on a local bench install.
- Budget and pocket money tracking functional with at least manual/desk
  entry, voice entry as the showcased happy path.
- Weekly/monthly report retrievable via `/report` with a chart image.
- Documented, phase-based Codex workflow that another engineer (or another
  AI agent) could pick up and continue from any checkpoint.

## 8. Open Questions

_(Move anything undecided here rather than guessing in code — see
`AGENTS.md` rule 8.)_

- Which languages must Sarvam AI reliably support beyond English/Hindi?
- Should overspend notifications also email, or Telegram-only?
- Exact list of default expense categories to seed on install?
