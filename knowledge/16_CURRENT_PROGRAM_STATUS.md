# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-02

## Accepted cleanup baseline

Repository cleanup package:

- PR #147 — `Cleanup: reduce repository to active Omni-CIO bot and Gateway`;
- cleanup squash commit: `2032c4d9be66892af25cbaf995f0eb29922436c3`;
- exact-head Regression Shield run #871 completed successfully;
- PR #148 synchronized this status after the cleanup and also passed a fresh Regression Shield before merge;
- PR #149 removed the self-referential latest-main SHA from this status and passed Regression Shield run #875 before squash merge.

Do not hardcode the ever-changing latest `main` SHA in this status document: merging the document itself changes `main`. For the exact current SHA, read the GitHub `main` ref. The cleanup commit above is stable evidence for the accepted cleanup package.

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
- production Render service: `omni-cio-gateway`;
- entrypoint: `app:app`;
- exactly 14 GET Actions;
- `trading_methods=false`.

## Final Render topology confirmed by owner

On 2026-08-02 the owner removed the obsolete Render resources and disconnected the old Blueprint. The intended production topology is now:

- one active Render Web Service: `omni-cio-gateway`;
- no active Blueprint instance;
- obsolete Telegram service removed;
- obsolete duplicate/alternate Gateway service removed;
- primary service remains connected to `Misha2304/omni-cio-gateway` / `main`;
- owner-provided Render logs show repeated `GET /health` responses with HTTP `200` after the cleanup.

`render.yaml` remains in GitHub as a single-service declarative/recovery contract. It must not be used to create a second production service while the existing `omni-cio-gateway` is healthy.

## Accepted repository structure

Repository is organized around one supported product:

`Omni-CIO Custom GPT → read-only Omni-CIO Gateway → T-Invest API`

Cleanup #147:

- removed obsolete duplicate GPT setup/instructions files;
- removed stale dated audit/inventory artifacts;
- removed unused external-transport-specific active artifacts;
- made `gpt/SETUP_INDEX.md` the single setup/update/recovery entrypoint;
- retained current configuration/runtime/safety/test/maintenance documentation;
- kept the original Omni-CIO master plan because it directly specifies this same bot;
- kept `app_v371.py`, `app_v360.py` and `main.py` because current `app.py` still imports them.

Repository search after Render cleanup shows no active source references to the retired Telegram service name or the old `*-au6d` production endpoint.

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

Render topology cleanup is complete and the primary service remains Live.

Remaining GPT-side acceptance only:

1. Replace the two changed GPT Knowledge files listed above if this has not already been done.
2. Run Preview smoke tests:
   - `Проверь подключение к брокеру.`
   - `Сколько у меня сейчас денег?`
   - `Что у меня сейчас в портфеле?`
   - `Какие операции были за последние 90 дней?`
   - `УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные и скажи, что делать.`
3. Confirm masked account, MSK display and `trading_methods=false`.
4. Press `Update` if GPT Editor still has pending configuration changes.

## Next maintenance priority

Keep repository and Render topology stable: one Custom GPT, one production Gateway service, one canonical endpoint. Address actual compatibility/warning debt through separate focused PRs without mixing it into portfolio behavior.
