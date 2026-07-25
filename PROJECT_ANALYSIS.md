# Expense Manager — Project Analysis

## 1. Repository Structure

`expense_manager` is a Frappe v16 application scaffold. Its tracked runtime
package currently contains app metadata, empty package markers, templates, a
public-assets placeholder, and the standard Frappe hook template. The intended
application architecture is fully described in `docs/`, but its planned
runtime packages (`api/`, `doctype/`, `services/`, `telegram/`, `ai/`, and
`tests/`) do not yet exist.

```text
apps/expense_manager/
├── expense_manager/
│   ├── config/                 # Empty package marker
│   ├── expense_manager/         # Empty nested package created by the scaffold
│   ├── patches/                 # Empty package; no patches registered
│   ├── public/                  # .gitkeep plus empty css/js directories
│   ├── templates/pages/         # Empty package markers
│   ├── __init__.py              # Version: 0.0.1
│   ├── hooks.py                 # Metadata only; all functional hooks commented
│   ├── modules.txt              # "Expense Manager"
│   └── patches.txt              # Empty pre/post-model-sync sections
├── docs/                        # Product, architecture, API, operations, and workflow specs
├── .github/workflows/           # CI and lint workflows
├── AGENTS.md                    # Mandatory implementation instructions
├── README.md                    # Product overview and documentation index
├── pyproject.toml               # Python 3.14 package/lint configuration
└── repository tooling           # .editorconfig, Ruff/pre-commit, ESLint, .gitignore
```

Conventions are documented rather than demonstrated by application code:
snake_case Python modules and methods, PascalCase DocType names, Frappe ORM
over raw SQL, type hints and docstrings for new public code, tabs in Python,
and a 110-character Ruff line limit. CI provisions a fresh Frappe v16 bench,
MariaDB, and Redis, then installs and tests the app.

The working tree already contains user-provided, untracked `AGENTS.md` and
`docs/` content and a modified `README.md`; these are not implementation
changes and are outside this analysis's scope.

## 2. Existing DocTypes

No DocType JSON definitions, controllers, or migrations exist in the source
tree. Therefore, no DocTypes are installed by this app today. The documented
target data model comprises the following planned DocTypes:

| Planned DocType | Purpose | Key ownership/constraints |
|---|---|---|
| Category | An Individual's expense categories | Case-insensitive unique name per `owner_user`; Dependents read the guardian's categories. |
| Budget | Monthly category allocation | Unique category/month/owner; positive allocation; computed spend and alert threshold. |
| Dependent | Family member managed by an Individual | Linked to a guardian and a restricted Frappe User with the `Dependent` role. |
| Pocket Money Allocation | Monthly dependent allowance and savings rollover | Unique dependent/month; computed spend; rollover is service logic. |
| Expense | Canonical spending record | Positive amount; category must belong to the owning Individual; supports Individual or Dependent owner and web/Telegram source. |
| Telegram Link | Telegram ID to Individual/Dependent mapping | One active link per Telegram ID; stores short-lived OTP state and unlink status. |

The documentation also specifies core Frappe `User` as the Individual
identity. No roles, custom permissions, indexes, seed data, or schema files
have been implemented. Suggested initial categories and indexes are design
notes only.

## 3. Existing APIs

There is no `expense_manager/api/` package and no active
`@frappe.whitelist()` method. Consequently, the application exposes no custom
API endpoints at present.

The documented API contract reserves these endpoint groups under
`/api/method/expense_manager.api.*`:

| Module | Planned methods |
|---|---|
| `expense` | `create_expense`, `list_expenses`, `get_expense`, `delete_expense` |
| `budget` | `set_budget`, `get_budget_status` |
| `dependent` | `add_dependent`, `allocate_pocket_money`, `get_pocket_money_status`, `rollover_pocket_money` |
| `report` | `weekly_summary`, `monthly_summary`, `generate_chart_png` |
| `telegram_link` | `generate_otp`, `verify_otp`, `unlink` |

These methods are specifications, not callable endpoints. The documented
layering requires API functions to be thin, reusable wrappers over services,
with validation errors returned as Frappe validation exceptions.

## 4. Existing Reports

No Frappe Report or Query Report directory, report JSON, JavaScript, Python,
or chart-generation code exists. There are no executable reports today.

The planned reporting surface is weekly and monthly category totals for an
Individual or Dependent, with chart-ready data and a PNG renderer for the
Telegram `/report` flow. The design calls for Frappe Query Reports and ORM
queries rather than raw SQL, but neither implementation nor tests are
present.

## 5. Existing Hooks

`hooks.py` defines only application metadata:

- `app_name`: `expense_manager`
- `app_title`: `Expense Manager`
- publisher, description, email, and MIT license metadata

Every operational hook is a commented Frappe scaffold example. In particular,
there are currently no active asset includes, installation hooks, document
events, permission hooks, request/job hooks, authentication hooks, doctypes
extensions, method overrides, scheduler registrations, or privacy-retention
settings. `patches.txt` likewise registers no patches.

## 6. Existing Scheduled Jobs

No scheduled job exists. `scheduler_events` is present only as a commented
template in `hooks.py`, and no `tasks.py` module exists.

The documentation anticipates a running Frappe scheduler for month-end pocket
money rollover and potentially budget-related checks. Webhook processing is
also designed to use `frappe.enqueue`, which is background work rather than a
registered scheduler event. Neither has been implemented.

## 7. Existing Permission System

No custom role, DocType permission matrix, permission query condition, or
`has_permission` implementation is active. Current behaviour is therefore
limited to Frappe defaults for the app's existing (non-custom) artifacts.

The planned permission model is:

| Persona | Intended access |
|---|---|
| Individual | Full CRUD on own Categories, Budgets, Dependents, own Expenses, and Dependents' Expenses. |
| Dependent | Restricted linked User; read guardian categories, create/read only own Expenses, read only own Dependent and pocket-money records, and no Budget access. |
| Telegram Link | System-managed; end users should use the linking flow rather than edit records in Desk. |
| Telegram webhook | Guest endpoint guarded by Telegram's secret-token header; a chat ID alone is never authorization. |

This model requires concrete DocType permission records plus ownership-aware
server-side checks before it can protect data.

## 8. Suggestions for Telegram Integration

The documented webhook-first design is appropriate for Frappe and should be
implemented in the prescribed phases:

1. Add configuration helpers that read bot and AI secrets from environment or
   Frappe site configuration; never persist them in source.
2. Add an `allow_guest=True`, POST-only webhook that verifies
   `X-Telegram-Bot-Api-Secret-Token`, records/deduplicates `update_id`, and
   enqueues processing before returning HTTP 200.
3. Keep the handler/service boundary strict: handlers route updates and format
   replies; services own business logic; the AI modules only transcribe or
   parse; API functions remain Telegram-agnostic.
4. Implement OTP-based identity linking before permitting expense, report, or
   budget operations. Resolve every Telegram ID through a Telegram Link record
   and apply Frappe permissions for its linked identity.
5. Process voice notes asynchronously, download to a unique temporary file,
   delete it in `finally`, then use Sarvam AI for transcription and OpenAI
   structured JSON output. Validate all model output before creating Expenses.
6. Make retries, rate limits, idempotency, structured logging, and friendly
   failure replies part of the first functional webhook release, since the
   design treats them as correctness and cost controls.

The endpoint, command set, failure mapping, test fixtures, and provider
contracts are already specified in `docs/telegram*.md`, `docs/webhook.md`,
`docs/ai.md`, and `docs/error_handling.md`.

## 9. Missing Infrastructure

- All custom DocType schemas, controllers, roles, permission matrices, and
  database indexes.
- API, service, AI, Telegram, configuration, task, install, and utility
  modules.
- Query Reports, chart PNG generation, and report tests.
- Webhook registration utility, secret verification, deduplication storage,
  rate limiting, queue jobs, and outbound Telegram client.
- OTP lifecycle, account-linking UI or Desk workflow, and audited unlinking.
- External dependencies for the planned integrations (for example OpenAI,
  HTTP client, optional image rendering, and potentially audio conversion)
  are not declared in `pyproject.toml`.
- Tests, fixtures, mock-AI support, and test data; CI will install and run
  tests but the app currently contains none.
- Installation/seed-data logic, migrations, documentation completion status,
  operational monitoring, production deployment configuration, backups, and
  a persistent HTTPS endpoint.

## 10. Risks

| Risk | Impact | Current mitigation/status |
|---|---|---|
| Documentation-to-code gap | The documented contract can drift before any implementation validates it. | No runtime implementation exists; follow the phased workflow and test each phase. |
| Unauthorized data access | Telegram identifiers alone could expose household financial data. | OTP linking and secret-token verification are specified but absent. |
| Duplicate expense creation | Telegram retries can replay updates. | `update_id` idempotency is specified but no storage or processing exists. |
| Sensitive-data exposure | Voice recordings, transcripts, expense data, and credentials require careful handling. | Privacy/logging rules are documented; no enforcement code exists. |
| External-provider failures and cost | Sarvam AI/OpenAI latency, changes, outages, and retries can affect reliability and cost. | Timeouts, bounded retries, mock mode, and manual entry fallback are specified only. |
| Incomplete authorization semantics | The planned dynamic owner model and guardian access need robust server-side checks. | Permission requirements are documented but not encoded in schemas or hooks. |
| Version compatibility | The app declares Python `>=3.14`, while its own guidance and Frappe deployment assumptions mention Python 3.11+; package/provider support must be verified when implementation begins. | CI is configured for Python 3.14, but no app dependencies or tests exercise the stack. |
| Production operations | Webhooks require public HTTPS, workers, scheduler, monitoring, backups, and retention controls. | Deliberately deferred; current target is local bench only. |

## 11. Overall Readiness Assessment

The project is ready for the documented analysis and design phases: its
requirements, data model, architecture, error handling, test strategy, and
implementation order are unusually well specified. The repository is not yet
ready for functional use or Telegram integration because it remains a Frappe
scaffold with no custom DocTypes, APIs, reports, permissions, services,
scheduled jobs, or tests.

The appropriate next milestone is the documentation-only Telegram architecture
phase, followed by the folder skeleton and configuration phases in
`docs/codex_workflow.md`. Each phase should reconcile the written contract
with installed Frappe v16 capabilities and add its accompanying tests before
the next phase begins.
