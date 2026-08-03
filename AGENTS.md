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

## 2. Active v9 program lock

Активная owner-approved / program-locked программа:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

До полного закрытия её Definition of Done:

1. это default product roadmap;
2. feature work должен относиться к одному из WP0–WP15, blocking defect, security/dependency maintenance или сохранению стабильного v8.6.1;
3. по умолчанию брать самый ранний незавершённый work package, зависимости которого уже выполнены;
4. не начинать конкурирующий roadmap, duplicate bot/frontend/gateway или параллельный execution surface;
5. applied production GPT остаётся v8.6.1 до WP15;
6. будущий v9 scope нельзя выдавать за уже реализованный без code + tests + CI + required acceptance.

Protected baseline/recovery contract:

`docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md`

Protected v8.6.1 release commit:

`baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`

## 3. Сначала восстановить контекст

Перед изменением кода:

1. `README.md`;
2. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
3. `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
4. `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md` пока v9 active;
5. для GPT — `gpt/SETUP_INDEX.md`, `gpt/CONFIGURATION.md`, `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`, `gpt/ACTIONS_CATALOG.md`;
6. профильный architecture/runbook;
7. `docs/master-plan/README.md` при roadmap-задаче;
8. фактический `main`, открытые PR/issues, current work package и GitHub Actions.

Старый чат или screenshot не является источником истины, если расходится с `main`.

## 4. Broker execution boundary

### 4.1 Production read-only

`TINVEST_TOKEN` всегда остаётся read-only. Его запрещено повышать до full-access, заменять trading token-ом или использовать как fallback внутри real execution.

### 4.2 T-Invest Sandbox

Sandbox writes разрешены только внутри изолированного sandbox contour:

- fixed host `https://sandbox-invest-public-api.tbank.ru/rest`;
- только `TINVEST_SANDBOX_TOKEN`;
- `SANDBOX_TRADING_ENABLED=true`;
- `sandbox=true`, `real_money=false`;
- proposal → отдельное exact confirmation → submit;
- UUID idempotency;
- ambiguous submit не повторяется;
- margin/transfer/withdraw запрещены.

### 4.3 Real execution v1

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

Не публиковать в protected real v1 path: transfer/withdraw/securities transfer, MARKET/BESTPRICE, margin/short, futures/options/currency execution, stop orders, ReplaceOrder, PostOrderAsync, autonomous recurring execution, real cancellation.

`REAL_TRADING_ENABLED=false` — master rollback state: real mutation Actions должны исчезать из OpenAPI.

Owner acceptance 2026-08-03 доказал first real SBER fill, broker/portfolio/operations reconciliation и replay без второго submit. Это не ослабляет safety contract для следующих сделок.

## 5. Owner authorization boundary

Engineering autonomy не является разрешением на конкретную новую реальную сделку.

После v8.6.1 release каждая реальная операция по-прежнему требует действующий preflight/proposal/confirmation contract. Future v9 may simplify UX through an immutable portfolio plan, but it must preserve explicit owner approval before any real-money submit unless a separately owner-approved threat model and release explicitly changes that boundary.

Нельзя интерпретировать `управляй портфелем`, автономную разработку или read-only monitoring как разрешение на broker write.

## 6. v9 delivery discipline

Каждый work package проходит:

1. architecture/data/threat contract;
2. versioned models/interfaces;
3. deterministic implementation;
4. fake-client/unit/contract/integration tests;
5. regression coverage старого behavior при disabled feature flag;
6. security/secret review;
7. documentation/source-of-truth update;
8. exact-head Regression Shield;
9. squash merge;
10. feature-flagged deploy;
11. shadow/Sandbox/minimal-real acceptance, только если пакет этого требует.

Новые v9 engines должны быть additive/shadow-first. Feature flag обязан иметь safe default, validation, rollback value и tests proving old behavior when disabled. Execution-affecting flag failure = fail closed.

Durable state must be versioned. Не reinterpret existing real journal destructively; schema migration должна быть explicit/tested, unresolved broker/plan state сохраняется через rollback, broker state reconciled before destructive cleanup.

## 7. Secrets и приватные данные

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

## 8. Runtime/deployment

- production service: `omni-cio-gateway`;
- endpoint: `https://omni-cio-gateway.onrender.com`;
- Render plan: Free;
- entrypoint: `app:app`;
- deployment contract: `render.yaml`;
- selected durable real journal: external Upstash Redis Free over HTTPS;
- Render Persistent Disk не требуется;
- `app_v371.py`, `app_v360.py`, `main.py` остаются current dependencies `app.py` до отдельного compatibility refactor.

Conditional execution routes должны отсутствовать, когда соответствующий kill switch выключен.

## 9. Custom GPT configuration

Current applied UI/config release:

`Omni-CIO API | Управляющий и аналитик v8.6.1`

Canonical GPT Editor Instructions:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`

Full engineering reference:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`

Production Knowledge: ровно 10 файлов из `gpt/knowledge/`, перечисленных в `gpt/CONFIGURATION.md`.

OpenAPI:

`https://omni-cio-gateway.onrender.com/openapi.json`

Authentication: API Key → Bearer using `GATEWAY_API_KEY` only.

GitHub не синхронизирует GPT Editor автоматически. Applied GPT остаётся v8.6.1 до WP15; после reviewed GPT-visible changes требуется owner apply + Preview + `Update`.

## 10. Portfolio-management routing

Для `УПРАВЛЯЙ ПОРТФЕЛЕМ` обязательный protected v8.6.1 старт:

1. `getPortfolioSnapshot`;
2. при успехе `getCashLiquiditySnapshot`;
3. `getPortfolioAnalytics`;
4. затем анализ.

Portfolio management не является real-trade authorization.

Exact-action запрос имеет приоритет: если пользователь говорит `вызови только X`, другие Actions не вызываются.

WP1 may generalize natural-language routing, but it must preserve exact-action isolation and broker-write authorization boundaries.

## 11. Money/data quality

- exact decimal logic;
- не смешивать валюты без verified FX + timestamp;
- не double-count commissions/child operations/embedded trades;
- `complete=false`, partial или truncated не выдавать как полный результат;
- last price не считать гарантированной ценой сделки;
- stale/incomplete market блокирует real proposal;
- `withdraw_limits` не считать buying budget;
- technical affordability не считать personal sizing;
- BUY sizing только own funds, SELL только own position; margin fields не авторизуют sizing.

## 12. T-Invest broker report

Для `getBrokerReportReconciliation` сохранять async contract:

- `days=1..31`;
- первый вызов без `task_id`;
- `wait_seconds=0` может вернуть `pending` + настоящий `task_id`;
- повторная проверка использует тот же `task_id`;
- T-Invest `30058` = report pending;
- прочие ошибки не переименовывать в pending;
- готовность только при `complete=true`.

## 13. Repository structure

- runtime/wrappers — root + `omni_cio/`;
- Sandbox — `omni_cio/sandbox/`;
- Real execution — `omni_cio/real_trading/`;
- future v9 engines — только agreed package paths внутри существующего product tree;
- GPT config — `gpt/`;
- engineering memory — `knowledge/`;
- architecture — `docs/architecture/`;
- active program — `docs/master-plan/`;
- release runbooks — `docs/operations/`;
- tests — `tests/`;
- CI/security — `scripts/`, `.github/`.

Не создавать duplicate setup/audit docs вместо обновления существующего source of truth.

## 14. Tests and Regression Shield

Минимальные проверки:

```bash
python scripts/check_ci_security_baseline.py
python scripts/check_repository_layout.py
python scripts/check_gpt_recovery_consistency.py
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

## 15. Git workflow

- отдельная branch;
- один логический scope на PR;
- dependency locks вручную не править;
- external Actions pinned full SHA;
- перед merge проверить head SHA, CI, review threads;
- release/package changes merge через squash после зелёного exact-head Regression Shield;
- после backend/config merge выполнить production acceptance затронутых routes, если package gate этого требует.

## 16. Documentation after significant change

Обновлять только затронутые источники истины:

- `README.md`;
- `CHANGELOG.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
- `gpt/` при изменении Custom GPT;
- relevant architecture/runbook;
- v9 program/status при progression work package.

## 17. External boundaries

GitHub не заменяет:

- Render Dashboard для secrets/deploy state;
- GPT Editor для применённых Instructions/Knowledge/model/Bearer/OpenAPI;
- T-Invest API для live broker state.

Green CI не доказывает production state. Для release-visible изменений нужна соответствующая acceptance evidence.