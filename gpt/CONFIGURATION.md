# Custom GPT configuration registry — Omni-CIO

> Канонический реестр настроек единственного поддерживаемого Omni-CIO. Не вставлять этот файл целиком в Instructions.

## Identity

- Current UI name: `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- Canonical GPT Editor behavior/config release: **v8.6.1 Compact**.
- Canonical Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Purpose: личный инвестиционный аналитик и строго подтверждаемый исполнитель T-Invest.
- Primary language: Russian.
- User timezone: `Europe/Moscow` / MSK.
- Recommended model: `Thinking 5.6`.

Active development program:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Program status: **OWNER-APPROVED / PROGRAM LOCKED**. Stable production baseline v8.6.1 must remain available while v9 is developed.

## Production description

> Личный инвестиционный GPT для T-Invest через Omni-CIO Gateway. Анализирует портфель, операции, ликвидность, рынок и риски. Реальные торговые действия доступны только через защищённый протокол prepare → точное подтверждение → execute с жёсткими серверными ограничениями, без маржи и шортов.

## Conversation starters — current production

1. `УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные и скажи, что делать.`
2. `АНАЛИТИК — объясни состояние портфеля простыми словами.`
3. `НОВОСТИ — проверь важные события по моим компаниям.`
4. `ЖУРНАЛ — покажи решения текущего разговора.`

Пользователь не обязан знать названия Actions для обычного анализа. Exact-action диагностические запросы остаются поддержанными. Обычная portfolio-management команда не является разрешением на реальную сделку.

## Instructions

Canonical GPT Editor payload:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`

Full engineering reference:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`

Historical fallbacks:

- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt` — Sandbox-capable historical release;
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` — read-only historical fallback.

Не смешивать версии и не вставлять полный v8.6.0 поверх compact payload.

## Knowledge — ровно 10 production files

1. `02_GATEWAY_DATA_CONTRACT_V2_OPERATIONS.txt`
2. `04_CIO_PORTFOLIO_MANAGER.txt`
3. `05_ANALYST_NEWS_SIMPLE_LANGUAGE.txt`
4. `06_EVIDENCE_CREDIT_BANKRUPTCY.txt`
5. `07_PERSONAL_STRATEGY.txt`
6. `08_DECISION_JOURNAL_AND_QUALITY_CONTROL.txt`
7. `09_AUTONOMOUS_ACTION_ORCHESTRATOR.txt`
8. `10_DECISION_ENGINE_AND_CANDIDATE_COMPARISON.txt`
9. `11_RISK_DECOMPOSITION_AND_SIZING_GATES.txt`
10. `13_COMMUNICATION_STYLE_2026.txt`

Каждый файл загружать один раз. Secrets, accountId, private broker reports и source code в Knowledge не помещать.

## GPT capabilities

- Web Search: ON.
- Data Analysis / Code Interpreter: ON.
- Image generation: OFF для investment workflow.
- Apps: OFF / не использовать вместе с Actions.
- Actions: ON.

## Gateway / Actions

Production service: `https://omni-cio-gateway.onrender.com`

Render instance: **Free**.

Entrypoint: `app:app`.

OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`

Health: `https://omni-cio-gateway.onrender.com/health`

Authentication:

- API Key → Bearer;
- value = existing `GATEWAY_API_KEY` из Render;
- никакой T-Invest или Upstash token в GPT Editor не вставляется.

### Production read-only

`TINVEST_TOKEN` всегда остаётся read-only. Portfolio-management baseline:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`.

### Sandbox

`SANDBOX_TRADING_ENABLED=true` добавляет только isolated virtual Sandbox Actions. Sandbox responses остаются `sandbox=true`, `real_money=false`.

### Real execution v1

Real contour использует только отдельный `TINVEST_TRADING_TOKEN` и durable Upstash journal.

Conditional real Actions:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Real v1 boundary:

- BUY/SELL only;
- supported cash share/ETF, RUB;
- LIMIT / CURRENCY / DAY only;
- own funds / own position only;
- margin and uncovered short forbidden;
- hard caps mandatory;
- stale/incomplete market blocks proposal;
- immutable proposal + exact short-lived confirmation in a new owner turn;
- UUID idempotency;
- ambiguous possible-submit = no automatic retry;
- `submitted` != `filled` without broker proof;
- durable proposal/submission state required.

No real withdrawal, transfer, token management, MARKET/BESTPRICE, stop order, replace, async submit, autonomous recurring execution or first-release real cancellation.

## Durable state / Render names

Production real journal:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<configured in Render>
UPSTASH_REDIS_REST_TOKEN=<secret configured in Render>
```

Other external config names are documented in `gpt/SECRETS_AND_RENDER.md`. Secret values never belong in GitHub or GPT Knowledge.

## v8.6.1 owner acceptance — COMPLETE

Completed 2026-08-03:

- permanent Upstash Free configured;
- dedicated trading token separated from read-only token;
- saved GPT v8.6.1 + exactly 10 Knowledge files + refreshed production OpenAPI;
- real readiness `status=ready`, `execution_ready=true`, `journal_backend=upstash`, `journal_integrity=ok`;
- expiry and wrong-confirmation rejection;
- own-funds/margin-protection rejection;
- read-only isolation;
- kill-switch rollback and recovery;
- one explicitly authorized real LIMIT BUY SBER accepted and filled;
- broker state reconciled to `EXECUTION_REPORT_STATUS_FILL`, 1/1 lot;
- real portfolio/operations reconciled;
- exact confirmation replay produced no second `executeRealTrade` and no second broker submit.

**Release state: Omni-CIO v8.6.1 real BUY/SELL v1 = 100% complete.**

Release completion does not relax any safety rule for future orders.

## v9 development / migration boundary

Canonical program:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Protected baseline contract:

`docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md`

v9 is implemented incrementally behind explicit compatibility/feature boundaries. Research, analysis, screening, strategy selection, plan creation and monitoring may become autonomous. Unconfirmed real-money writes remain prohibited.

Do not change GPT Editor to v9 until WP15 and its owner Preview acceptance are complete.

## Publishing / recovery checklist

1. Restore UI name exactly: `Omni-CIO API | Управляющий и аналитик v8.6.1` until a later release is accepted.
2. Apply `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt` fully.
3. Keep exactly the 10 Knowledge files above.
4. Recommended model `Thinking 5.6`; Web Search/Data Analysis ON; image generation OFF.
5. Import `https://omni-cio-gateway.onrender.com/openapi.json`.
6. Authentication = API Key → Bearer using existing `GATEWAY_API_KEY`.
7. Verify read-only smoke; verify Sandbox/Real only if those contours are enabled.
8. Keep Render entrypoint `app:app` and current secret-role separation.
9. `Update` GPT only after Preview acceptance of the affected configuration.

## GitHub ↔ external systems boundary

GitHub is canonical for code/config reference, but it does not automatically apply Instructions, Knowledge, model selection, Bearer secret, Render secret values, Upstash state or OpenAPI import inside GPT Editor.
