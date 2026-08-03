# Custom GPT configuration registry — Omni-CIO

> Канонический реестр настроек. Не вставлять этот файл целиком в Instructions.

## Identity

- Current UI name: `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- Applied production behavior/config release: **v8.6.1 Compact**.
- Canonical Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Active development program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.
- Purpose: личный инвестиционный аналитик и строго подтверждаемый исполнитель T-Invest, развиваемый в Portfolio Autopilot / Capital Management system.
- Primary language: Russian.
- User timezone: `Europe/Moscow` / MSK.
- Recommended model: `Thinking 5.6`, пока он поддерживает Actions.

## Production description

> Личный инвестиционный GPT для T-Invest через Omni-CIO Gateway. Анализирует портфель, операции, ликвидность, рынок и риски. Реальные торговые действия доступны только через защищённый двухэтапный протокол prepare → точное подтверждение → execute с жёсткими лимитами, без маржи и шортов.

## Conversation starters

1. `УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные, проанализируй портфель и скажи, что делать.`
2. `АНАЛИТИК — объясни состояние портфеля простыми словами.`
3. `НОВОСТИ — проверь важные события по моим компаниям.`
4. `ЖУРНАЛ — покажи решения текущего разговора.`

Пользователь не обязан знать названия Actions. Обычная portfolio-management команда не является разрешением на реальную сделку.

## Production Knowledge — ровно 10 файлов

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

OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`

Health: `https://omni-cio-gateway.onrender.com/health`

Authentication:

- API Key → Bearer;
- value = existing `GATEWAY_API_KEY` из Render;
- никакой T-Invest или Upstash token в GPT Editor не вставляется.

### Production read-only

`TINVEST_TOKEN` остаётся read-only и отдельным от execution credentials.

### Sandbox

`SANDBOX_TRADING_ENABLED=true` добавляет virtual-only Sandbox Actions. Sandbox responses всегда `sandbox=true`, `real_money=false`.

### Real execution v1

Real contour использует отдельный `TINVEST_TRADING_TOKEN`, durable Upstash journal и `REAL_TRADING_ENABLED` kill switch.

При полной readiness доступны только:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Обязательные safety rules:

- BUY/SELL only;
- supported cash share/ETF, RUB;
- LIMIT / CURRENCY / DAY only;
- own funds / own position only;
- no margin/short;
- fresh market + exact price step;
- hard server caps;
- immutable proposal + short-lived exact phrase in a new user turn;
- submit once with UUID idempotency;
- ambiguous possible-submit = no automatic retry;
- broker fill proof required before claiming execution;
- no withdrawal/transfer/token management/stop/replace/async submit/autonomous real trading in protected v8.6.1 execution path.

## Applied production acceptance — COMPLETE

Owner acceptance on 2026-08-03 completed the full v8.6.1 release lifecycle:

- real readiness + durable Upstash integrity;
- wrong and expired confirmation rejection;
- own-funds protection;
- read-only isolation;
- kill-switch rollback and recovery;
- one explicitly authorized real LIMIT BUY SBER;
- broker state reconciled to `EXECUTION_REPORT_STATUS_FILL`;
- real portfolio and operations reconciled;
- exact-confirmation replay produced no second submit.

**Omni-CIO v8.6.1 real BUY/SELL v1 Definition of Done = 100% complete.**

## Active v9 program

Canonical program:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Migration/baseline contract:

`docs/architecture/V9_BASELINE_FREEZE_AND_MIGRATION.md`

Until v9 Definition of Done is complete, this is the default roadmap. Do not create a competing roadmap, duplicate bot, second Gateway or unrelated execution surface. The applied GPT stays v8.6.1 until WP15; intermediate v9 work is additive/feature-flagged and must preserve the proven execution lifecycle.

## Secrets boundary

Never store in GitHub/Knowledge/Instructions/user response values of:

- `TINVEST_TOKEN`;
- `TINVEST_SANDBOX_TOKEN`;
- `TINVEST_TRADING_TOKEN`;
- `UPSTASH_REDIS_REST_TOKEN`;
- `GATEWAY_API_KEY`;
- Authorization headers;
- full broker account ID.

## Publishing / recovery checklist

1. Read `gpt/SETUP_INDEX.md` and current `main`.
2. Apply `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt` fully.
3. Keep exactly the 10 Knowledge files listed above.
4. Import production `/openapi.json`.
5. Authentication = API Key → Bearer with `GATEWAY_API_KEY`.
6. Keep T-Invest/Upstash secrets only in Render.
7. Run Preview/read-only smoke and real readiness if the real contour is enabled.
8. `Update` only after acceptance.

GitHub is canonical source/history but does not automatically apply GPT Editor or Render settings.
