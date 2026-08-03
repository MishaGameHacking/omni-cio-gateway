# Omni-CIO v8.6.1 — setup / recovery runbook

Для обычной настройки сначала читать `gpt/SETUP_INDEX.md`. Этот документ — пошаговый recovery checklist, если текущий Omni-CIO пришлось настраивать заново.

Текущий production baseline остаётся v8.6.1 до завершения и отдельного acceptance программы v9.

## 1. Canonical runtime

- GitHub repo: `Misha2304/omni-cio-gateway`.
- Deploy branch: `main`.
- Render service: `omni-cio-gateway`.
- Render instance: **Free**.
- Entrypoint: `app:app`.
- Base URL: `https://omni-cio-gateway.onrender.com`.
- Health: `https://omni-cio-gateway.onrender.com/health`.
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`.

Один Gateway service. Не создавать duplicate service для Sandbox, real trading или v9.

## 2. Canonical GPT configuration

- UI name: `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- Canonical Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Recommended model: `Thinking 5.6`.
- Timezone: MSK / `Europe/Moscow`.
- Web Search: ON.
- Data Analysis: ON.
- Image generation: OFF for investment workflow.
- Apps: do not combine with Actions.

Do not paste the full v8.6.0 reference on top of the compact Instructions.

## 3. Knowledge — exactly 10

Upload exactly:

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

Never upload secrets, source code, full account IDs or private broker reports as GPT configuration.

## 4. Action authentication

Import:

`https://omni-cio-gateway.onrender.com/openapi.json`

Authentication:

- Type: API Key;
- Mode: Bearer;
- Value: current `GATEWAY_API_KEY` from Render.

Never paste T-Invest or Upstash tokens into GPT Editor.

## 5. Action surface recovery

Use `gpt/ACTIONS_CATALOG.md` as the static reference and production `/openapi.json` as the deployed surface.

Read-only remains available independently of optional execution contours.

Sandbox uses only its dedicated token/host and remains virtual.

Valid real enable exposes only:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

No real cancel/replace/withdraw/transfer/MARKET/margin Actions belong to v8.6.1.

## 6. Render / storage recovery

See `gpt/SECRETS_AND_RENDER.md`.

Preserve role separation:

- `TINVEST_TOKEN` = production read-only;
- `TINVEST_SANDBOX_TOKEN` = Sandbox only;
- `TINVEST_TRADING_TOKEN` = real order execution only, account-scoped and non-transfer;
- `GATEWAY_API_KEY` = GPT → Gateway authentication.

Real execution durable state:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<Upstash HTTPS endpoint>
UPSTASH_REDIS_REST_TOKEN=<secret REST token>
```

The Upstash token stays only in Render Environment.

Risk/cap values must be restored from the accepted Render configuration and canonical documentation. Never infer secret values or production limits from chat history.

## 7. Recovery smoke

### Read-only

1. `/health` or `gatewayHealth`;
2. `getConnection`;
3. portfolio snapshot;
4. cash/liquidity;
5. analytics;
6. operations;
7. normal `УПРАВЛЯЙ ПОРТФЕЛЕМ` routing.

### Sandbox if enabled

- status and virtual portfolio;
- proposal/confirmation separation;
- wrong/expired confirmation rejection;
- replay protection.

### Real if enabled

- `getRealTradingStatus` must be ready and account-masked;
- durable journal must report Upstash/integrity ready;
- do not create a real proposal merely for recovery unless an affected release requires it;
- `REAL_TRADING_ENABLED=false` remains the master rollback state.

The v8.6.1 first-real-order acceptance is already complete and does not need to be repeated during ordinary recovery.

## 8. v8.6.1 accepted release state

Completed 2026-08-03:

- real readiness and durable journal accepted;
- wrong/expired confirmation protections accepted;
- own-funds protection accepted;
- kill-switch rollback/recovery accepted;
- one real SBER LIMIT BUY was explicitly authorized and broker-filled;
- portfolio and operations reconciled;
- exact confirmation replay created no second submit.

**Release state: v8.6.1 = 100% complete.**

## 9. v9 development boundary

Active owner-approved program:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Protected baseline/migration/rollback contract:

`docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md`

Do not configure the live GPT as v9 until WP15 is complete and owner Preview acceptance is performed. Development packages must preserve the v8.6.1 production path until their own exit gates pass.

## 10. Publishing

Click GPT Editor `Update` only when:

- UI name and canonical Instructions match this runbook;
- Knowledge count is exactly 10;
- Action surface matches current flags/readiness;
- Bearer authentication works;
- relevant smoke checks pass.

## 11. GitHub / external-service boundary

A GitHub merge/deploy does not automatically modify GPT Editor, Render Environment or Upstash. Conversely, changing external services does not update GitHub.

Keep GitHub `main` as the canonical reproducible code/config reference, with secret values remaining external.
