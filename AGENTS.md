# AGENTS.md — Omni-CIO project rules

Этот файл обязателен для любого AI-агента, разработчика или нового чата, который меняет `Misha2304/omni-cio-gateway`.

## 1. Product boundary

Поддерживается один пользовательский продукт:

`Omni-CIO Custom GPT → Omni-CIO Gateway → T-Invest API`

Production broker contour остаётся read-only. Отдельно допускается только явно включённый T-Invest Sandbox-контур для виртуальных сделок.

Не создавать параллельный дубликат Custom GPT, отдельный frontend, publishing transport или второй broker execution surface без нового явного решения владельца.

## 2. Сначала восстановить контекст

Перед изменением кода:

1. Прочитать `README.md`.
2. Прочитать `knowledge/00_PROJECT_MASTER_CONTEXT.md`.
3. Прочитать `knowledge/16_CURRENT_PROGRAM_STATUS.md`.
4. Если задача касается GPT — прочитать `gpt/SETUP_INDEX.md`, `gpt/CONFIGURATION.md`, `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` и `gpt/ACTIONS_CATALOG.md`.
5. Прочитать профильный domain/architecture file.
6. Для roadmap свериться с `docs/master-plan/README.md` и master plan.
7. Проверить фактический `main`, открытые PR, issues и GitHub Actions.
8. Не считать старый чат, screenshot или временный PR источником истины, если они расходятся с `main`.

## 3. Broker execution boundary

### 3.1 Real-money production

Без отдельного нового release запрещено добавлять, публиковать или вызывать против реального счёта:

- создание/отправку заявки;
- замену заявки;
- отмену заявки;
- stop-order execution;
- withdrawal/transfer;
- любые другие broker methods, изменяющие реальный счёт.

Обязательные production-инварианты:

- `TINVEST_TOKEN` остаётся read-only;
- `real_trading_methods=false` / существующий `trading_methods=false` сохраняется для реального контура;
- stable Render entrypoint `app:app`;
- masked account ID;
- fail-closed при неполных/противоречивых данных.

### 3.2 Единственное разрешённое исключение: T-Invest Sandbox

Виртуальные broker writes допускаются только внутри `omni_cio/sandbox/` и только при одновременном выполнении всех условий:

- вызовы жёстко направлены на `https://sandbox-invest-public-api.tbank.ru/rest`;
- используется только `TINVEST_SANDBOX_TOKEN`, никогда `TINVEST_TOKEN`;
- `SANDBOX_TRADING_ENABLED=true` выставлен явно;
- ответы явно маркируются `sandbox=true`, `real_money=false`;
- торговая заявка создаётся как proposal, затем требует отдельного явного подтверждения пользователя;
- подтверждение короткоживущее и привязано к неизменяемым параметрам заявки;
- перед submit повторно проверяются broker limits;
- используется UUID idempotency key;
- неоднозначный timeout/5xx после submit никогда не приводит к автоматическому повторному submit;
- margin не подтверждается (`confirmMarginTrade=false`);
- transfer/withdrawal запрещены;
- sandbox stop-orders и автоматическая замена заявок не входят в первый execution release.

Нельзя расширять это исключение на production host, production OrdersService или full-access real token в том же PR.

## 4. Секреты и приватные данные

Никогда не сохранять в GitHub:

- `TINVEST_TOKEN`;
- `TINVEST_SANDBOX_TOKEN`;
- будущие full-access/transfer-access broker token values;
- значение `GATEWAY_API_KEY`;
- Authorization headers;
- полный broker account ID;
- реальные приватные позиции/операции/отчёты как configuration data;
- Render/GPT secrets;
- private keys/credentials.

Допустимы только имена переменных и безопасные placeholders.

## 5. Runtime/deployment

- Production service: `omni-cio-gateway`.
- Production endpoint: `https://omni-cio-gateway.onrender.com`.
- Entrypoint: `app:app`.
- Deployment contract: `render.yaml`.
- `app_v371.py`, `app_v360.py` и `main.py` сейчас являются зависимостями `app.py`; не удалять их как legacy-мусор без отдельного compatibility refactor.
- Root runtime migration выполняется только отдельным PR с полным Regression Shield.
- Sandbox routes должны отсутствовать из OpenAPI, пока `SANDBOX_TRADING_ENABLED` не включён явно.

## 6. Custom GPT configuration

Единственные production Instructions до отдельного GPT execution release:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`

Production Knowledge: ровно 10 файлов из `gpt/knowledge/`, перечисленных в `gpt/CONFIGURATION.md`.

GitHub хранит эталон, но не синхронизирует GPT Editor автоматически. После изменения Instructions/Knowledge/OpenAPI требуется ручное применение в GPT Editor + Preview + `Update`.

Для Action contract:

- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`;
- Bearer auth через `GATEWAY_API_KEY`;
- operationId должен быть уникальным и стабильным;
- при выключенном Sandbox expected surface — exactly 14 GET Actions;
- Sandbox mutation Actions публикуются только при явном Sandbox enable и помечаются consequential;
- schema object responses должны оставаться совместимыми с GPT Actions;
- неизвестные ошибки нельзя маскировать под `ok`/`pending`.

## 7. Portfolio-management routing

Production GPT должен начинать запросы управления портфелем с реальных broker Actions:

1. `getPortfolioSnapshot`;
2. при успехе `getCashLiquiditySnapshot`;
3. `getPortfolioAnalytics`;
4. затем анализ.

Exact-action запрос имеет приоритет: если пользователь говорит `вызови только X`, другие Actions не вызываются.

Web Search не заменяет Gateway для фактов о счёте/портфеле.

Sandbox-сделка не может быть выведена из одного текстового намерения: сначала proposal/preflight, затем отдельное подтверждение, затем submit.

## 8. Money/data quality

- Деньги считать exact decimal logic.
- Не смешивать валюты без подтверждённого FX + timestamp.
- Не double-count top-level payment, nested commission, child operation или embedded trade.
- `complete=false`, `status=partial` или `pagination.truncated=true` нельзя выдавать как полный набор данных.
- last price не является гарантированной ценой сделки.
- при отсутствии fresh best ask / market readiness точный sizing решения блокируется.
- `withdraw_limits` не считать автоматически buying budget.
- Для Sandbox BUY использовать own-funds `GetSandboxMaxLots`; для SELL — own-position `sellMaxLots`; margin fields не использовать для автоматического sizing.

## 9. T-Invest broker report

Для `getBrokerReportReconciliation` сохранять async contract:

- `days=1..31`;
- первый вызов без `task_id`;
- `wait_seconds=0` может вернуть `pending` + настоящий `task_id`;
- повторная проверка использует тот же `task_id`;
- T-Invest `30058` означает report pending;
- прочие ошибки не переименовывать в pending;
- готовность только при `complete=true`.

## 10. Repository structure

- Runtime/wrappers — root + `omni_cio/`.
- Sandbox execution contour — только `omni_cio/sandbox/`.
- GPT configuration — `gpt/`.
- Engineering/domain memory — `knowledge/`.
- Original Omni-CIO specification — `docs/master-plan/`.
- Active architecture — `docs/architecture/`.
- Deploy/release runbooks — `docs/operations/`.
- Tests — `tests/`.
- CI/security scripts — `scripts/`.
- GitHub workflow/governance — `.github/`.

Не создавать новый параллельный setup file, если информация относится к существующему `gpt/SETUP_INDEX.md`.

## 11. Tests and Regression Shield

Минимальные локальные проверки:

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

Для Sandbox release дополнительно обязательны негативные тесты:

- production URL/token не используются;
- flag off не меняет production OpenAPI;
- wrong/expired confirmation не submit-ит заявку;
- duplicate execution не создаёт вторую заявку;
- ambiguous submission не повторяется автоматически;
- own-funds/own-position limit превышение блокируется;
- account IDs маскируются.

Merge evidence — полный `.github/workflows/regression-shield.yml` на exact head.

Тесты не должны обращаться к реальным T-Invest или production Render endpoints.

## 12. Git workflow

- Работать через отдельную branch.
- Один логический scope на PR.
- Не редактировать generated dependency locks вручную.
- External GitHub Actions pin to full SHA.
- Перед merge проверить head SHA, CI и review threads.
- Release changes merge через squash после зелёного exact-head Regression Shield.
- После backend merge выполнить production acceptance затронутых routes.
- Sandbox execution merge не означает автоматическое включение Sandbox в Render: enable — отдельный owner acceptance step.

## 13. Документация после значимого изменения

Обновить только действительно затронутые источники истины:

- `README.md`;
- `CHANGELOG.md`, если изменение release-visible;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md` / `16_CURRENT_PROGRAM_STATUS.md`, если меняется архитектура или текущий статус;
- профильный domain file;
- `gpt/` при изменении Custom GPT;
- relevant architecture/runbook.

Не плодить dated audit/inventory documents для каждой мелкой правки.

## 14. External boundaries

GitHub не заменяет:

- Render Dashboard для secrets/deploy state;
- GPT Editor для фактически применённых Instructions/Knowledge/model/Bearer/OpenAPI;
- T-Invest API для live broker/sandbox data.

Green CI не доказывает production state. После релевантных изменений нужна реальная Render/Gateway/GPT acceptance.
