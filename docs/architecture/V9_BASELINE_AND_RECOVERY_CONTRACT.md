# Omni-CIO v9 — Baseline and Recovery Contract

Status: WP0 implementation contract.

## Protected production baseline

The stable production baseline is Omni-CIO v8.6.1 at the start of the v9 program.

The following invariants must remain valid until a later version passes its own staged acceptance:

- one supported Custom GPT and one production Gateway;
- stable Render entrypoint `app:app`;
- production read-only token remains separate and read-only;
- Sandbox and real execution credentials remain isolated;
- real execution remains explicit-owner-confirmed, immutable, idempotent and broker-reconciled;
- no withdrawal, transfer, margin, short, MARKET/BESTPRICE, autonomous recurring execution or secret exposure;
- `REAL_TRADING_ENABLED=false` remains the master real-execution rollback state.

## Canonical recovery registry

The following values are machine-checked:

- UI release name: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- GPT Editor Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- Knowledge upload set: exactly the ten files listed in `gpt/CONFIGURATION.md`;
- Gateway endpoint: `https://omni-cio-gateway.onrender.com`;
- OpenAPI endpoint: `https://omni-cio-gateway.onrender.com/openapi.json`;
- health endpoint: `https://omni-cio-gateway.onrender.com/health`;
- production entrypoint: `app:app`;
- active roadmap: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.

## Migration rule

Every v9 work package must be additive or feature-flagged until its exact-head Regression Shield and package-specific acceptance pass.

A package may not silently replace the stable production path. Any migration must document:

1. old behavior;
2. new behavior;
3. feature flag or compatibility boundary;
4. data migration, if any;
5. rollback procedure;
6. tests proving the old protected path still works;
7. production acceptance required before declaring the package active.

## Rollback rule

Rollback must restore the last accepted production configuration without relying on chat history or screenshots.

The recovery source of truth is GitHub `main` plus external secret names documented in `gpt/SECRETS_AND_RENDER.md`. Secret values, private account IDs and private portfolio data are never stored in GitHub.

## CI consistency gate

`scripts/check_gpt_recovery_consistency.py` must fail when canonical setup files disagree about:

- UI release/version;
- current Instructions path;
- Knowledge file set/count;
- production endpoint or entrypoint;
- v9 active program;
- completed v8.6.1 Phase 4 release state;
- prohibited stale statements such as “Phase 4 remains”.

This gate is part of Regression Shield and must run on every pull request and push to `main`.
