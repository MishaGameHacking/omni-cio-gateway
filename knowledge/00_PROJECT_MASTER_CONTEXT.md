# 00 — OMNI-CIO PROJECT MASTER CONTEXT

Дата актуализации: 2026-08-02

Этот файл хранит короткую долговременную память **одного проекта**: личного Custom GPT Omni-CIO и его Gateway для T-Invest.

## 1. Поддерживаемый продукт

Единственный пользовательский интерфейс:

`Omni-CIO API | Управляющий и аналитик v8.4`

Архитектура:

```text
Custom GPT → Omni-CIO Gateway (`app:app`) → T-Invest API
                    │
                    ├→ production T-Invest read-only
                    └→ optional isolated T-Invest Sandbox execution
```

GitHub хранит backend-код и эталон GPT configuration. Render запускает Gateway. GPT Editor хранит фактически применённые Instructions/Knowledge/Bearer configuration и не синхронизируется с GitHub автоматически.

## 2. Current production baseline

- Read-only Instructions baseline: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`.
- Canonical Sandbox-enabled Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt`.
- UI configuration/name remains v8.4 unless changed manually by the owner.
- Recommended model: Thinking 5.6.
- User timezone: Europe/Moscow / MSK.
- Production endpoint: `https://omni-cio-gateway.onrender.com`.
- Entrypoint: `app:app`.
- With Sandbox disabled, user-facing surface remains exactly 14 GET Actions.
- With Sandbox explicitly enabled, 8 isolated Sandbox Actions are added.
- Real production contour remains read-only: `real_trading_methods=false` / existing `trading_methods=false`.

Текущий exact status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

## 3. Что делает Gateway

Production read-only data and analytics:

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

Optional isolated Sandbox execution:

- Sandbox status/account bootstrap/funding;
- Sandbox portfolio;
- BUY/SELL proposal and own-funds/own-position preflight;
- exact short-lived confirmation;
- confirmed submit with duplicate/idempotency protection;
- order-state verification;
- confirmed Sandbox cancellation.

Внутренние market/macro/rating modules помогают quality/risk/decision layers, но сами по себе не дают торговых полномочий.

## 4. Абсолютная safety boundary

### Real production

До отдельного real-money execution release запрещено:

- создание/отправка/замена/отмена real orders;
- stop-order execution;
- withdrawal/transfer;
- autonomous real trading;
- раскрытие полного account ID;
- хранение live tokens/keys в GitHub;
- утверждение stale/partial data как complete/current.

Обязательны:

- real production remains read-only;
- `real_trading_methods=false`;
- masked account;
- fail-closed quality gates;
- exact decimal money logic;
- source/freshness separation.

### Sandbox exception

Virtual writes are allowed only through `omni_cio/sandbox/` and only when:

- `TINVEST_SANDBOX_TOKEN` is used;
- egress is bound to T-Invest Sandbox;
- `SANDBOX_TRADING_ENABLED=true`;
- responses prove `sandbox=true`, `real_money=false`;
- proposal/preflight happens before submit;
- the owner sends a separate exact confirmation phrase;
- broker limits are revalidated immediately before submit;
- duplicate/ambiguous submit protection stays fail-closed;
- withdrawal/transfer and margin automation remain absent.

## 5. GPT behavior

При запросах управления реальным портфелем GPT обязан сначала получить broker facts:

1. `getPortfolioSnapshot`;
2. при успехе `getCashLiquiditySnapshot`;
3. `getPortfolioAnalytics`;
4. затем анализ.

Exact-action запросы имеют приоритет и не должны запускать другие Actions.

Sandbox execution is never inferred from an ordinary request to manage the real portfolio. Sandbox must be explicit and uses the separate two-phase confirmation protocol from Instructions v8.5.0.

Web Search используется для свежего публичного контекста, но не заменяет Gateway для фактов о счёте/деньгах/позициях.

## 6. Market/sizing rules

- last price != гарантированная цена сделки;
- fresh best ask/trading status нужны для точного market-sensitive decision;
- при закрытом рынке/отсутствующем ask/stale price exact sizing не выводится как персональная рекомендация;
- `withdraw_limits` != автоматически buying budget;
- technical affordability != personal sizing;
- Sandbox BUY uses own-funds max-lots; Sandbox SELL uses own-position sell max-lots; margin capacity is not used for automatic sizing.

## 7. Data quality

Для сильных выводов проверять:

- `retrieved_at`/freshness;
- `status`/`complete`;
- pagination truncation;
- component errors;
- instrument identity;
- currency/unit/lot;
- market availability;
- reconciliation state;
- REAL vs SANDBOX contour.

Не double-count top-level payment, nested commissions, child operations или embedded trades.

## 8. Secrets

Render separation:

- `TINVEST_TOKEN` — production read-only;
- `TINVEST_SANDBOX_TOKEN` — Sandbox only;
- `GATEWAY_API_KEY` — GPT → Gateway Bearer secret.

Future real-money trading, if implemented, must use a new separate account-scoped trading token. It must never overwrite or promote `TINVEST_TOKEN` and must not include transfer/withdrawal access.

В GitHub хранить только names/placeholders, но не значения.

## 9. Runtime dependency warning

Текущий `app.py` импортирует `app_v371.py` и `app_v360.py`; wrapper chain использует `main.py`. Эти файлы нельзя удалять как старый мусор до отдельного compatibility refactor с полным тестированием.

## 10. Canonical files

- `README.md` — текущее устройство и использование.
- `AGENTS.md` — обязательные engineering rules.
- `SECURITY.md` — security boundary.
- `gpt/SETUP_INDEX.md` — единая настройка/обновление/восстановление.
- `gpt/CONFIGURATION.md` — exact GPT UI state.
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` — read-only baseline Instructions.
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt` — Sandbox-enabled Instructions.
- `gpt/knowledge/` — production Knowledge set.
- `gpt/ACTIONS_CATALOG.md` — Action catalog.
- `docs/operations/SANDBOX_TRADING_RUNBOOK.md` — Sandbox enable/acceptance.
- `docs/master-plan/` — исходная спецификация развития именно Omni-CIO.
- `docs/architecture/` — действующая архитектура/contracts.
- `docs/operations/` — deploy/release/acceptance procedures.

## 11. Git workflow

Любое значимое изменение:

`branch → PR → exact-head Regression Shield → review → squash merge → production/external acceptance`

Не править `main` напрямую и не считать старую переписку источником истины при расхождении с текущим code/configuration.

## 12. Current readiness

Read-only production baseline is accepted.

Sandbox backend PR #160 and TLS fix PR #162 are merged. Owner Preview on 2026-08-02 demonstrated account bootstrap/funding, portfolio, MARKET BUY/SELL, negative own-position rejection, confirmation expiry, confirmation mismatch rejection, replay protection, LIMIT order state/cancel and portfolio reconciliation while `real_money=false` and `real_trading_methods=false`.

Remaining Sandbox recovery/hardening acceptance is tracked in `knowledge/16_CURRENT_PROGRAM_STATUS.md`; it does not enable real-money execution.

The next engineering program is a **separate real-money execution release**, beginning with threat model/design and default-off server controls. Real broker writes remain disabled until that release passes code review, Regression Shield and owner acceptance.
