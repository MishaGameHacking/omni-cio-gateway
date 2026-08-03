# AGENTS.md — Omni-CIO project rules

Этот файл обязателен для любого AI-агента, разработчика или нового чата, который меняет `Misha2304/omni-cio-gateway`.

## 1. Product boundary

Поддерживается один пользовательский продукт:

`Omni-CIO Custom GPT → Omni-CIO Gateway → T-Invest API`

Три broker-контура изолированы:

1. production read-only через `TINVEST_TOKEN`;
2. optional Sandbox через `TINVEST_SANDBOX_TOKEN`;
3. optional real execution v1 через отдельный `TINVEST_TRADING_TOKEN` + durable journal.

Не создавать второй Custom GPT, отдельный frontend, параллельный execution surface или новый broker gateway без явного решения владельца.

## 2. Сначала восстановить контекст

Перед изменением кода:

1. `README.md`;
2. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
3. `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
4. для GPT — `gpt/SETUP_INDEX.md`, `gpt/CONFIGURATION.md`, `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`, `gpt/ACTIONS_CATALOG.md`;
5. профильный architecture/runbook;
6. `docs/master-plan/README.md` при roadmap-задаче;
7. фактический `main`, открытые PR/issues и GitHub Actions.

Старый чат или screenshot не является источником истины, если расходится с `main`.

## 3. Broker execution boundary

### 3.1 Production read-only

`TINVEST_TOKEN` всегда остаётся read-only. Его запрещено повышать до full-access, заменять trading token-ом или использовать как fallback внутри real execution.

### 3.2 T-Invest Sandbox

Sandbox writes разрешены только внутри изолированного sandbox contour:

- fixed host `https://sandbox-invest-public-api.tbank.ru/rest`;
- только `TINVEST_SANDBOX_TOKEN`;
- `SANDBOX_TRADING_ENABLED=true`;
- `sandbox=true`, `real_money=false`;
- proposal → отдельное exact confirmation → submit;
- UUID idempotency;
- ambiguous submit не повторяется;
- margin/transfer/withdraw запрещены.

### 3.3 Real execution v1

Real BUY/SELL разрешён только через `omni_cio.real_trading` и только когда серверная готовность полностью valid.

Обязательные инварианты:

- отдельный account-scoped `TINVEST_TRADING_TOKEN` без transfer access;
- `REAL_TRADING_ENABLED=true`;
- durable journal = Upstash Redis over HTTPS (selected production path);
- supported cash share/ETF, RUB;
- LIMIT / CURRENCY / DAY only;
- own-funds BUY / own-position SELL;
- `confirmMarginTrade=false`;
- fresh trusted market/order book;
- exact price step;
- small server per-order/daily hard caps;
- immutable proposal;
- exact short-lived confirmation из нового user turn;
- повторный preflight непосредственно перед submit;
- UUID idempotency;
- `PostOrder` максимум один раз на proposal/request UUID;
- ambiguous possible-submit → unknown/do-not-resubmit, только reconciliation;
- `submitted` != `filled` без broker proof;
- account IDs маскируются.

First-release real surface:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Не публиковать в real v1: transfer/withdraw/securities transfer, MARKET/BESTPRICE, margin/short, futures/options/currency execution, stop orders, ReplaceOrder, PostOrderAsync, autonomous recurring execution, real cancellation.

`REAL_TRADING_ENABLED=false` — master rollback state: real mutation Actions должны исчезать из OpenAPI.

## 4. Owner authorization boundary

Engineering autonomy не является разрешением отправить первую реальную заявку.

До первого real submit должен быть пройден `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md` Phase 3 + kill-switch drill.

Первая настоящая заявка требует нового явного сообщения владельца в момент Phase 4. Даже после `prepareRealTrade` submit невозможен без точной server-generated confirmation phrase в новом user turn.

## 5. Secrets и приватные данные

Никогда не сохранять/публиковать значения:

- `TINVEST_TOKEN`;
- `TINVEST_SANDBOX_TOKEN`;
- `TINVEST_TRADING_TOKEN`;
- `UPSTASH_REDIS_REST_TOKEN`;
- `GATEWAY_API_KEY`;
- Authorization headers;
- полный broker account ID;
- private positions/operations/reports как configuration data;
- private keys/certificates.

Только env names, safe placeholders и masked IDs.

## 6. Runtime/deployment

- production service: `omni-cio-gateway`;
- endpoint: `https://omni-cio-gateway.onrender.com`;
- Render plan: Free;
- entrypoint: `app:app`;
- deployment contract: `render.yaml`;
- selected durable real journal: external Upstash Redis Free over HTTPS;
- Render Persistent Disk не требуется;
- `app_v371.py`, `app_v360.py`, `main.py` остаются current dependencies `app.py` до отдельного compatibility refactor.

Conditional execution routes должны отсутствовать, когда соответствующий kill switch выключен.

## 7. Custom GPT configuration

Canonical GPT Editor Instructions:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`

Full engineering reference:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`

Production Knowledge: ровно 10 файлов из `gpt/knowledge/`, перечисленных в `gpt/CONFIGURATION.md`.

OpenAPI:

`https://omni-cio-gateway.onrender.com/openapi.json`

Authentication: API Key → Bearer using `GATEWAY_API_KEY` only.

GitHub не синхронизирует GPT Editor автоматически. После изменения Instructions/Knowledge/OpenAPI требуется owner apply + Preview + `Update`.

## 8. Portfolio-management routing

Для `УПРАВЛЯЙ ПОРТФЕЛЕМ` обязательный старт:

1. `getPortfolioSnapshot`;
2. при успехе `getCashLiquiditySnapshot`;
3. `getPortfolioAnalytics`;
4. затем анализ.

Portfolio management не является real-trade authorization.

Exact-action запрос имеет приоритет: если пользователь говорит `вызови только X`, другие Actions не вызываются.

## 9. Money/data quality

- exact decimal logic;
- не смешивать валюты без verified FX + timestamp;
- не double-count commissions/child operations/embedded trades;
- `complete=false`, partial или truncated не выдавать как полный результат;
- last price не считать гарантированной ценой сделки;
- stale/incomplete market блокирует real proposal;
- `withdraw_limits` не считать buying budget;
- BUY sizing только own funds, SELL только own position; margin fields не авторизуют sizing.

## 10. T-Invest broker report

Для `getBrokerReportReconciliation` сохранять async contract:

- `days=1..31`;
- первый вызов без `task_id`;
- `wait_seconds=0` может вернуть `pending` + настоящий `task_id`;
- повторная проверка использует тот же `task_id`;
- T-Invest `30058` = report pending;
- прочие ошибки не переименовывать в pending;
- готовность только при `complete=true`.

## 11. Repository structure

- runtime/wrappers — root + `omni_cio/`;
- Sandbox — `omni_cio/sandbox/`;
- Real execution — `omni_cio/real_trading/`;
- GPT config — `gpt/`;
- engineering memory — `knowledge/`;
- architecture — `docs/architecture/`;
- release runbooks — `docs/operations/`;
- tests — `tests/`;
- CI/security — `scripts/`, `.github/`.

Не создавать duplicate setup/audit docs вместо обновления существующего source of truth.

## 12. Tests and Regression Shield

Минимальные проверки:

```bash
python scripts/check_ci_security_baseline.py
python scripts/check_repository_layout.py
python -m ruff check .
python -m ruff format --check scripts tests/test_ci_security_baseline.py
python -m mypy
python -m compileall -q app.py app_v371.py app_v360.py main.py \
  portfolio_market.py portfolio_analytics.py cash_liquidity.py \
  purchase_capacity.py purchase_capacity_integrity.py \
  operations_analytics.py broker_report_reconciliation omni_cio tests scripts
python -m pytest -q --cov --cov-branch --cov-fail-under=60
```

Execution regression дополнительно обязан доказывать:

- wrong/expired confirmation не submit-ит;
- replay не создаёт второй `PostOrder`;
- ambiguous submit не retry-ится;
- own-funds/own-position violations блокируются;
- hard caps fail closed;
- account mismatch/ambiguity fail closed;
- stale market fail closed;
- secrets/account IDs redacted;
- durable journal outage/tamper fail closed;
- conditional OpenAPI surface корректен.

CI tests не должны обращаться к live T-Invest/Render.

Merge evidence — полный `.github/workflows/regression-shield.yml` на exact head.

## 13. Git workflow

- отдельная branch;
- один логический scope на PR;
- dependency locks вручную не править;
- external Actions pinned full SHA;
- перед merge проверить head SHA, CI, review threads;
- release changes merge через squash после зелёного exact-head Regression Shield;
- после backend/config merge выполнить production acceptance затронутых routes.

## 14. Documentation after significant change

Обновлять только затронутые источники истины:

- `README.md`;
- `CHANGELOG.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
- `gpt/` при изменении Custom GPT;
- relevant architecture/runbook.

## 15. External boundaries

GitHub не заменяет:

- Render Dashboard для secrets/deploy state;
- GPT Editor для применённых Instructions/Knowledge/model/Bearer/OpenAPI;
- T-Invest API для live broker state.

Green CI не доказывает production state. Для release-visible изменений нужна owner acceptance.