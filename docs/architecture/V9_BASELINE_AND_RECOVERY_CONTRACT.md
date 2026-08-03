# Omni-CIO v9 — Baseline and Recovery Contract

Status: **WP0 protected-baseline contract**.  
Protected release: **Omni-CIO v8.6.1**.  
Release commit: **`baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`**.  
Active program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.

## 1. Protected production baseline

The v8.6.1 release commit above is the immutable reference point for the second major development program. It records the completed real-money v1 acceptance, including broker fill, portfolio/operations reconciliation and replay protection.

Until a later version passes its own package-specific Regression Shield and staged acceptance, preserve these invariants:

- one supported Custom GPT and one production Gateway;
- production service `omni-cio-gateway`, Render Free, entrypoint `app:app`;
- production read-only `TINVEST_TOKEN` remains separate and read-only;
- Sandbox and real execution credentials remain isolated;
- real execution remains explicit-owner-confirmed, immutable, idempotent and broker-reconciled;
- no withdrawal, transfer, margin, uncovered short, MARKET/BESTPRICE or autonomous recurring real execution;
- secret values and full broker account identifiers are never committed;
- `REAL_TRADING_ENABLED=false` remains the master real-execution rollback state.

The v9 program may add intelligence around this baseline, but no package may silently weaken or bypass it.

## 2. Canonical recovery registry

The following values are machine-checked by `scripts/check_gpt_recovery_consistency.py`:

- UI release name: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- GPT Editor Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`;
- Knowledge upload set: exactly the ten files listed in `gpt/CONFIGURATION.md`;
- Gateway endpoint: `https://omni-cio-gateway.onrender.com`;
- OpenAPI endpoint: `https://omni-cio-gateway.onrender.com/openapi.json`;
- health endpoint: `https://omni-cio-gateway.onrender.com/health`;
- production entrypoint: `app:app`;
- active roadmap: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`;
- completed v8.6.1 release state.

The compact Instructions payload must remain within the current 8,000-character GPT Editor limit.

## 3. Migration contract for every v9 package

Each v9 package must document and test:

1. **Protected behavior** — which v8.6.1 behavior must remain unchanged.
2. **New behavior** — the exact capability being added.
3. **Activation boundary** — feature flag, new read-only route, shadow mode or other explicit compatibility boundary.
4. **State/data migration** — schema/version changes, if any, with backwards handling.
5. **Failure mode** — how the package fails closed when inputs, external services or state are unavailable.
6. **Rollback** — exact steps to return to the last accepted production configuration.
7. **Regression proof** — unit/fake-client/integration tests proving the protected path still works.
8. **Acceptance** — shadow, Sandbox or minimal-real validation required before declaring the package active.
9. **Documentation** — update only canonical source-of-truth files; do not create duplicate setup documents.

No production mutation capability is activated merely because its code is merged.

## 4. Rollback contract

Rollback must be possible without chat history or screenshots.

Recovery source of truth:

- GitHub `main` for code and reference configuration;
- `gpt/SETUP_INDEX.md` for restoration order;
- `gpt/CONFIGURATION.md` for GPT identity/capabilities;
- `gpt/BOT_ONLY_FILE_MANIFEST.md` for canonical bot files;
- `gpt/SECRETS_AND_RENDER.md` for secret **names** and external boundaries;
- Render/Upstash/GPT Editor for actual external state and secret values.

For a v9 package rollback:

1. disable the package feature flag or route surface if one exists;
2. restore the last accepted code/config commit when required;
3. retain durable journals and evidence needed for reconciliation;
4. never reuse an ambiguous real-order proposal as a new submit;
5. verify `/health`, baseline read-only Actions and affected package contract;
6. only then re-enable any optional execution contour.

## 5. CI recovery-consistency gate

`scripts/check_gpt_recovery_consistency.py` must fail when canonical files disagree about:

- UI name/version;
- current Instructions/reference files;
- Knowledge file set/count;
- production endpoint, OpenAPI or entrypoint;
- current v9 program lock;
- protected baseline commit;
- completed v8.6.1 Phase 4 release state;
- current real Action names;
- stale recovery statements such as “Phase 4 remains”.

The gate also validates that the compact Instructions payload fits the editor limit.

It is exercised by the Regression Shield test suite and must remain green on every v9 package before merge.

## 6. WP0 exit condition

WP0 may be marked complete only after:

- canonical recovery files contain no conflicting release state;
- the recovery consistency checker and its tests pass;
- the exact-head Regression Shield is green;
- the protected v8.6.1 baseline remains behaviorally unchanged;
- the v9 program remains locked as the active roadmap.
