# Архитектура Omni-CIO

## 1. Поддерживаемая система

Репозиторий содержит один пользовательский продукт и один production runtime:

```text
Пользователь в ChatGPT
        ↓
Custom GPT Omni-CIO
        ↓ Bearer GATEWAY_API_KEY
Omni-CIO Gateway (`app:app`) on Render
        ↓ read-only TINVEST_TOKEN
T-Invest API
```

Дополнительные market/macro/rating modules находятся внутри Gateway codebase и остаются read-only.

## 2. GitHub ↔ Render ↔ GPT Editor

GitHub:

- хранит backend code;
- хранит tests/CI;
- хранит эталон GPT configuration/Knowledge;
- не хранит secret values.

Render:

- запускает production Gateway из репозитория согласно deploy-настройке service;
- хранит `TINVEST_TOKEN` и `GATEWAY_API_KEY` как environment secrets.

GPT Editor:

- хранит фактически применённые Instructions/Knowledge/model/capabilities;
- хранит Bearer secret для Action;
- не синхронизируется с GitHub автоматически.

Custom GPT при обычной работе обращается к Render Gateway, а не к GitHub.

## 3. Gateway runtime

- `app.py` — production wrapper, release/OpenAPI surface, entrypoint `app:app`.
- `app_v371.py` — текущая runtime compatibility dependency.
- `app_v360.py` — текущая runtime compatibility dependency.
- `main.py` — base FastAPI/auth/read-only core dependency.
- `portfolio_market.py` — portfolio market snapshot.
- `portfolio_analytics.py` — structure/concentration analytics.
- `cash_liquidity.py` — cash/liquidity diagnostics.
- `purchase_capacity.py` / `purchase_capacity_integrity.py` — read-only technical affordability.
- `operations_analytics.py` — operations/cash-flow analytics.
- `broker_report_reconciliation/` — official T-Invest broker report reconciliation.
- `omni_cio/` — versioned contracts, quality, market, analytics, risk and release modules.

Wrappers/core нельзя удалять только из-за исторического имени: текущий `app.py` импортирует их. Их консолидация — отдельный compatibility refactor.

## 4. Custom GPT configuration

Production configuration lives in `gpt/`:

- `SETUP_INDEX.md` — единственный setup/update entrypoint;
- `CONFIGURATION.md` — exact UI configuration;
- `CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` — production Instructions;
- `knowledge/` — ровно 10 production Knowledge files;
- `ACTIONS_CATALOG.md` — 14 GET Actions;
- `SECRETS_AND_RENDER.md` — secret/deployment boundary.

## 5. Production endpoints

- Base: `https://omni-cio-gateway.onrender.com`
- Health: `/health`
- OpenAPI: `/openapi.json`
- API version: `3.10.0`
- Entrypoint: `app:app`

## 6. Security boundary

- user-facing Actions GET-only;
- `trading_methods=false`;
- no create/submit/replace/cancel/withdraw/transfer methods;
- account IDs masked;
- secrets via environment/GPT secret storage only;
- data-quality failures exposed honestly;
- money uses exact decimal logic;
- currencies stay separate without verified FX.

## 7. Portfolio decision flow

For portfolio-management requests:

```text
getPortfolioSnapshot
        ↓ success
getCashLiquiditySnapshot
        ↓
getPortfolioAnalytics
        ↓
quality/structure/risk analysis
        ↓ if needed
instrument identity + fresh market checks
        ↓
read-only decision / NO_ACTION alternative
```

Web Search can add public context after broker facts, but does not replace broker Actions.

## 8. Market/sizing boundary

- last price is not an executable guarantee;
- fresh best ask/trading status are required for a current market-sensitive sizing decision;
- technical capacity does not automatically equal personal sizing;
- `withdraw_limits` does not automatically equal buying budget.

## 9. Deploy and CI

`render.yaml` is the production deployment contract:

```text
pip install --require-hashes -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port $PORT
```

Regression Shield verifies repository structure, runtime contract, GET-only surface, tests/coverage, dependencies, SAST and secrets.

Green CI does not prove the external Render/GPT state; production acceptance is separate.
