# Deployment — Local Bench (Current Phase)

Production deployment (VPS, Nginx, Supervisor, HTTPS certs) is explicitly
**out of scope for this phase** — see `docs/roadmap.md`. This doc covers
running everything locally for development and demoing.

## 1. Prerequisites

- Frappe Bench installed (`pip install frappe-bench`), with its own
  prerequisites: Python 3.14+, Node.js, MariaDB, Redis, yarn/npm.
- A Sarvam AI API key (sign up at sarvam.ai).
- An OpenAI API key.
- A Telegram bot token (from @BotFather).
- A public HTTPS URL for the webhook during local development — Telegram
  requires HTTPS, so a tunnel is needed since `localhost` isn't reachable
  from Telegram's servers. Use a tunneling tool (e.g. ngrok or a similar
  service) to expose your local bench site.

## 2. Bench & Site Setup

```bash
bench init frappe-bench --frappe-branch version-16
cd frappe-bench
bench new-site expense.local
bench get-app expense_manager <repo_url_or_local_path>
bench --site expense.local install-app expense_manager
```

## 3. Configuration (site config, not environment files)

```bash
bench --site expense.local set-config sarvam_api_key "<key>"
bench --site expense.local set-config openai_api_key "<key>"
bench --site expense.local set-config openai_model "gpt-4o-mini"
bench --site expense.local set-config sarvam_stt_model "saarika:v2"
bench --site expense.local set-config telegram_bot_token "<token>"
bench --site expense.local set-config telegram_webhook_secret "<random string>"
```

Full variable list and precedence rules: `docs/environment.md`.

## 4. Start the Bench

```bash
bench start
```

This runs the web server, background workers (needed for the Telegram
webhook's enqueued jobs — see `docs/webhook.md`), and the scheduler
(needed for daily jobs: budget alerts, reminders, monthly rollover).

## 5. Exposing the Webhook Locally

```bash
ngrok http 8000     # or whichever port bench serves on
```

Take the resulting HTTPS URL and register it with Telegram:

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://<ngrok-subdomain>.ngrok.io/api/method/expense_manager.telegram.webhook.handle" \
  -d "secret_token=<same value as telegram_webhook_secret>"
```

## 6. Verifying the Setup

```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

Should show your URL with no pending errors. Then send `/start` to the bot
from Telegram and confirm a reply arrives.

## 7. Running Background Workers & Scheduler

Bench's `bench start` runs these automatically in development. If running
components separately:

```bash
bench worker --queue default
bench schedule
```

The scheduler runs these daily jobs (registered in `hooks.py`):
- `expense_manager.jobs.budget_alerts.run_budget_alerts` — budget overspend alerts
- `expense_manager.jobs.reminders.run_reminders` — no-expenses, weekly/monthly summary, low balance
- `expense_manager.jobs.monthly_rollover.run_monthly_rollover` — pocket money allocation rollover

## 8. Running Tests

```bash
bench --site expense.local run-tests --app expense_manager
```

Currently **290 tests** across service unit tests, integration tests,
webhook tests, router tests, config tests, and reminder tests.

## 9. What's Deferred to a Later Phase

- Supervisor/systemd process management
- Nginx reverse proxy + real TLS certificate (Let's Encrypt)
- Persistent public domain instead of an ngrok tunnel
- Site backup/restore automation
- CI/CD pipeline

These will get their own `docs/deployment.md` update (or a new
`docs/deployment_production.md`) when that phase begins.
