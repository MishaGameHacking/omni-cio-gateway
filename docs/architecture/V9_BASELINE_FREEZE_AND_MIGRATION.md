# Omni-CIO v9 — Baseline Freeze & Migration Contract

Status: WP0 active

## Protected production baseline

The protected production baseline for the v9 program is Omni-CIO v8.6.1 at or after the owner-accepted real BUY/SELL v1 release. The baseline includes the existing single Custom GPT, single Render Gateway, read-only contour, isolated Sandbox contour, isolated real-execution contour, Upstash durable journal, kill switch and exact-confirmation protocol.

No v9 work may silently rewrite or bypass the v8.6.1 execution contract.

## Migration rule

Every v9 work package must be additive or feature-flagged until its own acceptance criteria are complete. A package may replace an older internal component only after:

1. an explicit architecture/data contract is merged;
2. deterministic unit/contract tests cover the new component;
3. legacy behavior required by v8.6.1 is covered by regression tests;
4. exact-head Regression Shield is green;
5. rollback is documented;
6. production-visible changes receive the required Preview/production acceptance.

## Runtime invariants that remain mandatory

- one product: Custom GPT -> Omni-CIO Gateway -> T-Invest;
- `TINVEST_TOKEN` remains production read-only;
- Sandbox uses only `TINVEST_SANDBOX_TOKEN` and remains `real_money=false`;
- real execution uses only separate `TINVEST_TRADING_TOKEN` and durable journal;
- account IDs stay masked;
- no withdrawal/transfer/securities transfer surface;
- no margin/short in the protected real v1 execution path;
- real execution remains immutable proposal -> new-turn exact owner confirmation -> submit once -> broker reconciliation;
- ambiguous possible-submit is never retried automatically;
- `REAL_TRADING_ENABLED=false` remains the master rollback;
- GitHub stores no broker/Upstash/Gateway secret values.

## Feature-flag discipline

New v9 engines must default to shadow/read-only mode until their package acceptance is complete. New code must not implicitly change the existing production decision or execution path merely because it is deployed.

Feature flags must have:

- safe default;
- explicit validation;
- fail-closed behavior for execution-affecting features;
- documented rollback value;
- tests proving old behavior when disabled.

## Data and decision migration

New v9 state must be versioned. Durable schemas must include a version field and must not destructively reinterpret existing real-trading journal records. If a new schema cannot read old data safely, migration must be explicit, reversible where practical, and covered by fixtures.

## GPT migration

The current applied GPT remains v8.6.1 until WP15. Intermediate v9 backend features may be deployed behind flags without requiring the owner to continuously edit the GPT. A new canonical GPT payload is produced only after the relevant backend contracts are stable.

## Rollback hierarchy

1. disable the package-specific v9 feature flag;
2. if execution integrity is uncertain, set `REAL_TRADING_ENABLED=false`;
3. preserve durable evidence while any order/plan state is unresolved;
4. reconcile broker state before deleting operational state;
5. revert to the last green production commit only after state reconciliation if broker writes could have occurred.

## WP0 completion criteria

WP0 is complete only when:

- v9 master program is merged and linked from canonical project instructions;
- stale recovery/configuration references to pre-v8.6.1 production behavior are removed or explicitly marked historical;
- repository-layout checks recognize the v8.6.1 real-execution baseline;
- a dedicated configuration-consistency check prevents version/knowledge/program drift;
- Regression Shield runs that consistency check;
- recovery docs identify v8.6.1 as the protected applied GPT and v9 as the active development program;
- no runtime or broker-write behavior changes are introduced by WP0.
