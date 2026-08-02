# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-02

## Current accepted baseline

Последний принятый product/configuration merge:

- PR #146 — `GPT: make portfolio management Action dispatch tool-first`;
- squash-merged в `main`;
- accepted main commit before repository cleanup: `99a57d753f2ab50e16ddc79a36f0f9cfcfe9777a`;
- exact-head Regression Shield run #864: `success`.

Production baseline:

- Custom GPT: `Omni-CIO API | Управляющий и аналитик v8.4`;
- production Instructions: `v8.4.1`;
- recommended model: `Thinking 5.6`;
- user timezone: Moscow / `Europe/Moscow`;
- Gateway: `v3.10.0`;
- production endpoint: `https://omni-cio-gateway.onrender.com`;
- entrypoint: `app:app`;
- exactly 14 GET Actions;
- `trading_methods=false`.

## Owner Preview acceptance already observed

Preview tests confirmed working natural-language routing for:

- broker connection;
- current money/balance;
- current portfolio composition;
- 90-day operations;
- exact single-Action requests;
- portfolio management flow;
- masked account display;
- Moscow time display.

Portfolio-management Instructions require:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`

Market/sizing rules block exact personalized lot sizing when a fresh best ask / market-ready state is unavailable.

## Current repository cleanup package

Active branch:

`cleanup/bot-only-repository`

Purpose:

- keep only files directly required by Omni-CIO configuration, runtime, safety, tests and maintenance;
- consolidate GPT setup into one source of truth;
- remove obsolete setup duplicates and dated audit/inventory clutter;
- remove external publishing/transport-specific artifacts from active project files;
- preserve all runtime dependencies required by `app.py`;
- preserve original Omni-CIO master plan because it is directly related to this bot's development.

Cleanup must merge only after a fresh Regression Shield succeeds on its exact final head.

## Deliberately retained runtime dependencies

The following files are not garbage even though names look historical:

- `app_v371.py`;
- `app_v360.py`;
- `main.py`.

Current `app.py` imports these wrappers/core. Deleting them now would break production. Removing them requires a separate compatibility refactor after this cleanup.

## Secret state

GitHub does not store real values of:

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY`;
- Authorization headers;
- full account IDs.

`TINVEST_TOKEN` stays in Render. `GATEWAY_API_KEY` stays in Render and GPT Action Bearer configuration.

## Current supported capability scope

Omni-CIO supports read-only:

- Gateway health and T-Invest connection;
- portfolio/enriched portfolio;
- instrument search;
- market snapshots;
- portfolio analytics;
- cash/liquidity diagnostics;
- purchase-capacity preview;
- operations history/analytics;
- broker-report reconciliation;
- final decision review;
- relevant public web/news context through GPT Web Search.

No broker write execution is supported.

## Next maintenance priorities after cleanup

1. Merge this cleanup only after green Regression Shield.
2. Verify Render `/health` after merge.
3. Apply only changed GPT Knowledge files to GPT Editor when needed.
4. Run standard Preview smoke tests.
5. Keep repository structure stable; future functionality uses one logical PR at a time.
6. Address genuine runtime compatibility/warning debt separately without mixing it into product behavior.

## Definition of healthy current bot

Healthy state requires:

- production Render health OK;
- T-Invest connection OK;
- exactly 14 GET Actions;
- correct Bearer auth;
- masked account;
- `trading_methods=false`;
- simple-command routing works;
- portfolio-management Action chain works;
- no stale-price personalized sizing;
- Preview tests pass after GPT configuration changes.

Green GitHub CI alone does not prove the external GPT/Render state; external acceptance remains a separate final check after backend/configuration changes.
