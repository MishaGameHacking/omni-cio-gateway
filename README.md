# Omni-CIO — Custom GPT + T-Invest Gateway

Omni-CIO is one investment CIO/analyst Custom GPT backed by one production Gateway.

## Release state

Applied and repository-aligned configuration: **`Omni-CIO API | Управляющий и аналитик v9.0.0`**.  
Instructions: **`gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`**.  
Knowledge: **`gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`**.

The **existing** GPT was upgraded in place and owner-accepted on 2026-08-05. Protected rollback Instructions remain `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.

```text
GitHub main ──► Render / omni-cio-gateway (`app:app`)
                    │
                    ├─ production read-only broker contour
                    ├─ optional virtual Sandbox contour
                    ├─ exact-owner-confirmed Real execution contour
                    ├─ Upstash durable state
                    └─ hidden signed Watchtower/QStash routes

Canonical GitHub GPT config ──owner applies/recovers──► EXISTING Omni-CIO GPT v9.0.0
```

Gateway: `https://omni-cio-gateway.onrender.com`  
OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`  
Status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

## v9 program — complete

Canonical roadmap: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.

WP0–WP15 repository delivery and owner external acceptance are complete. WP15 repository target was squash-merged as `b9e4fabcb54f8f6e0ba206f030c35f2fafa2ce62` after exact-head Regression Shield #1241; owner acceptance on the existing GPT is recorded in completed issue #216 and epic #176.

The repository is now in **controlled maintenance mode**: dependency/security updates, compatibility fixes and hygiene changes still require branch → PR → exact-head Regression Shield/security → zero unresolved review threads → squash merge.

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

The owner-accepted v8.6.1 real BUY/SELL rollback release remains **100% complete**. Canonical recovery invariant: **idempotent replay verified with no second submit**.

## Internal v9 engines versus GPT Actions

The repository contains deterministic routing, policy, universe, candidate/research, credit/funds, portfolio risk, strategy, optimizer, immutable plan, safe plan execution, Watchtower and decision journal/evaluation components.

These internal modules are **not automatically GPT Actions**. The Custom GPT may call only operationIds present in the effective imported production OpenAPI and must never claim an internal engine executed without returned evidence.

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

GitHub does not hold external secret values or automatically change GPT Editor state.

## Watchtower

Portfolio Watchtower is read-only background monitoring over signed hidden scheduler routes. Those routes are excluded from GPT OpenAPI. Watchtower may raise material alerts/review triggers but cannot authorize or submit a real order.

Operations: `docs/operations/V9_WATCHTOWER_RUNBOOK.md`.

## Recovery / rollback

`REAL_TRADING_ENABLED=false` remains the master real-money kill switch. `WATCHTOWER_ENABLED=false` disables Watchtower independently.

If a v9 GPT update is defective, edit the **same** GPT and restore the protected v8.6.1 configuration from GitHub; do not create a replacement bot.

Full recovery: `gpt/MY_GPT_SETUP_RUNBOOK.md`.

## Dependencies

Canonical dependency sources stay at the repository root because CI and Render consume them directly:

- `requirements.in` → runtime direct constraints;
- `requirements.txt` → generated/hash-locked runtime set;
- `requirements-dev.in` → CI/test/security direct constraints;
- `requirements-dev.txt` → generated/hash-locked development set.

Dependabot is configured by `.github/dependabot.yml`. Dependency PRs are proposals only and are merged only after current-main exact-head Regression Shield/security succeeds. Maintenance policy: `docs/operations/DEPENDENCY_MAINTENANCE.md` when present on the accepted maintenance baseline.

## Development workflow

Rules: `AGENTS.md`.

Use branch → PR → exact-head Regression Shield/security → zero review threads → squash merge. External owner Preview/Update acceptance is additionally required whenever a repository change alters the applied Custom GPT configuration.
