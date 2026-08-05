# Omni-CIO — V9 protected runtime + V10 active development program

Omni-CIO is one investment platform. The current production/recovery surface remains the owner-accepted Custom GPT v9.0.0 + one production Gateway, while V10 is developed sequentially in the same repository.

## Current release and development state

Applied and repository-aligned production configuration: **`Omni-CIO API | Управляющий и аналитик v9.0.0`**.  
Instructions: **`gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`**.  
Knowledge: **`gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`**.

The **existing** GPT was upgraded in place and owner-accepted on 2026-08-05. V9 WP0–WP15 are complete. V9 runtime mode remains **controlled maintenance**. Protected rollback Instructions remain `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.

The owner-approved V10 feature program is active after explicit `START V10` on 2026-08-05. Current V10 progress/next work package is defined only by `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`; V10 work does not retire V9 or expand broker authority by itself.

```text
CURRENT PRODUCTION / RECOVERY
GitHub main ──► Render / omni-cio-gateway (`app:app`)
                    │
                    ├─ production read-only broker contour
                    ├─ optional virtual Sandbox contour
                    ├─ exact-owner-confirmed Real execution contour
                    ├─ Upstash durable state
                    └─ hidden signed Watchtower/QStash routes

Canonical GitHub GPT config ──owner applies/recovers──► EXISTING Omni-CIO GPT v9.0.0

ACTIVE DEVELOPMENT
V10 Program Lock + Master Plan
        │
        └─ sequential WP delivery in this same repository
           (one deterministic Core; future Web/Telegram/AI adapters)
```

Gateway: `https://omni-cio-gateway.onrender.com`  
OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`  
Current V9 runtime status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.  
Current V10 program status: `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## Where to look first

| Need | Canonical source |
|---|---|
| Mandatory engineering rules | `AGENTS.md` |
| Long-lived project context | `knowledge/00_PROJECT_MASTER_CONTEXT.md` |
| Current V9 runtime/applied state | `knowledge/16_CURRENT_PROGRAM_STATUS.md` |
| Current V10 progress / next WP | `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` |
| V10 scope/sequence lock | `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md` |
| V10 canonical program | `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` |
| V10 system architecture | `docs/architecture/V10_SYSTEM_ARCHITECTURE.md` |
| Repository ownership/boundaries | `docs/architecture/REPOSITORY_STRUCTURE.md` |
| Active architectural decisions | `docs/architecture/DECISIONS.md` |
| Current V9 system architecture | `docs/architecture/SYSTEM_OVERVIEW.md` |
| GPT setup/recovery entry | `gpt/SETUP_INDEX.md` |
| Applied GPT registry | `gpt/CONFIGURATION.md` |
| Effective GPT Action authority | production `/openapi.json` |
| Completed v9 requirements/audit trail | `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md` |
| Release history | `CHANGELOG.md` |

**Historical-record rule:** closed issues, merged PR descriptions and old comments are implementation evidence from the time they were written. They may intentionally mention an older applied version or an unfinished WP. They do **not** override accepted `main`, current status files, current Program Lock or effective production OpenAPI.

## V10 program — active and sequential

Canonical program: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`.  
Program Lock: `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`.

V10 is the exclusive feature-development program until its final 100% Definition of Done and owner acceptance. Work proceeds one WP at a time through focused branch/PR, exact-head Regression Shield/security and squash merge.

Current V9 production/recovery boundaries remain protected until the responsible later V10 work package explicitly replaces them and passes its Exit Gate.

Do not start Web, Telegram, AI runtime, Lenovo runtime setup or new Real-money authority out of sequence. The exact current/next WP is always read from `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## v9 program — complete and protected

Canonical completed specification: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.

WP0–WP15 repository delivery and owner external acceptance are complete. WP15 repository target was squash-merged as `b9e4fabcb54f8f6e0ba206f030c35f2fafa2ce62` after exact-head Regression Shield #1241; owner acceptance on the existing GPT is recorded in completed issue #216 and epic #176.

The completed V9 master plan is retained as specification/recovery/audit evidence. It is **not** the active V10 task queue.

## Broker contours

### Production read-only

The production read-only broker credential remains read-only. Baseline portfolio-management routing is:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`

Other read-only functions include connection, instrument identity, market snapshot, portfolio market valuation, operations, purchase-capacity preview, broker-report reconciliation and final reviewed decision source.

### Sandbox

Sandbox uses its own credential/host and is always virtual. Sandbox output must never be represented as a real portfolio mutation.

### Real execution

Real execution uses a separate credential and narrow conditional Action surface:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Real BUY/SELL remains exact-owner-confirmed, immutable, idempotent and broker-reconciled. Current v1 remains bounded to reviewed own-funds/own-position LIMIT execution.

Hard prohibitions remain transfer/withdrawal, margin/short, MARKET/BESTPRICE, stop/replace/async, token management through GPT, autonomous recurring real execution and automatic retry after possible-submit ambiguity.

The owner-accepted v8.6.1 real BUY/SELL rollback release remains **100% complete** as protected recovery evidence. Canonical recovery invariant: **idempotent replay verified with no second submit**.

`START V10`, a V10 PR merge, AI output or monitoring alert is never broker-submit authorization.

## Internal V9 engines versus GPT Actions

The repository contains deterministic routing, policy, universe, candidate/research, credit/funds, portfolio risk, strategy, optimizer, immutable plan, safe plan execution, Watchtower and decision journal/evaluation components.

These internal modules are **not automatically GPT Actions**. The Custom GPT may call only operationIds present in the effective imported production OpenAPI and must never claim an internal engine executed without returned evidence.

V10 repository architecture keeps these reviewed domain packages under one deterministic `omni_cio/` Core and reserves future presentation/AI/infrastructure roots without implementing them out of sequence.

## Canonical GPT configuration

Start/recovery: `gpt/SETUP_INDEX.md`  
Registry: `gpt/CONFIGURATION.md`  
Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`  
Knowledge: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`  
Actions: `gpt/ACTIONS_CATALOG.md`  
Secrets/env roles: `gpt/SECRETS_AND_RENDER.md`  
Full Preview/rollback: `gpt/MY_GPT_SETUP_RUNBOOK.md`

Editor policy:

- Actions ON;
- Apps OFF while Actions are used;
- Web Search for public context;
- Data Analysis when supported;
- use a currently available non-Pro model that supports Custom GPT Actions.

GitHub does not hold external secret values or automatically change GPT Editor state. Current GPT assets remain migration/recovery sources until the explicit V10 parity/decommission gate.

## Watchtower

Portfolio Watchtower is read-only background monitoring over signed hidden scheduler routes. Those routes are excluded from GPT OpenAPI. Watchtower may raise material alerts/review triggers but cannot authorize or submit a real order.

Operations: `docs/operations/V9_WATCHTOWER_RUNBOOK.md`.

## Recovery / rollback

`REAL_TRADING_ENABLED=false` remains the master real-money kill switch. `WATCHTOWER_ENABLED=false` disables Watchtower independently.

If a current GPT update is defective, edit the **same** GPT and restore the protected configuration from GitHub; do not create a replacement bot.

V10 recovery architecture: `docs/architecture/V10_RECOVERY_CONTRACT.md`.  
Current GPT recovery: `gpt/MY_GPT_SETUP_RUNBOOK.md`.

## Dependencies

Canonical dependency sources stay at the repository root because CI and Render consume them directly:

- `requirements.in` → runtime direct constraints;
- `requirements.txt` → generated/hash-locked runtime set;
- `requirements-dev.in` → CI/test/security direct constraints;
- `requirements-dev.txt` → generated/hash-locked development set.

Dependabot is configured by `.github/dependabot.yml`. Dependency PRs are proposals only and are merged only after current-main exact-head Regression Shield/security succeeds. Maintenance policy: `docs/operations/DEPENDENCY_MAINTENANCE.md`.

Exact V10 toolchain/frontend/PostgreSQL/package-manager baselines are selected by WP2 after WP1 acceptance; they must not be guessed or implemented earlier.

## Development workflow

Rules: `AGENTS.md`. Contributor checklist: `CONTRIBUTING.md`.

Use branch → focused PR → exact-head Regression Shield/security → zero review threads → squash merge. External owner Preview/`Update` acceptance is additionally required only when a repository change alters the applied Custom GPT configuration or reviewed Action contract.
