# Omni-CIO V10 — Protected V9 Baseline Freeze

Status: **WP0 protected baseline**  
Purpose: define exactly what V10 must not regress before a later package explicitly replaces a boundary.

## 1. Baseline identities

### V10 start repository baseline

Accepted `main` at the moment the owner issued `START V10`:

`159316c5b211977b0d9125dffb86210316ae10d3`

This is the squash merge of planning PR #227. That planning merge did not intentionally change production runtime authority.

Post-merge Regression Shield on this exact start SHA:

**run #1332 — success**.

### Last completed V9 feature-program repository acceptance

WP15 repository target:

`b9e4fabcb54f8f6e0ba206f030c35f2fafa2ce62`

WP15 exact-head Regression Shield evidence:

**#1241** on head `578ffad5362df3182f8a23937ab4ca19de5c0b78`, followed by owner acceptance on the existing GPT.

### Protected Real rollback release

Protected v8.6.1 release commit:

`baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`

Canonical Real recovery invariant:

**idempotent replay verified with no second submit**.

## 2. Current accepted V9 runtime

Until a later V10 work package explicitly replaces a boundary and passes its Exit Gate, preserve:

- applied Custom GPT: `Omni-CIO API | Управляющий и аналитик v9.0.0`;
- applied Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`;
- applied Knowledge manifest: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`;
- production Gateway: `https://omni-cio-gateway.onrender.com`;
- production OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`;
- stable entrypoint: `app:app`;
- current wrappers/runtime dependencies including `app_v371.py`, `app_v360.py`, `main.py` while imported;
- production read-only broker credential remains read-only;
- Sandbox remains virtual and isolated;
- Real execution remains separate, narrow, exact-owner-confirmed and broker-reconciled;
- Watchtower hidden scheduler/callback routes remain outside GPT OpenAPI.

## 3. Protected safety behavior

V10 must not regress these invariants without a later owner-reviewed architecture/security replacement:

- READ token never falls back to trading credential;
- Real trading credential is separate and has no transfer authority;
- no real submit from advisory wording, `START V10`, alert acknowledgement or development approval;
- prepare/plan and execute approval do not collapse into one implicit authorization;
- immutable proposal/plan identity before Real submit;
- fresh trusted market/account preflight;
- own-funds BUY / own-position SELL;
- no withdrawal/transfer;
- no margin/uncovered short;
- no MARKET/BESTPRICE under current reviewed surface;
- no automatic retry after possible-submit ambiguity;
- at most one possible submit per request identity;
- `submitted` != `filled` without broker evidence;
- account identity stays masked in user-facing output;
- secret values/private broker payloads never enter GitHub/Knowledge/public output;
- exact decimal/multi-currency discipline remains intact.

Master rollback:

`REAL_TRADING_ENABLED=false`.

Watchtower rollback:

`WATCHTOWER_ENABLED=false`.

## 4. Protected V9 capability stack

Repository-delivered and owner-accepted V9 program components:

- CIO routing;
- Investment Policy/readiness;
- market universe;
- candidate funnel;
- research/evidence;
- credit/rating/default;
- Fund X-Ray;
- portfolio risk 2.0;
- meta-strategy;
- optimizer/capital scaling;
- immutable portfolio plans;
- safe plan execution;
- Portfolio Watchtower;
- Decision Journal/evaluation/replay;
- applied Custom GPT v9 configuration/recovery.

V10 may extract/refactor these engines later, but golden-equivalence/compatibility evidence is required before retiring existing paths.

## 5. Canonical recovery assets

Must remain available until their explicit replacement/retirement gate:

- `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
- `docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md`;
- `gpt/SETUP_INDEX.md`;
- `gpt/CONFIGURATION.md`;
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`;
- `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`;
- `gpt/ACTIONS_CATALOG.md`;
- `gpt/SECRETS_AND_RENDER.md`;
- `gpt/MY_GPT_SETUP_RUNBOOK.md`;
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- existing Regression Shield/security workflows and recovery consistency checks.

## 6. Regression evidence that remains mandatory

Until intentionally replaced by a later V10 package, every significant V10 PR must preserve the existing Regression Shield coverage for:

- dependency-lock reproducibility;
- CI/security policy;
- repository structure/contract checks;
- Python compilation;
- Ruff lint/format;
- mypy baseline;
- stable `app:app` entrypoint;
- GPT Action/recovery contracts while current GPT remains applied;
- pytest/coverage;
- dependency audit;
- SAST;
- secret scan.

A later V10 test suite may add checks, but may not silently remove protected gates merely to make migration easier.

## 7. Replacement rule

A protected V9 boundary is retired only when the responsible V10 WP documents:

1. protected behavior;
2. replacement behavior;
3. migration/activation boundary;
4. deterministic regression evidence;
5. failure mode;
6. rollback/forward-recovery;
7. security/money-authority review;
8. required runtime/owner acceptance.

Before that evidence, the V9 boundary remains authoritative.
