# AGENTS.md — Omni-CIO project rules

Этот файл обязателен для любого AI-агента, разработчика или нового чата, который меняет `Misha2304/omni-cio-gateway`.

## 1. Product boundary

Поддерживается один пользовательский продукт:

`Omni-CIO Custom GPT → Omni-CIO Gateway → T-Invest API`

Не создавать второй Custom GPT, второй Gateway, отдельный дублирующий frontend или параллельный execution surface без отдельного явного решения владельца.

## 2. Active program lock

Активная owner-approved программа второго релиза:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

До полного закрытия её Definition of Done:

1. это default product roadmap;
2. новый feature work должен относиться к одному из v9 work packages;
3. исключения — blocking defects, security/dependency maintenance и сохранение стабильного v8.6.1;
4. не начинать конкурирующий roadmap или новый продукт;
5. applied GPT остаётся v8.6.1 до WP15;
6. будущий v9 scope нельзя выдавать за уже реализованный.

Protected migration contract:

`docs/architecture/V9_BASELINE_FREEZE_AND_MIGRATION.md`

## 3. Сначала восстановить контекст

Перед изменением кода/конфигурации:

1. `README.md`;
2. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
3. `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
4. `docs/master-plan/README.md`;
5. пока v9 active — `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`;
6. для GPT — `gpt/SETUP_INDEX.md`, `gpt/CONFIGURATION.md`, `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`, `gpt/ACTIONS_CATALOG.md`;
7. профильный architecture/operations/domain contract;
8. фактический `main`, open PR/issues, current v9 work package и latest GitHub Actions.

Старый чат/screenshot не является источником истины, если расходится с `main`.

## 4. Protected production baseline — Omni-CIO v8.6.1

Стабильный owner-accepted baseline включает три изолированных broker-контура.

### 4.1 Production read-only

- credential: только `TINVEST_TOKEN`;
- он всегда остаётся read-only;
- запрещено повышать его до full-access или использовать как fallback real execution.

### 4.2 Sandbox

- fixed Sandbox host;
- только `TINVEST_SANDBOX_TOKEN`;
- `SANDBOX_TRADING_ENABLED` kill switch;
- `sandbox=true`, `real_money=false`;
- proposal → exact confirmation in new user turn → submit;
- UUID idempotency;
- ambiguous submit не retry;
- margin/transfer/withdraw forbidden.

### 4.3 Real execution v1

Real BUY/SELL разрешён только через `omni_cio.real_trading` и только при valid readiness.

Обязательные инварианты:

- отдельный account-scoped `TINVEST_TRADING_TOKEN` без transfer access;
- `REAL_TRADING_ENABLED=true`;
- durable journal = Upstash Redis over HTTPS REST;
- supported cash share/ETF, RUB;
- LIMIT / CURRENCY / DAY only;
- own-funds BUY / own-position SELL;
- `confirmMarginTrade=false`;
- fresh trusted market/order book;
- exact price step;
- server per-order/daily caps;
- immutable proposal;
- exact short-lived confirmation из нового user turn;
- повторный preflight перед submit;
- UUID idempotency;
- `PostOrder` максимум один раз на proposal/request UUID;
- ambiguous possible-submit → unknown/do-not-resubmit;
- `submitted` != `filled` без broker proof;
- account IDs mask only.

Published real v1 surface:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Protected v8.6.1 path не публикует withdrawal/transfer/securities transfer, MARKET/BESTPRICE, margin/short, futures/options/currency execution, stop orders, ReplaceOrder, PostOrderAsync или autonomous recurring real execution.

`REAL_TRADING_ENABLED=false` — master rollback state.

Owner acceptance 2026-08-03 доказал full lifecycle, включая first real SBER fill, portfolio/operations reconciliation и replay без второго submit.

## 5. Owner authorization boundary

Engineering autonomy не является разрешением на новую конкретную реальную сделку.

Даже после v8.6.1 release каждая реальная операция должна проходить действующий confirmation contract. Будущий v9 может упростить UX через immutable portfolio plan, но не может молча отменить owner-confirmed real-money boundary без отдельного owner-approved architecture/release decision.

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

### Feature flags

Новые v9 engines должны быть additive/shadow-first. Flag обязан иметь safe default, validation, rollback value и tests proving old behavior when disabled. Execution-affecting flag failure = fail closed.

### State/schema migration

- durable state versioned;
- не reinterpret existing real journal destructively;
- schema migration explicit and tested;
- unresolved broker/plan state preserved through rollback;
- broker state reconciled before destructive cleanup.

## 7. Secrets/private data

Никогда не сохранять/публиковать значения:

- `TINVEST_TOKEN`;
- `TINVEST_SANDBOX_TOKEN`;
- `TINVEST_TRADING_TOKEN`;
- `UPSTASH_REDIS_REST_TOKEN`;
- `GATEWAY_API_KEY`;
- Authorization headers;
- полный broker account ID;
- private positions/operations/reports as config data;
- private keys/certificates.

Только env names, placeholders и masked IDs.

## 8. Runtime/deployment

- service: `omni-cio-gateway`;
- endpoint: `https://omni-cio-gateway.onrender.com`;
- Render plan: Free;
- entrypoint: `app:app`;
- deployment contract: `render.yaml`;
- durable real journal: Upstash Redis Free over HTTPS;
- `app_v371.py`, `app_v360.py`, `main.py` остаются dependencies `app.py` до отдельного compatibility refactor.

Conditional execution routes должны отсутствовать, когда соответствующий kill switch выключен.

## 9. Custom GPT configuration

Applied GPT:

`Omni-CIO API | Управляющий и аналитик v8.6.1`

Canonical applied Instructions:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`

Full engineering reference:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`

Production Knowledge: ровно 10 файлов из `gpt/knowledge/`, перечисленных в `gpt/CONFIGURATION.md`.

OpenAPI:

`https://omni-cio-gateway.onrender.com/openapi.json`

Authentication: API Key → Bearer using `GATEWAY_API_KEY` only.

GitHub не синхронизирует GPT Editor автоматически. Applied GPT остаётся v8.6.1 до WP15.

## 10. Portfolio-management routing

Для обычной человеческой команды типа `УПРАВЛЯЙ ПОРТФЕЛЕМ`, `проанализируй портфель`, `куда вложить деньги` пользователь не обязан знать Action names.

Protected v8.6.1 обязательный старт:

1. `getPortfolioSnapshot`;
2. при успехе `getCashLiquiditySnapshot`;
3. `getPortfolioAnalytics`;
4. затем анализ.

Exact-action запрос имеет приоритет, если пользователь явно ограничил Action scope.

## 11. Money/data quality

- exact decimal logic;
- currencies not mixed without verified FX + timestamp;
- no double-count commissions/child operations/embedded trades;
- partial/truncated/incomplete not presented as complete;
- last price is not guaranteed execution price;
- stale/incomplete market blocks exact real proposal;
- `withdraw_limits` is not buying budget;
- technical affordability is not automatic strategy sizing;
- BUY sizing uses own funds, SELL uses own position in protected v8.6.1 path.

## 12. T-Invest broker report

Для async broker report сохранять действующий contract:

- `days=1..31`;
- first call without `task_id`;
- pending may return real `task_id`;
- reuse exact `task_id`;
- T-Invest `30058` = pending;
- other errors not renamed pending;
- ready only when `complete=true`.

## 13. Repository structure

- runtime/wrappers — root + `omni_cio/`;
- Sandbox — `omni_cio/sandbox/`;
- Real execution — `omni_cio/real_trading/`;
- v9 engines — new modules only under agreed v9 architecture/package paths;
- GPT config — `gpt/`;
- engineering memory — `knowledge/`;
- architecture — `docs/architecture/`;
- program — `docs/master-plan/`;
- operations/release — `docs/operations/`;
- tests — `tests/`;
- CI/security — `scripts/`, `.github/`.

Не создавать duplicate setup/audit docs вместо обновления source of truth.

## 14. Tests and Regression Shield

Минимальные проверки:

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

Execution regression обязан сохранять доказательства: wrong/expired confirmation no submit, replay no second submit, ambiguous submit no retry, own-funds/own-position guards, caps fail closed, account ambiguity fail closed, stale market fail closed, secrets/account IDs redacted, durable journal fail closed, conditional OpenAPI correct.

CI tests не обращаются к live T-Invest/Render.

External GitHub Actions pin full commit SHA. Это соответствует GitHub secure-use guidance.

## 15. Git workflow

- separate branch;
- one logical scope per PR;
- dependency locks not hand-edited;
- before merge check head SHA, CI, review threads;
- squash merge only after green exact-head Regression Shield;
- backend/config merge ≠ production acceptance automatically.

## 16. Documentation after significant change

Обновлять только затронутые sources of truth:

- `README.md`;
- `CHANGELOG.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
- `gpt/` when GPT changes;
- relevant architecture/runbook;
- v9 master program/status for work-package progression.

## 17. External boundaries

GitHub не заменяет Render Dashboard для secrets/deploy state, GPT Editor для applied Instructions/Knowledge/model/Bearer/OpenAPI и T-Invest API для live broker state.

Green CI proves repository behavior, not live production state.
