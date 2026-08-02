# 00 — OMNI-CIO PROJECT MASTER CONTEXT

Дата актуализации: 2026-08-02

Этот файл хранит короткую долговременную память **одного проекта**: личного Custom GPT Omni-CIO и его read-only Gateway для T-Invest.

## 1. Поддерживаемый продукт

Единственный пользовательский интерфейс:

`Omni-CIO API | Управляющий и аналитик v8.4`

Архитектура:

```text
Custom GPT → Omni-CIO Gateway (`app:app`) → T-Invest API
                    │
                    └→ market/macro/rating/read-only analytics modules
```

GitHub хранит backend-код и эталон GPT configuration. Render запускает Gateway. GPT Editor хранит фактически применённые Instructions/Knowledge/Bearer configuration и не синхронизируется с GitHub автоматически.

## 2. Current production baseline

- Production Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`.
- UI configuration: v8.4.
- Recommended model: Thinking 5.6.
- User timezone: Europe/Moscow / MSK.
- Gateway API: v3.10.0.
- Production endpoint: `https://omni-cio-gateway.onrender.com`.
- Entrypoint: `app:app`.
- User-facing surface: exactly 14 GET Actions.
- `trading_methods=false`.

Текущий exact status и accepted main commit: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

## 3. Что делает Gateway

Gateway предоставляет read-only данные и расчёты для:

- health / T-Invest connection;
- portfolio snapshot;
- enriched positions/instrument identity;
- instrument search;
- instrument market snapshot;
- portfolio market snapshot;
- portfolio analytics;
- cash/liquidity diagnostics;
- purchase-capacity preview/integrity;
- operations history/analytics/reconciliation;
- official T-Invest broker-report generation/reconciliation;
- final read-only decision review.

Внутренние market/macro/rating modules помогают quality/risk/decision layers, но сами по себе не дают торговых полномочий.

## 4. Абсолютная safety boundary

Текущий проект запрещает:

- создание/отправку/замену/отмену orders;
- stop-order execution;
- withdrawal/transfer;
- autonomous trading;
- раскрытие полного account ID;
- хранение live tokens/keys в GitHub;
- утверждение stale/partial data как complete/current.

Обязательны:

- GET-only Actions;
- `trading_methods=false`;
- masked account;
- fail-closed quality gates;
- exact decimal money logic;
- source/freshness separation.

## 5. GPT behavior

При запросах управления портфелем production GPT обязан сначала получить broker facts:

1. `getPortfolioSnapshot`;
2. при успехе `getCashLiquiditySnapshot`;
3. `getPortfolioAnalytics`;
4. затем анализ.

Exact-action запросы имеют приоритет и не должны запускать другие Actions.

Web Search используется для свежего публичного контекста, но не заменяет Gateway для фактов о счёте/деньгах/позициях.

## 6. Market/sizing rules

- last price != гарантированная цена сделки;
- fresh best ask/trading status нужны для точного market-sensitive decision;
- при закрытом рынке/отсутствующем ask/stale price exact sizing не выводится как персональная рекомендация;
- `withdraw_limits` != автоматически buying budget;
- technical affordability != personal sizing.

## 7. Data quality

Для сильных выводов проверять:

- `retrieved_at`/freshness;
- `status`/`complete`;
- pagination truncation;
- component errors;
- instrument identity;
- currency/unit/lot;
- market availability;
- reconciliation state.

Не double-count top-level payment, nested commissions, child operations или embedded trades.

## 8. Secrets

`TINVEST_TOKEN` находится только в Render Environment.

`GATEWAY_API_KEY` находится в Render и как Bearer secret в GPT Action.

В GitHub хранить только names/placeholders, но не значения.

## 9. Runtime dependency warning

Текущий `app.py` импортирует `app_v371.py` и `app_v360.py`; wrapper chain использует `main.py`. Эти файлы нельзя удалять как старый мусор до отдельного compatibility refactor с полным тестированием.

## 10. Canonical files

- `README.md` — текущее устройство и использование.
- `AGENTS.md` — обязательные engineering rules.
- `SECURITY.md` — security boundary.
- `gpt/SETUP_INDEX.md` — единая настройка/обновление/восстановление.
- `gpt/CONFIGURATION.md` — exact GPT UI state.
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` — production Instructions.
- `gpt/knowledge/` — production Knowledge set.
- `gpt/ACTIONS_CATALOG.md` — 14 Actions.
- `docs/master-plan/` — исходная спецификация развития именно Omni-CIO.
- `docs/architecture/` — действующая архитектура/contracts.
- `docs/operations/` — deploy/release/acceptance procedures.

## 11. Git workflow

Любое значимое изменение:

`branch → PR → exact-head Regression Shield → review → squash merge → production acceptance`

Не править `main` напрямую и не считать старую переписку источником истины при расхождении с текущим code/configuration.

## 12. Definition of current readiness

Рабочий бот считается настроенным, если:

- Gateway health отвечает;
- T-Invest connection отвечает;
- Action surface = 14 GET;
- Bearer auth работает;
- simple natural-language routing вызывает нужные Actions;
- portfolio-management запускает tool-first chain;
- account masked;
- MSK display работает;
- stale-market sizing gate работает;
- `trading_methods=false` сохраняется;
- Preview acceptance пройден.

Любая будущая функция считается существующей только после кода, тестов и acceptance.
