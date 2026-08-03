# GitHub Copilot Instructions — Omni-CIO

Работай только над существующим Omni-CIO Custom GPT + Omni-CIO Gateway.

## Перед изменениями

Прочитай:

1. `AGENTS.md`;
2. `README.md`;
3. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
4. `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
5. `docs/master-plan/README.md`;
6. пока v9 не завершён — `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`;
7. профильные architecture/operations/domain files;
8. для GPT-задач — `gpt/SETUP_INDEX.md`, `gpt/CONFIGURATION.md`, `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`, `gpt/ACTIONS_CATALOG.md`;
9. фактический `main`, open PR/issues и latest GitHub Actions.

## Program lock

Активный roadmap — `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.

До закрытия его Definition of Done не начинай конкурирующий roadmap, второго бота, второй Gateway, дублирующий frontend или unrelated execution surface. Допустимы v9 work packages, blocking defects, security/dependency maintenance и сохранение стабильного v8.6.1.

Applied GPT остаётся `Omni-CIO API | Управляющий и аналитик v8.6.1` до WP15.

## Protected production baseline

- single product: Custom GPT → Gateway → T-Invest;
- entrypoint `app:app`;
- `TINVEST_TOKEN` остаётся production read-only;
- Sandbox использует только `TINVEST_SANDBOX_TOKEN` и остаётся `real_money=false`;
- real execution использует только отдельный `TINVEST_TRADING_TOKEN` + durable journal;
- real lifecycle: immutable proposal → exact owner confirmation в новом user turn → submit once → broker reconciliation;
- no withdrawal/transfer/securities transfer;
- no margin/short в protected v8.6.1 execution path;
- ambiguous possible-submit never retries automatically;
- `REAL_TRADING_ENABLED=false` = master rollback;
- account IDs masked;
- no secret values/private broker payloads in GitHub/logs/docs.

## v9 delivery discipline

- architecture/data contract before complex runtime code;
- additive/feature-flagged/shadow-first implementation;
- safe default and rollback for each package;
- deterministic tests/fake clients; CI never calls live broker/Render;
- preserve v8.6.1 regression behavior when v9 flag is disabled;
- one logical scope per branch/PR;
- merge only after exact-head Regression Shield;
- production/Preview acceptance is separate from CI.

## Data/finance rules

- exact decimal logic;
- currencies stay separated without verified FX + timestamp;
- no double-count of commissions/child operations/embedded trades;
- partial/truncated/incomplete data is not reported as complete;
- stale last price is not executable market data;
- broker buying capacity is not automatically strategy sizing;
- Web Search is public evidence/context, not a substitute for broker facts.

## GPT configuration

- current applied Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- production Knowledge: exactly 10 files listed in `gpt/CONFIGURATION.md`;
- GitHub is canonical source/history but does not auto-sync GPT Editor/Render;
- portfolio-management routing begins `getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics`;
- user-visible time: Europe/Moscow/MSK.

## Required validation

```bash
python scripts/check_ci_security_baseline.py
python scripts/check_repository_layout.py
python scripts/check_gpt_configuration_consistency.py
python -m ruff check .
python -m mypy
python -m compileall -q app.py app_v371.py app_v360.py main.py \
  portfolio_market.py portfolio_analytics.py cash_liquidity.py \
  purchase_capacity.py purchase_capacity_integrity.py \
  operations_analytics.py broker_report_reconciliation omni_cio tests scripts
python -m pytest -q --cov --cov-branch --cov-fail-under=60
```

External GitHub Actions must remain pinned to full commit SHAs. Не создавай дублирующие setup/configuration docs вместо обновления canonical sources.
