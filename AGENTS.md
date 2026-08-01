# AGENTS.md — обязательные правила Omni-CIO

Этот файл обязателен для любого AI-агента, разработчика или нового чата, работающего с репозиторием.

## 1. Сначала восстановить контекст

Перед изменением кода или GPT-конфигурации:

1. Прочитать `README.md`.
2. Прочитать `docs/README.md`.
3. Прочитать `docs/master-plan/README.md`.
4. Прочитать `docs/master-plan/OMNI_CIO_PORTFOLIO_GPT_RESET_V1.md`.
5. Прочитать `docs/master-plan/OMNI_CIO_FINAL_STEP_BY_STEP_MASTER_PROMPT_RU_V1.md` только в непротиворечащей части.
6. Прочитать `knowledge/00_PROJECT_MASTER_CONTEXT.md` и `knowledge/16_CURRENT_PROGRAM_STATUS.md`.
7. Для Custom GPT прочитать `gpt/INSTRUCTIONS.md`, `gpt/INSTRUCTIONS_COMPACT.md`, `gpt/CONFIGURATION.md` и `gpt/ACTIONS_CATALOG.md`.
8. Проверить current `main`, открытые PR, Issues, review threads и GitHub Actions.
9. Проверить фактический GPT Editor и Preview evidence либо явно отметить, что они доступны только владельцу.
10. Не считать цель реализованной без кода, тестов и acceptance evidence.

## 2. Единственный продукт

Единственный пользовательский продукт — существующий Custom GPT Omni-CIO внутри ChatGPT.

Текущий scope — персональный read-only помощник по управлению инвестиционным портфелем владельца.

Он должен:

- получать портфель через Gateway Actions;
- анализировать структуру, концентрацию, ликвидность и риски;
- проверять свежие новости и корпоративные события;
- учитывать кредитные рейтинги и качество эмитентов;
- искать кандидатов для свободных денег;
- предлагать buy/sell/reduce/increase/hold/wait/do-nothing;
- рассчитывать доступный объём и влияние на диверсификацию;
- работать только по командам пользователя.

Без отдельного нового решения владельца запрещено:

- создавать сайт, web-кабинет или мобильное приложение;
- создавать отдельный чат-интерфейс или дубликат GPT;
- создавать собственную AI-модель или reasoning server;
- добавлять Telegram, Telegram API, публикации или drafts;
- развивать публичный многопользовательский продукт;
- начинать autonomous trading или broker-write work.

Gateway — минимальный защищённый data layer для GPT Actions, а не пользовательский продукт.

## 3. Неприкосновенный read-only режим

Обязательные инварианты:

- `trading_methods=false`;
- все пользовательские Gateway Actions — GET-only;
- `app:app` — стабильный entrypoint;
- отсутствуют order create, replace, cancel, stop-order, transfer и withdrawal;
- отсутствуют скрытые тестовые торговые вызовы;
- account ID маскируется;
- неизвестные или неполные данные fail closed;
- Telegram runtime и Telegram scope полностью отсутствуют.

Shadow, Paper, broker-authoritative Preview и Confirm-before-trade не входят в текущий roadmap. Они могут рассматриваться только после отдельного owner decision и отдельной admission program.

## 4. Секреты и приватные данные

Никогда не сохранять в GitHub, Instructions, Knowledge, тестах, логах или ответах:

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY`;
- полный номер счёта;
- реальные операции, позиции и брокерские отчёты;
- Authorization headers;
- Render или GPT Editor secrets.

Допустимы только имена переменных и безопасные placeholders. Когда требуется секрет, дать владельцу короткую UI-инструкцию и не просить само значение.

## 5. Разделение ответственности

### Custom GPT

- понимает команду;
- выбирает минимально необходимый Action;
- применяет обязательный аналитический workflow;
- использует Web Search для свежих публичных фактов;
- сравнивает альтернативы;
- объясняет выводы и ограничения.

### Gateway

- авторизуется в T-Invest;
- получает и нормализует приватные данные;
- выполняет точные денежные расчёты;
- проверяет freshness, completeness, identity, currency и pagination;
- маскирует account ID;
- блокирует неизвестные и write methods.

### GitHub

- хранит канонические Instructions, Knowledge templates, OpenAPI, Gateway, тесты и документацию;
- не обновляет GPT Editor автоматически;
- не хранит секреты.

## 6. GPT Instructions, Knowledge и Actions

- Критический workflow, routing, priorities и stop conditions находятся в Instructions.
- Knowledge используется только для личной политики и справочных методик.
- Project roadmap, CI runbooks, Telegram history и внутренние release-документы не загружаются в GPT Knowledge.
- Один Action имеет одно строгое назначение.
- Generic broker forwarding через `method/name/payload` запрещён.
- GPT использует Actions, а не Apps, пока официальная платформа не изменилась.
- Не создавать новый GPT вместо обновления существующего.

Для каждого Action обязательны:

- стабильный уникальный `operationId`;
- Bearer auth;
- явная schema;
- `status`, `version`, `retrieved_at`, masked account, `quality`, `complete`, `component_errors`, `warnings`, где применимо;
- typed failure states;
- отсутствие execution, withdrawal, transfer и token-management.

## 7. Аналитический стандарт

Каждая персональная рекомендация должна:

1. Получить актуальные приватные данные.
2. Проверить качество и полноту.
3. Разделить валюты.
4. Оценить структуру, концентрацию, ликвидность и риск.
5. Проверить релевантные свежие новости и рейтинги.
6. Сравнить минимум три варианта: ничего не делать, ограниченное изменение, более существенное изменение.
7. Применить личную политику владельца.
8. Рассчитать лоты, сумму, комиссию, остаток и структуру после изменения.
9. Указать условия отмены рекомендации, дату и источники.

Если личная политика не заполнена, допустимы диагностика и сценарии, но точные персональные sizing-нормативы не выдаются.

## 8. Деньги и качество данных

- Использовать `Decimal` или безопасную эквивалентную логику.
- Не складывать валюты без подтверждённого FX и timestamp.
- Не путать штуки, позиции и лоты.
- Для облигаций учитывать процент от номинала и НКД.
- Не двойно учитывать payment, комиссии, child operations и embedded trades.
- Не объявлять данные полными при `complete=false`, `status=partial`, stale/inconsistent state или `pagination.truncated=true`.
- Проверять UID, lot, currency, quote, trading status, pagination и account scope.
- Недостаточные данные приводят к abstain/missing-data.
- Одна новость, rating или technical pattern не является достаточным сигналом.

## 9. Структура репозитория

- Custom GPT — `gpt/`.
- Product scope — `docs/master-plan/`.
- Gateway runtime — корень и `omni_cio/`.
- Доменные правила — `knowledge/`.
- Tests — `tests/`.
- Checks — `scripts/`.
- Architecture, audits и runbooks — `docs/`.
- CI — `.github/`.

Каждый активный runtime-файл должен иметь consumer/test или явный статус compatibility/deprecated.
Dependency locks нельзя редактировать вручную. GitHub Actions закрепляются полным commit SHA.

## 10. Тестирование

Минимум:

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

По затронутому scope обязательны contract, failure, security и end-to-end tests.
Custom GPT изменения требуют Preview matrix из `gpt/PORTFOLIO_GPT_ACCEPTANCE_V1.md`.
Тесты не обращаются к реальным T-Invest или Render endpoints.

## 11. Git workflow

- Отдельная ветка от свежего `main`.
- Один логический scope — один PR.
- Draft PR до завершения проверок.
- В PR фиксировать exact base/head, contracts, risks, tests и rollback.
- Не merge при red, conflict, unresolved review или queued без evidence.
- Для релизов использовать squash merge.
- Старый green check не является доказательством после изменения head или `main`.

## 12. Обновление памяти

После значимого изменения обновить затронутые:

- `README.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
- `gpt/`;
- `docs/master-plan/README.md`;
- issue #27;
- inventory и runbooks, если изменился их scope.

## 13. Внешние owner-only действия

Пользователь выполняет только то, что нельзя безопасно выполнить инструментами:

- создаёт/отзывает брокерский токен;
- вводит секреты в Render и GPT Actions;
- вставляет проверенные Instructions в существующий GPT;
- загружает выбранные Knowledge-файлы;
- импортирует OpenAPI;
- запускает Preview-сценарии;
- нажимает Update после acceptance.

Не перекладывать на пользователя код, архитектуру, тесты, OpenAPI или анализ GitHub.

## 14. Формат отчёта

1. Что найдено.
2. Что изменено.
3. Что проверено.
4. Что осталось.
5. Риски.
6. GitHub: branch/base/head/PR/CI/artifact/review/merge decision.
7. GPT Editor: sync/schema/Knowledge/Preview state.
8. Одно необходимое owner-only действие.
9. Следующий один логический этап.
