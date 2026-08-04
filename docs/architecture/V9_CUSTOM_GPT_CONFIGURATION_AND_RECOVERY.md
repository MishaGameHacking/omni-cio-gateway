# Omni-CIO v9 — Custom GPT Configuration & Recovery Contract

Status: **WP15 implementation contract**  
Parent program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`  
Dependency base: WP14 squash merge `507b7f53e3ab924f0d484e348528c23b79ffce9d`.

## 1. Objective

WP15 upgrades the **existing** Omni-CIO Custom GPT configuration from the protected v8.6.1 applied baseline to the canonical v9 repository configuration. It does not create a second GPT, Gateway, frontend, scheduler or broker stack.

GitHub is the canonical recovery source. Applying the configuration in ChatGPT remains an owner-controlled external step after repository gates are green.

## 2. Target identity

Canonical target release:

- config release: `v9.0.0`;
- UI name: `Omni-CIO API | Управляющий и аналитик v9.0.0`;
- Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`;
- Knowledge manifest: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`;
- Actions catalog: `gpt/ACTIONS_CATALOG.md`;
- setup/recovery index: `gpt/SETUP_INDEX.md`;
- full setup runbook: `gpt/MY_GPT_SETUP_RUNBOOK.md`;
- stable Gateway: `https://omni-cio-gateway.onrender.com`;
- stable entrypoint: `app:app`.

The protected v8.6.1 files remain in GitHub as rollback evidence and are not deleted.

## 3. Editor model/capability policy

Model naming in ChatGPT changes independently of this repository. Recovery therefore does **not** bind correctness to a marketing model name. Select a currently available non-Pro model that supports Custom GPT Actions and verify it in Preview.

Capabilities:

- Actions: ON;
- Apps: OFF while Actions are used;
- Web Search: ON for public context only;
- Data Analysis: ON for calculations/structured files when available;
- Image generation: not required for the investment workflow.

## 4. Instructions versus Knowledge

Behavioral and safety rules belong in compact Instructions. Knowledge files are reference material and must not be treated as a substitute for server enforcement.

The v9 Instructions must remain within the repository-enforced editor character limit and preserve these invariants:

- ordinary Russian language routing;
- facts/actions before strong conclusions;
- explicit data-quality/freshness handling;
- IPS/policy constraints before personal sizing;
- candidate comparison against `NO_ACTION`;
- risk/concentration/credit/fund look-through discipline;
- immutable-plan semantics where discussed;
- no claim that an internal v9 Python module is a GPT Action unless it exists in the effective production OpenAPI;
- real execution only through the effective reviewed Real Actions and exact owner-confirmation lifecycle;
- no secret/account-id leakage.

## 5. Production Actions contract

The GPT imports the **effective production** schema from:

`https://omni-cio-gateway.onrender.com/openapi.json`

Authentication:

- type: API Key;
- mode: Bearer;
- value: existing `GATEWAY_API_KEY` managed outside GitHub.

WP15 does not invent Action operation IDs from internal WP1–WP14 modules. An operation is callable by the GPT only if it is present in the imported production OpenAPI.

The baseline reviewed surface remains the stable read-only GET surface. Conditional Sandbox/Real surfaces remain governed by their existing server flags/readiness. WP15 does not broaden real-money authority merely by changing GPT configuration.

## 6. v9 orchestration boundary

The v9 repository contains deterministic engines for routing, policy, universe, candidate screening, research, credit, funds, risk, strategy, optimization, immutable plans, safe plan execution, Watchtower and decision evaluation.

Custom GPT configuration uses their reviewed semantics as behavioral/reference constraints, but it must distinguish three things:

1. **effective GPT Actions** — callable API operations present in current OpenAPI;
2. **internal deterministic engines** — server/repository capabilities that are not automatically callable Actions;
3. **owner-confirmed execution** — consequential broker writes controlled by the existing server execution boundary.

The GPT must never fabricate a tool call or imply that an internal engine ran when no production evidence proves it.

## 7. Knowledge contract

The exact production upload set is defined only by `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md` and machine-checked by the recovery consistency script.

Rules:

- upload each listed file exactly once;
- no unlisted legacy duplicate;
- no broker report, account identifier, token, Authorization header, private key or source-code dump;
- reference files are text-forward;
- behavior/safety stays in Instructions;
- after upload, verify representative retrieval in Preview.

## 8. Recovery sources of truth

Recovery order:

1. `gpt/SETUP_INDEX.md`;
2. `gpt/CONFIGURATION.md`;
3. target compact Instructions;
4. v9 Knowledge manifest and listed files;
5. production `/openapi.json`;
6. `gpt/ACTIONS_CATALOG.md`;
7. `gpt/SECRETS_AND_RENDER.md`;
8. `gpt/MY_GPT_SETUP_RUNBOOK.md`;
9. `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

Old chat text or screenshots never override current `main`.

## 9. Upgrade-in-place proof

The release checklist explicitly requires opening the existing Omni-CIO GPT and selecting Edit/Configure. The owner must not use `Create` for WP15.

Evidence after Preview acceptance records:

- existing GPT identity/link retained;
- name updated in place;
- target Instructions pasted in full;
- exact Knowledge set present once each;
- existing production Action replaced/refreshed from current OpenAPI rather than creating a duplicate bot;
- authentication boundary preserved;
- Preview acceptance passed;
- `Update` applied to the existing GPT.

## 10. Rollback

Repository rollback target is the protected v8.6.1 configuration:

- UI: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- corresponding v8.6.1 Knowledge/recovery registry retained in git history;
- Gateway remains `app:app`;
- `REAL_TRADING_ENABLED=false` remains the master real-money kill switch.

A GPT configuration rollback never rotates or copies broker/Upstash/QStash secrets through ChatGPT.

## 11. Exit gate

WP15 repository delivery is complete only when:

1. architecture and threat/recovery contracts exist;
2. compact v9 Instructions pass character/safety checks;
3. exact Knowledge manifest is machine-checked;
4. Actions catalog matches the reviewed production OpenAPI policy;
5. configuration/version consistency CI is green;
6. recovery docs can reconstruct the existing GPT without secrets in GitHub;
7. exact-head Regression Shield and security are green;
8. unresolved review threads are zero;
9. PR is squash-merged.

Program completion additionally requires owner Preview acceptance and restoration demonstration on the **existing** GPT. Until that owner-controlled external step is recorded, repository readiness must not be misreported as applied production v9 acceptance.
