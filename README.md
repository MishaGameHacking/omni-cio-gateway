# Omni-CIO — Custom GPT + T-Invest Gateway

Omni-CIO — личный инвестиционный аналитик внутри ChatGPT. Единственный пользовательский интерфейс проекта — Custom GPT `Omni-CIO API | Управляющий и аналитик v8.4`.

```text
GitHub main ──> Render: Omni-CIO Gateway (`app:app`)
     │                         │
     │                         ├── TINVEST_TOKEN ──> production T-Invest read-only
     │                         │
     │                         └── optional TINVEST_SANDBOX_TOKEN
     │                                      └──> T-Invest Sandbox only
     │
     └──> эталон GPT configuration
                │
                └── вручную → GPT Editor

Custom GPT Actions ──HTTPS/Bearer──> https://omni-cio-gateway.onrender.com
```

## Текущее production-состояние

- Read-only Instructions baseline: **v8.4.1**.
- Canonical Sandbox-enabled Instructions: **v8.5.0**.
- GPT UI/product name: **v8.4** until manually renamed by the owner.
- Recommended model: **Thinking 5.6**.
- Production entrypoint: **`app:app`**.
- Production Render service: **`omni-cio-gateway`**.
- При выключенном Sandbox user-facing API: **ровно 14 GET Actions**.
- При явном Sandbox enable добавляются **8 Sandbox Actions**; real-money mutation Actions отсутствуют.
- Реальный `TINVEST_TOKEN`: read-only.
- `real_trading_methods=false` для real-money contour.
- Broker account ID показывается только маскированно.
- User-visible timezone: **Москва / Europe/Moscow / MSK**.
- Вывод/перевод денег и ценных бумаг отсутствуют.

Текущий статус: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

## Что умеет бот

Production read-only:

- проверять Gateway и подключение T-Invest;
- получать портфель и позиции;
- обогащать идентификаторы инструментов;
- показывать деньги, блокировки и ликвидность;
- анализировать структуру и концентрацию;
- получать market snapshot инструмента и портфеля;
- находить инструмент;
- проверять technical purchase/sale capacity без создания реальной заявки;
- получать историю и аналитику операций;
- сверять официальный broker report T-Invest;
- выполнять read-only final decision review;
- использовать Web Search для свежих публичных новостей/событий после broker facts;
- сравнивать действие с `NO_ACTION/CASH`.

Optional Sandbox execution release добавляет виртуальный контур:

- отдельный Sandbox token;
- виртуальный Sandbox account;
- виртуальное пополнение;
- Sandbox portfolio/positions;
- BUY/SELL proposal;
- own-funds / own-position max-lots preflight;
- короткоживущее подтверждение конкретной неизменяемой заявки;
- повторный preflight непосредственно перед submit;
- UUID/idempotency protection;
- order-state verification;
- Sandbox cancel с отдельным подтверждением;
- fail-closed при timeout/неопределённом результате.

Sandbox-контур включается только через `SANDBOX_TRADING_ENABLED=true` и не меняет реальный брокерский счёт.

Owner Preview on 2 August 2026 validated the core deployed Sandbox path through GPT → Render → T-Invest Sandbox, including virtual BUY/SELL, confirmation expiry/mismatch, replay protection, LIMIT order state/cancel and portfolio reconciliation. Remaining recovery/hardening checks are tracked in `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

## Что бот по-прежнему не делает

- не торгует реальными деньгами;
- не использует production `OrdersService/PostOrder`;
- не заменяет и не отменяет реальные заявки;
- не выводит и не переводит деньги;
- не автоматизирует margin;
- не обещает доходность;
- не использует stale price как подтверждённую цену реальной покупки;
- не хранит broker tokens в GitHub.

## Как им пользоваться

Пользователь не обязан знать названия Actions.

Примеры production read-only:

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

После отдельного Sandbox enable виртуальная сделка всегда идёт двумя фазами:

`prepareSandboxTrade → показать параметры и причину → пользователь подтверждает exact phrase новым сообщением → executeSandboxTrade → getSandboxOrderState`

Одно сообщение «купи» не является достаточным подтверждением submit.

## Как GitHub связан с ботом

GitHub выполняет две роли:

1. **Backend source** — код Gateway хранится в `main`; Render разворачивает production Gateway из репозитория согласно deploy-настройке.
2. **Configuration source** — GitHub хранит эталон Name/Description/Instructions/Knowledge/Action catalog.

Важно: **GPT Editor не синхронизируется с GitHub автоматически**. Если менялись Instructions, Knowledge или OpenAPI surface, владелец вручную применяет актуальные данные из `main`, выполняет Preview и нажимает `Update`.

Custom GPT в работе обращается **к Render Gateway**, а не к GitHub.

## Настройка и восстановление GPT

Начинать только с:

`gpt/SETUP_INDEX.md`

Ключевые файлы:

- `gpt/CONFIGURATION.md` — Name, Description, starters, model, capabilities;
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` — read-only baseline Instructions;
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt` — Sandbox-enabled Instructions;
- `gpt/knowledge/` — ровно 10 Knowledge-файлов;
- `gpt/ACTIONS_CATALOG.md` — Actions;
- `gpt/SECRETS_AND_RENDER.md` — секреты и Render;
- `gpt/MY_GPT_SETUP_RUNBOOK.md` — полное восстановление;
- `docs/operations/SANDBOX_TRADING_RUNBOOK.md` — включение и acceptance виртуальной торговли.

Production URLs:

- Base: `https://omni-cio-gateway.onrender.com`
- Health: `https://omni-cio-gateway.onrender.com/health`
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`

## Секреты

GitHub хранит только имена переменных/placeholder values.

Никогда не коммитить:

- значение `TINVEST_TOKEN`;
- значение `TINVEST_SANDBOX_TOKEN`;
- будущие full-access/transfer-access broker token values;
- значение `GATEWAY_API_KEY`;
- Authorization headers;
- полный accountId;
- реальные приватные broker payloads как configuration files.

Render separation:

- `TINVEST_TOKEN` — существующий production read-only token, не менять ради Sandbox;
- `TINVEST_SANDBOX_TOKEN` — отдельный Sandbox token;
- `GATEWAY_API_KEY` — Bearer secret между GPT и Gateway.

Future real-money execution, if released, must use a **new separate account-scoped trading token** and a separate default-off kill switch. It must not overwrite the read-only production token and must not include transfer/withdrawal access.

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
omni_cio/sandbox/               optional isolated T-Invest Sandbox execution

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

`branch → PR → Regression Shield → review → squash merge → external acceptance`

## Проверки

Основной merge gate — `.github/workflows/regression-shield.yml`.

Для обычного production состояния он сохраняет:

- repository layout;
- stable `app:app`;
- 14 GET Action contract при выключенном Sandbox;
- `real_trading_methods=false` для real-money contour;
- compile/lint/format/type checks;
- pytest + branch coverage;
- dependency audit;
- SAST;
- secret scan.

Sandbox release дополнительно тестирует confirmation, TTL, idempotency, ambiguous submit, own-funds/own-position limits, masking и отсутствие production write endpoint/token coupling.

Тесты не должны обращаться к реальным T-Invest или production Render endpoints.

## Acceptance

После backend/OpenAPI изменения CI недостаточно. Нужно отдельно проверить deployed Render/GPT behavior.

Sandbox runbook includes:

1. deployed Render commit and health;
2. authentication boundary;
3. read-only production routes;
4. Sandbox status after enable;
5. GPT OpenAPI import;
6. virtual BUY/SELL;
7. order state;
8. duplicate/expiry/tamper negative cases;
9. LIMIT/cancel behavior;
10. kill switch and recovery behavior.

Полный порядок: `docs/operations/SANDBOX_TRADING_RUNBOOK.md`.

## Следующий engineering stage

После core Sandbox acceptance следующий пакет — **отдельный real-money execution release program**.

Он начинается не с включения торгового токена, а с threat model, отдельного account-scoped trading token contract, default-off kill switch, immutable proposal + exact confirmation protocol, hard server-side limits, pre-submit revalidation, idempotency, ambiguous-submit reconciliation, audit trail and rollback design.

До завершения этого отдельного release `real_trading_methods=false` остаётся обязательным инвариантом.

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
