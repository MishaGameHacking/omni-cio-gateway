# AGENTS.md — Omni-CIO project rules

Этот файл обязателен для любого AI-агента, разработчика или нового чата, который меняет `Misha2304/omni-cio-gateway`.

## 1. Product boundary

Поддерживается один пользовательский продукт:

`Omni-CIO Custom GPT → read-only Omni-CIO Gateway → T-Invest API`

Не создавать параллельный дубликат Custom GPT, отдельный frontend, publishing transport или broker execution surface без нового явного решения владельца.

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

## 3. Неприкосновенный read-only режим

Запрещено добавлять, публиковать или вызывать:

- создание заявки;
- отправку заявки;
- замену заявки;
- отмену заявки;
- stop-order execution;
- withdrawal/transfer;
- любые другие broker methods, изменяющие счёт.

Обязательные инварианты:

- user-facing Gateway Actions только `GET`;
- `trading_methods=false`;
- stable Render entrypoint `app:app`;
- masked account ID;
- fail-closed при неполных/противоречивых данных.

## 4. Секреты и приватные данные

Никогда не сохранять в GitHub:

- `TINVEST_TOKEN`;
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

## 6. Custom GPT configuration

Единственные production Instructions:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`

Production Knowledge: ровно 10 файлов из `gpt/knowledge/`, перечисленных в `gpt/CONFIGURATION.md`.

GitHub хранит эталон, но не синхронизирует GPT Editor автоматически. После изменения Instructions/Knowledge требуется ручное применение в GPT Editor + Preview + `Update`.

Для Action contract:

- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`;
- Bearer auth через `GATEWAY_API_KEY`;
- operationId должен быть уникальным и стабильным;
- expected surface — exactly 14 GET Actions;
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

## 8. Money/data quality

- Деньги считать exact decimal logic.
- Не смешивать валюты без подтверждённого FX + timestamp.
- Не double-count top-level payment, nested commission, child operation или embedded trade.
- `complete=false`, `status=partial` или `pagination.truncated=true` нельзя выдавать как полный набор данных.
- last price не является гарантированной ценой сделки.
- при отсутствии fresh best ask / market readiness точный sizing решения блокируется.
- `withdraw_limits` не считать автоматически buying budget.

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
  operations_analytics.py broker_report_reconciliation tests scripts
python -m pytest -q --cov --cov-branch --cov-fail-under=60
```

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
- GPT Editor для фактически применённых Instructions/Knowledge/model/Bearer;
- T-Invest API для live broker data.

Green CI не доказывает production state. После релевантных изменений нужна реальная Render/Gateway/GPT acceptance.
