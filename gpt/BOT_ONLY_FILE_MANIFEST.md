# Omni-CIO bot-only manifest

Этот manifest определяет **единственный** поддерживаемый Omni-CIO Custom GPT и связанные production/recovery assets.

## 1. Единственный продукт

`Omni-CIO Custom GPT → Omni-CIO Gateway → T-Invest API`

Applied and repository-aligned UI:

`Omni-CIO API | Управляющий и аналитик v9.0.0`

The existing GPT was owner-updated in place and accepted on 2026-08-05. Do not create a second Custom GPT, duplicate frontend, second Gateway, competing scheduler or parallel broker/execution stack.

Protected rollback UI remains `Omni-CIO API | Управляющий и аналитик v8.6.1`.

## 2. Главная точка восстановления

`gpt/SETUP_INDEX.md`

Canonical applied/recovery registry:

- config: `gpt/CONFIGURATION.md`;
- Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`;
- Knowledge manifest: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`;
- Actions: `gpt/ACTIONS_CATALOG.md`;
- secrets/env roles: `gpt/SECRETS_AND_RENDER.md`;
- full runbook: `gpt/MY_GPT_SETUP_RUNBOOK.md`;
- Gateway: `https://omni-cio-gateway.onrender.com`;
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`;
- Health: `https://omni-cio-gateway.onrender.com/health`;
- Entrypoint: `app:app`.

Protected rollback payload remains `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.

## 3. Canonical program

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

WP0–WP15 and owner external acceptance are complete. Tracking issue #216 and epic #176 are closed completed.

WP15 configuration/recovery contracts remain:

- `docs/architecture/V9_CUSTOM_GPT_CONFIGURATION_AND_RECOVERY.md`;
- `docs/architecture/V9_CUSTOM_GPT_CONFIGURATION_THREAT_MODEL.md`.

## 4. Production/recovery GPT files

| File | Purpose |
|---|---|
| `gpt/SETUP_INDEX.md` | Single setup/recovery entrypoint |
| `gpt/CONFIGURATION.md` | Applied identity, description, starters, capabilities |
| `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt` | Canonical applied v9 Instructions |
| `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md` | Exact Knowledge upload registry |
| `gpt/ACTIONS_CATALOG.md` | Reviewed effective Action policy |
| `gpt/SECRETS_AND_RENDER.md` | External secrets/environment boundary |
| `gpt/MY_GPT_SETUP_RUNBOOK.md` | Preview, recovery and rollback |
| `gpt/knowledge/` | Exact manifest-listed reference files |
| `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt` | Protected rollback Instructions |

Development continuity also retains `AGENTS.md`, `knowledge/00_PROJECT_MASTER_CONTEXT.md`, `knowledge/16_CURRENT_PROGRAM_STATUS.md` and the locked master plan.

## 5. Knowledge

Single source of truth: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`.

No duplicate/unlisted production upload. Permanent Knowledge contains reusable reference material only; account-specific/private data and authentication material stay outside GPT Knowledge.

## 6. Actions versus internal engines

Only operationIds present in effective imported production `/openapi.json` are GPT Actions.

Internal v9 routing/policy/universe/research/credit/fund/risk/strategy/optimizer/plan/execution/Watchtower/journal modules are not automatically Actions. The GPT may use their reviewed semantics as reference discipline but cannot claim server execution without returned evidence.

## 7. Runtime files that must remain

- `app.py` and current compatibility/runtime dependencies;
- `omni_cio/reconciliation/` canonical broker-report reconciliation/gateway extension hook;
- `omni_cio/` domain/runtime packages including v9 modules;
- `render.yaml` and non-secret environment templates;
- canonical dependency inputs/lock files;
- tests/scripts/workflows including Regression Shield;
- architecture/operations/recovery documentation.

One-time bootstrap payload chunks and generated CI projections are **not** runtime assets and must not be retained once their release task is complete.

## 8. Protected execution boundary

Real BUY/SELL remains exact-owner-confirmed, immutable, idempotent and broker-reconciled. Protected v8.6.1 acceptance remains **100% complete** and rollback-safe.

Canonical recovery invariant: **idempotent replay verified with no second submit**.

Current v9 configuration does not authorize transfer/withdrawal, margin/short, MARKET/BESTPRICE, autonomous recurring real execution, automatic retry after ambiguity or token management through GPT.

## 9. External/manual boundary

GitHub cannot itself alter GPT Editor state or supply secret values. Owner acceptance for current v9 has already been recorded. Any future change follows the same discipline:

1. open the **existing** GPT on ChatGPT web;
2. Edit/Configure, never Create;
3. apply reviewed Name/Description/starters/Instructions/Knowledge;
4. keep Apps OFF / Actions ON;
5. refresh production OpenAPI and existing Bearer authentication if required;
6. run Preview acceptance;
7. `Update` the same GPT only after Preview passes;
8. record non-secret acceptance/restoration evidence in GitHub.

## 10. Recovery authority

Current `main` overrides old chats/screenshots. Never rebuild the bot from stale conversational text when it conflicts with the canonical files above.
