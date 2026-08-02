# Custom GPT configuration registry — Omni-CIO

> Реестр настроек. Не вставлять этот файл целиком в Instructions.

## Identity

- Current UI name until owner manually renames it: `Omni-CIO API | Управляющий и аналитик v8.4`.
- Canonical behavior/config release: **v8.6.0**.
- Purpose: личный инвестиционный аналитик и строго подтверждаемый исполнитель T-Invest.
- Primary language: Russian.
- User timezone: `Europe/Moscow` / MSK.
- Recommended model: `Thinking 5.6`.

## Production description

> Личный GPT для T-Invest. Получает портфель, операции, ликвидность, инструменты и рынок через Omni-CIO Gateway; анализирует структуру и варианты действий. Production read-only credential остаётся отдельным. Sandbox выполняет только виртуальные сделки. Отдельный real execution contour может отправить настоящую BUY/SELL LIMIT-заявку только после готового server-side preflight и точного короткоживущего подтверждения владельца в новом сообщении.

## Conversation starters

1. `УПРАВЛЯЙ ПОРТФЕЛЕМ — сначала вызови getPortfolioSnapshot. Если успешно, вызови getCashLiquiditySnapshot и getPortfolioAnalytics. Затем проанализируй данные и скажи, что делать.`
2. `АНАЛИТИК — объясни состояние портфеля простыми словами.`
3. `НОВОСТИ — проверь важные события по моим компаниям.`
4. `ЖУРНАЛ — покажи решения текущего разговора.`

Обычная portfolio-management команда не является разрешением на реальную сделку. Real proposal требует явного намерения купить/продать/исполнить на настоящем счёте.

## Instructions

Canonical:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`

Historical fallbacks:

- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt` — Sandbox-capable, real production read-only;
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` — read-only fallback.

Не смешивать версии.

## Knowledge — ровно 10 файлов

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
- никакой T-Invest token в GPT Editor не вставляется.

Полный условный surface: `gpt/ACTIONS_CATALOG.md`.

### Baseline read-only

При `REAL_TRADING_ENABLED=false` real Actions отсутствуют.

При `SANDBOX_TRADING_ENABLED=false` остаются 14 baseline GET Actions.

### Sandbox

`SANDBOX_TRADING_ENABLED=true` добавляет 8 virtual-only Sandbox Actions. Sandbox responses: `sandbox=true`, `real_money=false`.

### Real execution

Real contour использует отдельный `TINVEST_TRADING_TOKEN` и никогда не заменяет/не читает read-only token как fallback.

При valid real enable доступны только:

- `getRealTradingStatus` — readiness;
- `prepareRealTrade` — proposal only, no broker submit;
- `executeRealTrade` — consequential submit после exact phrase;
- `getRealOrderState` — reconciliation.

Real v1:

- BUY/SELL only;
- cash share/ETF, RUB;
- LIMIT / CURRENCY / DAY only;
- own funds / own position only;
- margin and short forbidden;
- server hard caps mandatory;
- stale/incomplete market blocks proposal;
- immutable proposal + TTL + exact phrase;
- no same-turn prepare+execute;
- UUID idempotency;
- ambiguous submit = no retry;
- `submitted` != `filled`;
- durable proposal/submission state required.

No real withdrawal, transfer, token management, MARKET/BESTPRICE, stop order, replace, async submit, autonomous execution or real cancellation in the first release.

## Portfolio dispatch acceptance

For `УПРАВЛЯЙ ПОРТФЕЛЕМ`:

1. `getPortfolioSnapshot`;
2. if success → `getCashLiquiditySnapshot`;
3. `getPortfolioAnalytics`;
4. then analysis/market/candidates.

Real execution starts only after a separate explicit real BUY/SELL intent.

## Real confirmation acceptance

Normal real BUY/SELL:

1. fresh broker/market facts;
2. `getRealTradingStatus` ready;
3. `prepareRealTrade`;
4. show `REAL MONEY`, masked account, parameters, preliminary amount/commission, TTL and exact phrase;
5. explicitly say nothing has been submitted;
6. stop;
7. owner sends exact phrase in a new message;
8. only then `executeRealTrade` with original `proposal_id`;
9. immediately `getRealOrderState`;
10. after broker-confirmed fill, read back portfolio/liquidity/operations as needed.

Wrong/expired phrase, account mismatch, stale market, hard-limit violation or insufficient own funds/position must fail closed.

## Secrets boundary

Never store in GitHub/Knowledge/Instructions/user response:

- values of `TINVEST_TOKEN`;
- values of `TINVEST_SANDBOX_TOKEN`;
- values of `TINVEST_TRADING_TOKEN`;
- values of `GATEWAY_API_KEY`;
- Authorization headers;
- full broker account ID;
- private portfolio/operation payloads as configuration.

Details: `gpt/SECRETS_AND_RENDER.md`.

## Publishing checklist

1. All relevant code/config PRs merged after exact-head Regression Shield.
2. Open `gpt/SETUP_INDEX.md`.
3. Apply `CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt` fully.
4. Keep exactly 10 Knowledge files.
5. Keep recommended model/capabilities above.
6. Check deployed `/health`.
7. Re-import production `/openapi.json` whenever conditional Action surface changes.
8. Compare with `gpt/ACTIONS_CATALOG.md`.
9. Run read-only + Sandbox regression smoke.
10. Before first real order, complete Phase 3 of `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md` with no submit.
11. First real order only after a new explicit owner instruction and controlled acceptance.
12. Click `Update` only after Preview acceptance.

## GitHub ↔ GPT Editor boundary

GitHub is the canonical source/history. It does not automatically apply Instructions, Knowledge, model selection, Bearer secret or OpenAPI import inside GPT Editor.