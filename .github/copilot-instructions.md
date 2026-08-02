# GitHub Copilot Instructions — Omni-CIO

Работай только над существующим Omni-CIO Custom GPT и его read-only Gateway.

Перед изменениями прочитай:

1. `AGENTS.md`;
2. `README.md`;
3. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
4. `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
5. профильный domain/architecture file;
6. для GPT-задач — `gpt/SETUP_INDEX.md`, `gpt/CONFIGURATION.md`, `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`, `gpt/ACTIONS_CATALOG.md`;
7. master plan только для roadmap/new-functionality work;
8. фактический `main`, open PR/issues and GitHub Actions.

Обязательные правила:

- strict read-only architecture;
- `trading_methods=false`;
- user-facing Gateway Actions only GET and Bearer-protected;
- no order create/submit/replace/cancel/stop-order;
- no withdrawal/transfer;
- Gateway entrypoint `app:app`;
- production endpoint `https://omni-cio-gateway.onrender.com`;
- account ID masked;
- no T-Invest token, Gateway key values, Authorization headers, full account IDs or private broker payloads in GitHub/logs/docs;
- money stays separated by currency without verified FX;
- no double-count of payments/commissions/child operations/embedded trades;
- unknown failures are not silently converted to `ok`/`pending`;
- no stale-price personalized sizing;
- generated lock files are not hand-edited;
- external GitHub Actions pin full commit SHA.

Custom GPT rules:

- production Instructions only `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`;
- production Knowledge exactly 10 files from `gpt/knowledge/`;
- GitHub is configuration source, not automatic GPT Editor synchronization;
- portfolio management dispatch starts `getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics`;
- user-visible time uses Europe/Moscow/MSK;
- Web Search cannot substitute Gateway broker facts.

Broker report rules:

- `days=1..31`;
- first async call without `task_id`;
- T-Invest `30058` means report pending;
- reuse exact returned `task_id`;
- ready only when `complete=true`.

Required validation:

```bash
python scripts/check_ci_security_baseline.py
python scripts/check_repository_layout.py
python -m ruff check .
python -m ruff format --check scripts tests/test_ci_security_baseline.py
python -m mypy
python -m compileall -q app.py app_v371.py app_v360.py main.py \
  portfolio_market.py portfolio_analytics.py cash_liquidity.py \
  purchase_capacity.py purchase_capacity_integrity.py \
  operations_analytics.py broker_report_reconciliation tests scripts
python -m pytest -q --cov --cov-branch --cov-fail-under=60
```

Каждое изменение делай через отдельную branch + PR. Merge release package только после exact-head Regression Shield. Не создавай дублирующие setup/configuration documents, если можно обновить canonical file.
