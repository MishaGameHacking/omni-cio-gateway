# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-02

## Current accepted main

Latest accepted repository cleanup:

- PR #147 — `Cleanup: reduce repository to active Omni-CIO bot and Gateway`;
- squash-merged after exact-head Regression Shield run #871 completed successfully;
- current accepted `main` commit: `2032c4d9be66892af25cbaf995f0eb29922436c3`.

Previous product/configuration behavior package:

- PR #146 — tool-first Custom GPT portfolio routing;
- production Instructions release remains `v8.4.1`.

## Production baseline

- Custom GPT: `Omni-CIO API | Управляющий и аналитик v8.4`;
- production Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`;
- recommended model: `Thinking 5.6`;
- user-visible timezone: `Europe/Moscow` / MSK;
- Gateway API: `v3.10.0`;
- production endpoint: `https://omni-cio-gateway.onrender.com`;
- entrypoint: `app:app`;
- exactly 14 GET Actions;
- `trading_methods=false`.

## Accepted repository structure

Repository is now organized around one supported product:

`Omni-CIO Custom GPT → read-only Omni-CIO Gateway → T-Invest API`

Cleanup #147:

- removed obsolete duplicate GPT setup/instructions files;
- removed stale dated audit/inventory artifacts;
- removed unused external-transport-specific active artifacts;
- made `gpt/SETUP_INDEX.md` the single setup/update/recovery entrypoint;
- retained only current configuration/runtime/safety/test/maintenance documentation;
- kept the original Omni-CIO master plan because it directly specifies this same bot;
- kept `app_v371.py`, `app_v360.py` and `main.py` because current `app.py` still imports them.

## GPT files requiring owner-side refresh after cleanup

GitHub does not synchronize Knowledge into GPT Editor automatically.

PR #147 changed two production Knowledge files:

- `gpt/knowledge/05_ANALYST_NEWS_SIMPLE_LANGUAGE.txt`;
- `gpt/knowledge/13_COMMUNICATION_STYLE_2026.txt`.

To make the live Custom GPT match current `main`, replace only those two files in GPT Editor, keeping the total production Knowledge set at exactly 10 files, then run Preview smoke tests and press `Update`.

Production Instructions and Action/OpenAPI contract were not changed by cleanup #147, so no Instructions replacement or OpenAPI re-import is required solely because of this cleanup.

## Previously observed Preview acceptance

Owner Preview tests confirmed:

- broker connection;
- money/balance query;
- current portfolio query;
- 90-day operations query;
- exact single-Action isolation;
- portfolio-management routing;
- masked account display;
- Moscow time display.

Portfolio-management baseline:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`

Fresh-market gate blocks exact personalized lot sizing without market readiness/fresh best ask.

## Secret boundary

GitHub does not store real values of:

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY`;
- Authorization headers;
- full account IDs;
- private broker payloads as configuration.

`TINVEST_TOKEN` remains in Render. `GATEWAY_API_KEY` remains in Render and GPT Action Bearer configuration.

## Supported capability scope

Omni-CIO supports read-only:

- health/T-Invest connection;
- portfolio and enriched positions;
- instrument search;
- market snapshots;
- portfolio analytics;
- cash/liquidity diagnostics;
- purchase-capacity preview;
- operations history/analytics;
- official broker-report reconciliation;
- final decision review;
- relevant public web/news context through GPT Web Search.

No broker write, cancellation, withdrawal or transfer execution is supported.

## Immediate owner acceptance remaining

1. Confirm production Render `/health` after PR #147 deployment.
2. Replace the two changed GPT Knowledge files listed above.
3. Run Preview smoke tests:
   - `Проверь подключение к брокеру.`
   - `Сколько у меня сейчас денег?`
   - `Что у меня сейчас в портфеле?`
   - `Какие операции были за последние 90 дней?`
   - `УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные и скажи, что делать.`
4. Confirm masked account, MSK display and `trading_methods=false`.
5. Press `Update`.

## Next maintenance priority

After owner acceptance, keep repository structure stable. Address actual compatibility/warning debt through separate focused PRs without mixing it into portfolio behavior.
