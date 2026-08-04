# Omni-CIO — Custom GPT + T-Invest Gateway

Omni-CIO is one investment CIO/analyst Custom GPT backed by one production Gateway.

## Release state

Repository target configuration: **`Omni-CIO API | Управляющий и аналитик v9.0.0`**.  
Target Instructions: **`gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`**.  
Target Knowledge: **`gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`**.

Applied external GPT remains **v8.6.1** until the WP15 repository release is merged and the owner upgrades the **existing** GPT through Preview + `Update`.

Protected rollback Instructions remain `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.

```text
GitHub main ──► Render Free / omni-cio-gateway (`app:app`)
                    │
                    ├─ production read-only broker contour
                    ├─ optional virtual Sandbox contour
                    ├─ exact-owner-confirmed Real execution contour
                    ├─ Upstash durable state
                    └─ hidden signed Watchtower/QStash routes

Canonical GitHub GPT config ──owner applies──► EXISTING Omni-CIO GPT
                                               ├─ target v9 Instructions
                                               ├─ exact Knowledge set
                                               └─ production OpenAPI Action
```

Gateway: `https://omni-cio-gateway.onrender.com`  
OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`  
Status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

## v9 program

Canonical roadmap: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.

WP0–WP14 are complete. WP14 Decision Journal / Evaluation & Learning Loop was squash-merged as `507b7f53e3ab924f0d484e348528c23b79ffce9d` after exact-head Regression Shield #1231 on `56488dddb8a07d0da1cc880e15cb2650e2c6f174`, security success, Windows smoke #65 and zero review threads.

WP15 Custom GPT v9 Configuration & Recovery is the final active work package. It upgrades the existing GPT in place and provides canonical Instructions, Knowledge, Actions, recovery/version consistency and owner Preview acceptance.

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

Real BUY/SELL remains exact-owner-confirmed, immutable, idempotent and broker-reconciled. Current v1 remains bounded to reviewed own-funds/own-position LIMIT execution; no implicit authority expansion comes from WP15.

Hard prohibitions remain transfer/withdrawal, margin/short, MARKET/BESTPRICE, stop/replace/async, token management through GPT, autonomous recurring real execution and automatic retry after possible-submit ambiguity.

The owner-accepted v8.6.1 real BUY/SELL release remains **100% complete**. Canonical recovery invariant: **idempotent replay verified with no second submit**.

## Internal v9 engines versus GPT Actions

WP1–WP14 implemented deterministic routing, policy, universe, candidate/research, credit/funds, portfolio risk, strategy, optimizer, immutable plan, safe plan execution, Watchtower and decision journal/evaluation components.

These internal modules are **not automatically GPT Actions**. The Custom GPT may call only operationIds present in the effective imported production OpenAPI and must never claim an internal engine executed without returned evidence.

WP15 therefore changes configuration/recovery semantics without creating a second Gateway or silently broadening broker-write authority.

## Canonical GPT target configuration

Start: `gpt/SETUP_INDEX.md`  
Registry: `gpt/CONFIGURATION.md`  
Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`  
Knowledge: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`  
Actions: `gpt/ACTIONS_CATALOG.md`  
Secrets/env roles: `gpt/SECRETS_AND_RENDER.md`  
Full upgrade/Preview/rollback: `gpt/MY_GPT_SETUP_RUNBOOK.md`

Target editor policy:

- Actions ON;
- Apps OFF while Actions are used;
- Web Search for public context;
- Data Analysis when supported;
- select a currently available non-Pro model that supports Custom GPT Actions and validate it in Preview.

GitHub does not press `Update` in the GPT Editor and does not hold external secret values. Applied v9 status requires owner evidence after repository merge.

## Watchtower

Portfolio Watchtower is read-only background monitoring over signed hidden scheduler routes. Those routes are excluded from GPT OpenAPI. Watchtower may raise material alerts/review triggers but cannot authorize or submit a real order.

Operations: `docs/operations/V9_WATCHTOWER_RUNBOOK.md`.

## Recovery / rollback

`REAL_TRADING_ENABLED=false` remains the master real-money kill switch. `WATCHTOWER_ENABLED=false` disables Watchtower independently.

If a v9 GPT update is defective, edit the **same** GPT and restore the protected v8.6.1 configuration from GitHub; do not create a replacement bot.

Full recovery: `gpt/MY_GPT_SETUP_RUNBOOK.md`.

## Development workflow

Rules: `AGENTS.md`.

Use branch → PR → exact-head Regression Shield/security → zero review threads → squash merge. For WP15, repository merge is followed by owner Preview/Update acceptance on the existing GPT before the v9 program Definition of Done is closed.
