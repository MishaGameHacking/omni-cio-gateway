# Omni-CIO — Custom GPT + read-only T-Invest Gateway

Omni-CIO — личный инвестиционный аналитик внутри ChatGPT. Единственный пользовательский интерфейс проекта — Custom GPT `Omni-CIO API | Управляющий и аналитик v8.4`.

```text
GitHub main ──> Render: Omni-CIO Gateway (`app:app`) ──> T-Invest API
     │                         │
     │                         └── read-only broker/market data
     │
     └──> эталон GPT configuration
                │
                └── вручную → GPT Editor

Custom GPT Actions ──HTTPS/Bearer──> https://omni-cio-gateway.onrender.com
```

## Текущее production-состояние

- Production Instructions: **v8.4.1**.
- GPT UI configuration: **v8.4**.
- Recommended model: **Thinking 5.6**.
- Gateway API: **v3.10.0**.
- Production entrypoint: **`app:app`**.
- Production Render service: **`omni-cio-gateway`**.
- User-facing API: **ровно 14 GET Actions**.
- `trading_methods=false`.
- Broker account ID показывается только маскированно.
- User-visible timezone: **Москва / Europe/Moscow / MSK**.
- Создание, отправка, замена и отмена заявок отсутствуют.
- Вывод/перевод денег и ценных бумаг отсутствуют.

Текущий статус: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

## Что умеет бот

- проверять Gateway и подключение T-Invest;
- получать портфель и позиции;
- обогащать идентификаторы инструментов;
- показывать деньги, блокировки и ликвидность;
- анализировать структуру и концентрацию;
- получать market snapshot инструмента и портфеля;
- находить инструмент;
- проверять technical purchase capacity без создания заявки;
- получать историю и аналитику операций;
- сверять официальный broker report T-Invest;
- выполнять read-only final decision review;
- анализировать рыночные/макро/рейтинговые данные, поддерживаемые runtime;
- использовать Web Search для свежих публичных новостей/событий после получения broker facts;
- объяснять результат современным понятным русским языком;
- сравнивать действие с вариантом `NO_ACTION/CASH`.

## Что бот не делает

- не торгует;
- не создаёт и не отправляет заявки;
- не заменяет и не отменяет заявки;
- не выводит деньги;
- не меняет брокерский счёт;
- не обещает доходность;
- не использует stale price как подтверждённую цену покупки;
- не хранит broker tokens в GitHub.

## Как им пользоваться

Пользователь не обязан знать названия Actions.

Примеры:

- `Сколько у меня сейчас денег?`
- `Что у меня сейчас в портфеле?`
- `Проверь подключение к брокеру.`
- `Какие операции были за последние 90 дней?`
- `АНАЛИТИК — объясни состояние портфеля простыми словами.`
- `НОВОСТИ — проверь важные события по моим компаниям.`
- `УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные и скажи, что делать.`

Для режима управления базовый обязательный dispatch:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → анализ`

Если пользователь просит `вызови только <Action>`, вызывается только этот Action.

## Как GitHub связан с ботом

GitHub выполняет две роли:

1. **Backend source** — код Gateway хранится в `main`; Render разворачивает production Gateway из репозитория согласно своей deploy-настройке.
2. **Configuration source** — GitHub хранит эталон Name/Description/Instructions/Knowledge/Action catalog.

Важно: **GPT Editor не синхронизируется с GitHub автоматически**. Если менялись Instructions или Knowledge, владелец вручную применяет актуальные файлы из `main`, выполняет Preview и нажимает `Update`.

Custom GPT в работе обращается **к Render Gateway**, а не к GitHub.

## Настройка и восстановление GPT

Начинать только с:

`gpt/SETUP_INDEX.md`

Ключевые файлы:

- `gpt/CONFIGURATION.md` — Name, Description, starters, model, capabilities;
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` — единственные production Instructions;
- `gpt/knowledge/` — ровно 10 Knowledge-файлов;
- `gpt/ACTIONS_CATALOG.md` — 14 GET Actions;
- `gpt/SECRETS_AND_RENDER.md` — секреты и Render;
- `gpt/MY_GPT_SETUP_RUNBOOK.md` — полное восстановление.

Production URLs:

- Base: `https://omni-cio-gateway.onrender.com`
- Health: `https://omni-cio-gateway.onrender.com/health`
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`

## Секреты

GitHub хранит только имена переменных/placeholder values.

Никогда не коммитить:

- `TINVEST_TOKEN`;
- значение `GATEWAY_API_KEY`;
- Authorization headers;
- полный accountId;
- реальные приватные broker payloads как configuration files.

`TINVEST_TOKEN` находится только в Render. `GATEWAY_API_KEY` находится в Render и как Bearer secret в GPT Action.

## Структура репозитория

```text
app.py                          production Gateway wrapper / entrypoint
app_v371.py                     runtime compatibility dependency
app_v360.py                     runtime compatibility dependency
main.py                         runtime core dependency
portfolio_*.py                  portfolio market/analytics
cash_liquidity.py               cash/liquidity diagnostics
purchase_capacity*.py           read-only purchase capacity
operations_analytics.py         operations analytics
broker_report_reconciliation/   official T-Invest report reconciliation
omni_cio/                       contracts, quality, analytics, market, risk, release

gpt/                            Custom GPT configuration and Knowledge
knowledge/                      engineering/domain memory used by development/runtime
docs/master-plan/               original Omni-CIO development specification
docs/architecture/              active architecture/contracts
docs/operations/                deploy/release/acceptance runbooks

tests/                          regression/contract/security tests
scripts/                        repository/CI/security checks
.github/                        Regression Shield and GitHub governance
render.yaml                     single production Render contract
requirements*.in/.txt           pinned runtime/dev dependencies
```

`app_v371.py`, `app_v360.py` и `main.py` не удаляются как «старые»: текущий `app.py` всё ещё импортирует их. Их удаление возможно только через отдельный compatibility refactor с тестами.

## Разработка

Перед изменениями прочитать:

1. `AGENTS.md`
2. `README.md`
3. `knowledge/00_PROJECT_MASTER_CONTEXT.md`
4. `knowledge/16_CURRENT_PROGRAM_STATUS.md`
5. `gpt/SETUP_INDEX.md`, если задача касается Custom GPT
6. профильный domain file
7. current `main`, open PRs, issues and GitHub Actions

Каждое логическое изменение:

`branch → PR → Regression Shield → review → squash merge → production acceptance`

## Проверки

Основной merge gate — `.github/workflows/regression-shield.yml`.

Он проверяет:

- repository layout;
- stable `app:app`;
- GET-only release contract;
- `trading_methods=false`;
- compile/lint/format/type checks;
- pytest + branch coverage;
- dependency audit;
- SAST;
- secret scan.

Тесты не должны обращаться к реальным T-Invest или production Render endpoints.

## Production acceptance

После backend/OpenAPI изменения CI недостаточно. Нужно отдельно проверить:

1. deployed Render commit;
2. `/health`;
3. authentication boundary;
4. нужный production endpoint;
5. GPT OpenAPI import, если contract менялся;
6. authenticated Preview;
7. полный список Actions;
8. rollback path.

## Master plan

`docs/master-plan/` сохранён намеренно: это исходная спецификация развития **этого же Omni-CIO**, а не посторонний проект. Будущие идеи из master plan не считаются реализованными, пока их нет в коде, тестах и acceptance.

## Главные документы

- `AGENTS.md` — обязательные инженерные правила.
- `SECURITY.md` — финансовая и secret boundary.
- `knowledge/00_PROJECT_MASTER_CONTEXT.md` — долговременный контекст.
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` — фактическое текущее состояние.
- `gpt/SETUP_INDEX.md` — настройка/обновление/восстановление GPT.
- `docs/architecture/REPOSITORY_STRUCTURE.md` — структура и зависимости.
- `docs/operations/DEPLOYMENT_RUNBOOK.md` — Render deployment.
- `docs/operations/RELEASE_CHECKLIST.md` — выпуск и rollback.
