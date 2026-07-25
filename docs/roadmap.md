# Roadmap

Tracks what's built vs. planned. Update the "Completed" section at the end
of every phase (see `docs/codex_workflow.md`).

## Phase Plan (summary — full prompts in `docs/codex_workflow.md`)

1. Project analysis (read-only) — `PROJECT_ANALYSIS.md`
2. Telegram architecture design (docs only)
3. Folder/module skeletons (no logic)
4. Telegram configuration (secrets, environment)
5. Webhook receive + verify + log (no command handling)
6. Command routing (`/start`, `/help`, `/link`, `/unlink`, unknown)
7. Account linking (OTP flow)
8. Voice message receive/download (no transcription yet)
9. Sarvam AI speech-to-text integration
10. OpenAI GPT expense parsing (text → JSON)
11. Expense creation from parsed JSON
12. Reports (`/report weekly|monthly`, chart PNGs)
13. Budget alerts (Telegram notification on overspend)
14. *(future)* Pocket money allocation + rollover for Dependents
15. *(future)* Dependent-specific commands (`/pocketmoney`)
16. *(future)* Production deployment (VPS/Nginx/Supervisor) — see
    `docs/deployment.md` for what's deferred vs. in scope now

## Completed

_(Codex/you: append one line per finished phase here, with date.)_

- [ ] Phase 1 — Project analysis
- [ ] Phase 2 — Telegram architecture doc
- [ ] Phase 3 — Folder skeleton
- [x] Phase 4 — Telegram config (2026-07-22)
- [x] Phase 5 — Webhook receive (2026-07-22)
- [x] Phase 6 — Command routing (2026-07-22)
- [ ] Phase 7 — Account linking
- [ ] Phase 8 — Voice receive/download
- [ ] Phase 9 — Sarvam AI integration
- [ ] Phase 10 — OpenAI GPT parsing
- [ ] Phase 11 — Expense creation
- [ ] Phase 12 — Reports
- [ ] Phase 13 — Budget alerts

## Explicitly Out of Scope (for now)

- Multi-currency
- Non-Telegram bot channels (WhatsApp, etc.)
- Production/VPS deployment (deferred — current phase targets local bench only)
- Mobile app
