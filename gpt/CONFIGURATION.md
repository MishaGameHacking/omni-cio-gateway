# Custom GPT configuration registry — Omni-CIO

> Канонический реестр **целевой** конфигурации единственного поддерживаемого Omni-CIO. Не вставлять этот файл целиком в Instructions.

## Release state

- Repository target config: **v9.0.0**.
- Target UI name: `Omni-CIO API | Управляющий и аналитик v9.0.0`.
- Target Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`.
- Target Knowledge manifest: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`.
- Applied external GPT remains **v8.6.1** until owner Preview acceptance + `Update` are completed and recorded after the WP15 repository merge.
- Protected rollback Instructions remain `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.

Purpose: личный инвестиционный CIO/аналитик T-Invest и строго подтверждаемый исполнитель.  
Primary language: Russian.  
User-facing timezone: `Europe/Moscow` / MSK.

Canonical program:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

WP15 architecture:

`docs/architecture/V9_CUSTOM_GPT_CONFIGURATION_AND_RECOVERY.md`

## Production description — target v9

> Личный инвестиционный CIO в ChatGPT для T-Invest через единый Omni-CIO Gateway. Обновляет факты портфеля, анализирует ликвидность, рынок, риски и альтернативы, сравнивает решения с NO_ACTION и формирует проверяемый план. Реальные сделки возможны только через фактически опубликованные Real Actions и защищённый протокол prepare → точное подтверждение владельца новым сообщением → execute → broker reconciliation.

## Conversation starters — Russian / human language

1. `Управляй портфелем: обнови данные, оцени риски и скажи, что делать сейчас.`
2. `Куда вложить свободные деньги? Сравни варианты с бездействием.`
3. `Что изменилось в портфеле и какие риски требуют внимания?`
4. `Подготовь безопасный план ребалансировки, но ничего не исполняй без моего подтверждения.`

Пользователь не обязан знать operationId. Exact-action запросы остаются поддержанными. Аналитическая команда, план или рекомендация не являются разрешением на real execution.

## Instructions

Canonical target GPT Editor payload:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`

Protected rollback payload:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`

Full engineering/program reference is distributed across the locked master plan and reviewed `docs/architecture/V9_*` contracts; не вставлять эти большие документы целиком в GPT Instructions.

## Knowledge

Canonical source:

`gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`

Production target remains an exact 10-file text-forward reference set under `gpt/knowledge/`. Every file is uploaded once; unlisted legacy duplicates are removed. Behavior and execution safety live in Instructions/server code, not only in Knowledge.

## GPT capabilities

- Actions: **ON**.
- Apps: **OFF** while custom Actions are used.
- Web Search: ON for public context; never a substitute for broker facts.
- Data Analysis: ON when supported for calculations/structured files.
- Image generation: not required for the investment workflow.
- Model: select a currently available **non-Pro model that supports Custom GPT Actions**, then verify in Preview. Do not make recovery depend on a marketing model label.

## Gateway / Actions

Production service: `https://omni-cio-gateway.onrender.com`  
OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`  
Health: `https://omni-cio-gateway.onrender.com/health`  
Entrypoint: `app:app`  
Render plan: Free unless deliberately changed outside this config.

Authentication in GPT Editor:

- type: API Key;
- mode: Bearer;
- value: existing `GATEWAY_API_KEY` from the external server configuration.

No broker/durable-state/background-scheduler credential is entered into GPT Instructions or Knowledge. Secret roles/boundaries are documented in `gpt/SECRETS_AND_RENDER.md`.

### Reviewed baseline read-only flow

For portfolio-management requests:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`.

Other read-only operations are documented in `gpt/ACTIONS_CATALOG.md` and must match effective `/openapi.json`.

### Internal v9 engines versus GPT Actions

WP1–WP14 include deterministic repository/server engines for routing, policy, universe, candidate screening, research, credit, funds, risk, strategy, optimizer, plans, safe execution, Watchtower and decision evaluation.

They are **not automatically GPT Actions**. The GPT may call an operation only if its operationId exists in the effective imported OpenAPI. Otherwise it may use reviewed v9 semantics as reference/advisory discipline but must not claim that the internal engine ran.

### Sandbox

Sandbox operations are present only when the server publishes them. Responses remain explicitly virtual (`sandbox=true`, `real_money=false`). Sandbox never proves a real portfolio mutation.

### Real execution

Real contour remains isolated and conditional. Existing reviewed operationIds are:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

They remain governed by the server readiness/feature flag, separate trading credential, durable state, own-funds/own-position checks, hard caps, fresh market, immutable proposal, exact short-lived owner confirmation in a **new** user turn, idempotency and broker reconciliation.

No configuration change implicitly enables withdrawal/transfer, margin/short, MARKET/BESTPRICE, stop/replace/async, automatic retry or autonomous recurring real execution.

## v8.6.1 protected rollback evidence

Owner-accepted v8.6.1 remains recoverable in GitHub. Its real BUY/SELL v1 Definition of Done remains **100% complete**, including the canonical recovery invariant: **idempotent replay verified with no second submit**.

WP15 does not delete or weaken that evidence.

## Upgrade-in-place / publishing checklist

Repository readiness does not equal applied GPT acceptance.

After the WP15 repository PR is merged, owner-controlled external application is:

1. On **ChatGPT web**, open the existing Omni-CIO GPT and choose Edit/Configure — do **not** Create a new GPT.
2. Change name to `Omni-CIO API | Управляющий и аналитик v9.0.0`.
3. Apply the target description/starters from this file.
4. Replace Instructions fully with `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`.
5. Replace Knowledge with the exact manifest set.
6. Keep Apps OFF; enable Actions and desired supported capabilities.
7. Refresh the existing production Action from `/openapi.json`; authentication remains API Key → Bearer with the existing external `GATEWAY_API_KEY`.
8. Run the Preview acceptance checklist from `gpt/MY_GPT_SETUP_RUNBOOK.md`.
9. Only after Preview passes, select **Update** on the existing GPT.
10. Record acceptance/restoration evidence in GitHub; only then mark applied production GPT v9.0.0.

## GitHub ↔ external systems boundary

GitHub stores canonical code/config/recovery reference. It cannot itself press GPT Editor `Update`, upload Knowledge to the external GPT, or supply external secret values. Applied-state claims therefore require explicit owner acceptance evidence after repository merge.
