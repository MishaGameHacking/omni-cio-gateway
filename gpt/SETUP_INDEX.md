# Omni-CIO Custom GPT — единая карта настройки и восстановления

> **PROTECTED V9 RECOVERY ONLY — NOT CURRENT V10 AUTHORITY.** This file preserves the accepted Custom GPT v9.0.0 / `app:app` recovery surface. Current V10 implementation authority is the Timeweb + Telegram path defined by Amendments 18–21 and `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

Главная точка входа для **единственного** поддерживаемого Omni-CIO GPT.

## Release state

Repository target: **v9.0.0**  
Applied external GPT: **v9.0.0**, owner-accepted on 2026-08-05  
Target UI: `Omni-CIO API | Управляющий и аналитик v9.0.0`  
Target Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`  
Target Knowledge manifest: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`

Protected rollback UI remains `Omni-CIO API | Управляющий и аналитик v8.6.1`; protected rollback Instructions remain `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.

Canonical program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.

## Architecture

```text
GitHub main ──► Render / Omni-CIO Gateway (`app:app`)
                    │
                    ├─ production read-only broker contour
                    ├─ optional Sandbox contour
                    ├─ confirmed real-execution contour
                    ├─ Upstash durable state
                    └─ hidden QStash/Watchtower scheduler routes

GitHub canonical config ──owner applies/recovers──► EXISTING Omni-CIO GPT v9.0.0
                                                    ├─ v9 Instructions
                                                    ├─ exact v9 Knowledge set
                                                    └─ existing production OpenAPI Action
```

Do not create a second GPT, Gateway, frontend, scheduler or broker stack.

## 1. Applied GPT configuration

- Name: `Omni-CIO API | Управляющий и аналитик v9.0.0`.
- Description/starters/capabilities: `gpt/CONFIGURATION.md`.
- Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`.
- Knowledge: exact manifest `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`.
- Gateway: `https://omni-cio-gateway.onrender.com`.
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`.
- Health: `https://omni-cio-gateway.onrender.com/health`.
- Entrypoint: `app:app`.
- Timezone: `Europe/Moscow` / MSK.
- Actions: ON.
- Apps: OFF while Actions are used.
- Web Search: ON for public context.
- Data Analysis: ON when supported.
- Model: a currently available **non-Pro model that supports Custom GPT Actions**, verified in owner acceptance.

Owner evidence in #216 confirms the **existing** GPT was upgraded in place, not duplicated, and post-Update Action routing worked without a live trade.

## 2. Future update / recovery procedure — never create a duplicate

For any future applied-state change:

1. On ChatGPT **web**, open the existing Omni-CIO GPT.
2. Select Edit/Configure. Do **not** use Create.
3. Apply Name/Description/starters from `gpt/CONFIGURATION.md`.
4. Replace Instructions with the intended canonical payload.
5. Replace Knowledge with the exact manifest set; each file once.
6. Keep Apps OFF and Actions ON.
7. Refresh the existing Action from production `/openapi.json`.
8. Authentication remains API Key → Bearer with the existing external `GATEWAY_API_KEY`.
9. Run Preview acceptance from `gpt/MY_GPT_SETUP_RUNBOOK.md`.
10. Only after Preview passes, select `Update` on the existing GPT.
11. Record owner acceptance/restoration evidence in GitHub.

Repository merge alone never changes the external GPT Editor state.

## 3. Knowledge

Single source of truth: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`.

Production contains exactly 10 text-forward reference files under `gpt/knowledge/`. Knowledge is reference material; behavioral/execution safety belongs in Instructions and server enforcement.

Never upload account-specific/private broker data or authentication material as permanent Knowledge.

## 4. Actions

Static reviewed catalog: `gpt/ACTIONS_CATALOG.md`.  
Runtime authority: effective production `https://omni-cio-gateway.onrender.com/openapi.json`.

The baseline read-only portfolio chain remains:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`.

Internal WP1–WP14 Python engines are **not automatically GPT Actions**. The GPT may call only operationIds present in imported OpenAPI and must not claim an internal engine ran without returned evidence.

Conditional Sandbox/Real operations remain server-controlled. Reviewed Real operationIds are:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

## 5. Authentication / secrets boundary

GPT Action authentication:

- Type: API Key;
- Mode: Bearer;
- Value: existing `GATEWAY_API_KEY` from the external server configuration.

No broker, durable-state or scheduler secret is copied into Instructions or Knowledge. Canonical role/env-name reference: `gpt/SECRETS_AND_RENDER.md`.

## 6. Watchtower

Watchtower routes are hidden from GPT OpenAPI and remain read-only/background infrastructure. Operational configuration is documented in `docs/operations/V9_WATCHTOWER_RUNBOOK.md`.

Watchtower alerts can trigger analysis/review but never authorize a real order.

## 7. Real execution safety

A portfolio-management request, recommendation or plan is not execution authority.

Real execution remains:

`fresh facts → immutable proposal/plan context → exact owner confirmation in a NEW turn → one idempotent submit → broker reconciliation`.

Still forbidden: transfer/withdrawal, margin/short, MARKET/BESTPRICE, stop/replace/async, automatic retry after possible-submit ambiguity, autonomous recurring real execution and token management through GPT.

Master rollback remains `REAL_TRADING_ENABLED=false`.

Protected v8.6.1 recovery invariant remains: **idempotent replay verified with no second submit**.

## 8. Recovery / rollback

Full runbook: `gpt/MY_GPT_SETUP_RUNBOOK.md`.

Protected rollback configuration remains available from GitHub:

- UI `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- stable Gateway `app:app`;
- existing server secret-role separation.

Do not restore from old chat text/screenshots if they disagree with current `main`.

## 9. Sources of truth

- runtime/API: deployed GitHub `main`;
- v9 program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`;
- GPT applied registry: `gpt/CONFIGURATION.md`;
- Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`;
- Knowledge: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`;
- Actions: production `/openapi.json` + `gpt/ACTIONS_CATALOG.md`;
- secrets/env roles: `gpt/SECRETS_AND_RENDER.md`;
- full recovery/Preview: `gpt/MY_GPT_SETUP_RUNBOOK.md`;
- status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.
