# AGENTS.md — Instructions for Codex

This file governs how any autonomous coding agent (Codex CLI, Claude Code, etc.)
should behave inside this repository. Read this file, and every file in
`docs/`, before writing or modifying any code.

## 0. Golden Rules

1. **Never work on the whole project at once.** Follow `docs/codex_workflow.md`
   phase by phase. Each phase ends in a compiling, testable state.
2. **Never invent a DocType, field, or API route** that is not described in
   `docs/doctypes.md` or `docs/api.md`. If something is missing, stop and add
   a note to the "Known Limitations & Deferred Work" section of `README.md`
   instead of guessing.
3. **Never hardcode secrets** (bot tokens, API keys, DB passwords). Always read
   from Frappe site config (`site_config.json`) or environment variables —
   see `docs/environment.md`.
4. **Reuse existing Frappe primitives.** Use `frappe.get_doc`, `frappe.db`,
   Frappe's permission system, and the Report/Query Report framework instead
   of writing raw SQL or parallel validation logic.
5. **One responsibility per file.** Handlers only parse/route Telegram
   updates. Services only contain business logic. AI modules only call
   external AI APIs and normalize their output. See `docs/architecture.md`.
6. **Write tests as you go**, per `docs/testing.md` and
   `docs/testing_strategy.md`. A phase is not "done" until its tests pass.
7. **Log, don't print.** Use Frappe's logger (`frappe.logger("expense_manager")`)
   for anything that happens outside an HTTP request/response cycle
   (webhooks, background jobs, AI calls).
8. **Ask instead of assuming.** If a requirement is ambiguous, write the
   question into the "Known Limitations & Deferred Work" section of `README.md`
   and pick the most
   conservative reasonable default so work isn't blocked.

## 1. Repository Map

```
apps/expense_manager/expense_manager/
├── api/            # whitelisted Frappe REST endpoints
├── telegram/        # bot.py, handlers/, services/, middleware/, utils/
├── ai/               # speech_to_text.py (Sarvam AI), ai_parser.py (Groq LLM)
├── services/         # shared business logic (expense_service, budget_service, ...)
├── doctype/          # Frappe DocTypes (Expense, Budget, Dependent, ...)
├── templates/ www/   # any user-facing web pages (optional, low priority)
├── hooks.py
└── config.py
```

## 2. Tech Stack Reference

- Framework: Frappe v16 (Python 3.11+, MariaDB, Redis, Bench)
- Bot: python-telegram-bot or raw Telegram Bot API via webhook
- Speech-to-text: **Sarvam AI** Speech-to-Text API (see `docs/ai.md`)
- Expense parsing: **Groq LLM** (llama-3.3-70b-versatile by default, see `docs/prompts.md`)
- Deployment target for this phase: **local bench** (see `docs/deployment.md`)

## 3. Definition of Done (per phase)

- Code implements only what that phase's prompt describes — nothing more.
- Unit tests exist and pass (`bench --site <site> run-tests --app expense_manager`).
- No secrets committed. No TODOs left unexplained.
- A short entry is added to `docs/roadmap.md` under "Completed".

## 4. Things Codex Should Never Do

- Never call `frappe.db.sql` for anything expressible via the ORM.
- Never bypass Frappe permissions with `ignore_permissions=True` unless the
  phase prompt explicitly says to (e.g. system-triggered budget alerts).
- Never commit `.env`, `sites/*/site_config.json`, or any token/key.
- Never delete or rewrite a previous phase's code without being asked.

See `docs/codex_workflow.md` for the exact phase-by-phase prompts to follow.
