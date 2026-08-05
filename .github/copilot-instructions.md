# GitHub Copilot Instructions — Omni-CIO

Работай только над существующим продуктом:

`existing Omni-CIO Custom GPT v9.0.0 → Omni-CIO Gateway (app:app) → T-Invest API`.

Applied GPT v9.0.0 owner-accepted in place on 2026-08-05. WP0–WP15 complete. Repository mode: **controlled maintenance**. Protected rollback: v8.6.1.

## Перед изменениями

Прочитай:

1. `AGENTS.md`;
2. `README.md`;
3. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
4. `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
5. `docs/architecture/SYSTEM_OVERVIEW.md`;
6. `docs/architecture/REPOSITORY_STRUCTURE.md`;
7. профильный domain/architecture/runbook file;
8. для GPT-задач — `gpt/SETUP_INDEX.md`, `gpt/CONFIGURATION.md`, `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`, `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`, `gpt/ACTIONS_CATALOG.md`;
9. `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md` только как completed specification/audit trail или при подготовке новой owner-approved программы;
10. фактический `main`, open PR/issues and latest GitHub Actions.

Закрытые issues, merged PR и старые комментарии — исторические снимки. При конфликте с accepted `main`/`knowledge/16_CURRENT_PROGRAM_STATUS.md` не использовать их как текущую инструкцию.

## Product / runtime rules

- один existing Custom GPT и один production Gateway;
- не создавать duplicate bot, Gateway, frontend, scheduler или parallel broker stack без отдельной owner-approved программы;
- stable entrypoint `app:app`;
- production endpoint `https://omni-cio-gateway.onrender.com`;
- effective production `https://omni-cio-gateway.onrender.com/openapi.json` — runtime GPT Action authority;
- internal v9 module не является GPT Action только потому, что существует в репозитории;
- account IDs user-facing only masked;
- no token/key values, Authorization headers, full account IDs or private broker payloads in GitHub/logs/docs;
- exact decimal logic; no cross-currency aggregation without verified FX + timestamp;
- no double-count of payments/commissions/child operations/embedded trades;
- partial/stale/truncated/contradictory data is not complete/current truth;
- generated lock files are not hand-edited;
- external GitHub Actions pin full commit SHA.

## Broker contour rules

Three contours remain isolated:

1. production read-only — `TINVEST_TOKEN`;
2. optional virtual Sandbox — `TINVEST_SANDBOX_TOKEN`;
3. optional exact-owner-confirmed Real execution — separate `TINVEST_TRADING_TOKEN` + durable state.

Production read-only token is never a Real fallback.

Reviewed Real operationIds:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Real submit remains server-gated:

`readiness/fresh facts → immutable proposal/plan context → exact owner confirmation in a NEW turn → repeat preflight → one idempotent submit → broker reconciliation`.

Preserve:

- own-funds BUY / own-position SELL;
- hard server caps;
- fresh trusted market;
- exact price step;
- ambiguous possible-submit → no automatic retry;
- submitted != filled without broker proof;
- no transfer/withdrawal, margin/short, MARKET/BESTPRICE, stop/replace/async or autonomous recurring real-money execution.

`REAL_TRADING_ENABLED=false` is the master Real kill switch. `WATCHTOWER_ENABLED=false` disables Watchtower independently.

## Custom GPT rules

- applied Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`;
- applied Knowledge: exact 10-file set from `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`;
- protected rollback Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- Actions ON, Apps OFF while custom Actions are used;
- GitHub is canonical configuration/recovery source, not automatic GPT Editor synchronization;
- portfolio management baseline begins `getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics`;
- exact-action requests remain isolated;
- Web Search cannot substitute broker facts;
- future GPT-visible changes require owner Preview + `Update` on the **same** GPT after repository review.

## Broker report rules

For `getBrokerReportReconciliation` preserve:

- `days=1..31`;
- first async call without `task_id`;
- T-Invest `30058` = report pending;
- reuse exact returned `task_id`;
- ready/full only when contract reports completion;
- unrelated errors are not renamed pending.

## Required delivery discipline

Every significant maintenance package:

`branch → focused change → deterministic tests/guards → exact-head Regression Shield/security → zero unresolved review threads → squash merge`.

Do not weaken CI/security or broaden broker/GPT authority to make a change pass.

Use current Regression Shield as the exact command authority. Core checks include repository/security policy, GPT recovery consistency, Ruff, mypy, compile, pytest/coverage, dependency audit, SAST and secret scanning.

Не создавай дублирующие setup/configuration/audit documents, если можно обновить существующий canonical source.
