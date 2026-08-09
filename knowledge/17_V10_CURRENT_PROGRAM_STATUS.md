# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-09

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / WP10 COMPLETE / BLOCK C COMPLETE / WP11 NEXT**.

Accepted implementation progress is now **26%**:

- Block A — **COMPLETE (5%)**;
- Block B — **COMPLETE (9%)**;
- Block C — **COMPLETE (12%)**;
- Block D — **NOT STARTED / WP11 NEXT**.

Current authorized implementation work package:

**WP11 — V9 Core Extraction.**

WP11 may begin only from accepted `main` after WP10 post-merge acceptance is recorded. WP12 and all later WPs remain locked until WP11 Exit Gate passes and the accepted status is updated again.

Owner start command: **`START V10`** received 2026-08-05.

Starting or advancing V10 never expands broker/Real-money authority by itself.

## Canonical authority

Base program:

- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`.

Accepted planning elaborations are indexed by `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`. Binding execution/navigation sources additionally include:

- `AGENTS.md`;
- `README.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` for protected V9 runtime state;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/master-plan/OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_GITHUB_PRO_AND_MIGRATION_IMPLEMENTATION_AMENDMENT.md`;
- accepted architecture/security/recovery contracts under `docs/architecture/` and `docs/operations/`.

Protected production/recovery baseline remains **Omni-CIO v9.0.0 — COMPLETE / owner-accepted / controlled maintenance** until the responsible later V10 parity/decommission gate.

Historical issue text, old PR descriptions, screenshots and old chat context do not override accepted `main` plus this authority chain.

## Progress

| Block | Planned weight | Accepted state |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | COMPLETE — WP1 / WP2 / WP3 / WP4 |
| C. Lenovo Omni-CIO Node / infrastructure | 12% | **COMPLETE — WP5 / WP6 / WP7 / WP8 / WP9 / WP9A / WP10** |
| D. V10 Core and data | 14% | NOT STARTED — **WP11 NEXT** |
| E. Omni-CIO Web Platform | 14% | NOT STARTED |
| F. Telegram | 8% | NOT STARTED — product/interaction contract pre-approved only |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED — autonomous portfolio-governance role pre-approved only |
| I. Personal Real Execution | 7% | NOT STARTED — cash-only confirmed execution policy pre-approved only |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED — commercial/license/update/legal-gate planning pre-approved only |
| **TOTAL** | **100% planned** | **26% ACCEPTED** |

Block D is credited only after its owning WPs and Block D Exit Gate complete; WP11 implementation by itself does not increase the accepted percentage.

## Accepted implementation evidence

- WP0 PR #228 -> `7c5de954eed10dd406e743c38f7bdef6b0634108`;
- WP1 PR #229 -> `dbd459b280de84d3f571b458b46f1039880312ca`;
- WP2 PR #230 -> `3e3a89791d7f1594e4e1ba52125f8361708ae29d`;
- WP3 PR #236 -> `289ff563e99a64bbf8b5a289e84668dde58ef42a`;
- WP4 primary PR #248 -> `cc37bdce69331e8b03f5fd46554dc486616414f6`;
- WP4 artifact-transport hardening PR #249 -> `6c97df17f0de21a27ec0d12ee9699d2a00fab53f`; post-merge Regression Shield run `31181814984` — **SUCCESS**;
- WP5 PR #251 -> `d0b80f91a434e93e5facb244a92b17b066ccdf2a`; post-merge Regression Shield run `31252745722` — **SUCCESS**;
- WP6 PR #253 -> `c55fb0a32b309628fb86a7abf9182b95af4beca2`; post-merge Regression Shield run `31270545874` — **SUCCESS**;
- WP7 PR #255 -> `82225eef984f6c14c254108bada0627c1f0368a4`; post-merge Regression Shield run `31281148813` — **SUCCESS**;
- WP8 PR #257 -> `422ef68864050eec858e32d980165c995d9e7ecb`; post-merge Regression Shield run `31284931677` — **SUCCESS**;
- WP9 PR #259 -> `b43da57e74e6c5d4735c2b4e96b6839a52b4d1dc`; post-merge Regression Shield run `31291892741` — **SUCCESS**;
- WP9A PR #261 -> `0e5a7ec750ef3d3c20bb3f01c0f53804017cd938`; post-merge Regression Shield run `31294998878` — **SUCCESS**;
- WP10 PR #263 -> `7346052c6f6eea1715cd6b699c939d28eb927c9d`; post-merge Regression Shield run `31317709162` — **SUCCESS**.

## WP10 accepted evidence

WP10 exact head `e72b519c96d41bbaa36f3267638fff8d65bcd6cf` passed the authoritative/current-WP gates before squash merge:

- Self-Hosted Windows CI run `31317333590` — **SUCCESS**, including `V10 authoritative merge gate`;
- V10 WP10 Off-Device Audit run `31317333582` — **SUCCESS**;
- V10 WP10 Recovery Audit run `31317333594` — **SUCCESS**;
- V10 WP10 Recovery Continuity run `31317333576` — **SUCCESS** on isolated official CPython 3.14.6;
- OWNER-controlled encrypted off-device recovery rehearsal — **PASS** with sanitized evidence only;
- unresolved review threads — none.

WP10 established and proved:

- RPO = **60 minutes** and RTO = **240 minutes** for the future product DB binding;
- PostgreSQL 18 custom logical backup/restore tooling with SHA-256 and exact-size verification;
- bounded retention/rotation and corrupt/tampered backup rejection;
- encrypted OWNER-controlled off-device recovery target;
- separation of GitHub-controlled source, encrypted durable private state and separately restored runtime secrets;
- restore into an isolated recovery database and post-restore validation;
- no production DB access from CI, no private portfolio payloads in CI, and no real secret/recovery-key values in GitHub evidence;
- `app:app`, `trading_methods=false` and `REAL_TRADING_ENABLED=false` preserved.

The GitHub-hosted Fast PR / Toolchain / Recovery Compatibility lanes on the WP10 exact head reported external zero-step billing/spending failures. They are recorded as **DEGRADED_HOSTED_ACCELERATION**, not as successful source tests and not as evidence that source code failed. The OWNER-approved no-paid-overage continuity contract requires authoritative safety gates to remain enabled; those self-hosted authoritative gates passed.

After squash merge to `main` as `7346052c6f6eea1715cd6b699c939d28eb927c9d`, mandatory Regression Shield run `31317709162` completed **SUCCESS**:

- quality/contracts/coverage — SUCCESS;
- dependency audit — SUCCESS;
- SAST — SUCCESS;
- tracked-content secret scan — SUCCESS;
- stable `app:app` and read-only GPT Actions contract — SUCCESS.

Therefore WP10 and Block C are accepted. No rollback is justified by the currently available CI evidence. Any future concrete runtime defect must be handled as a focused defect branch/PR with reproduced evidence; accepted `main` must not be rewritten or force-reset.

## Accepted engineering and product locks

The following remain binding while later WPs are implemented:

- V10 is controlled migration/productization of accepted V9, not a greenfield rewrite;
- default migration preference is `REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`;
- no material rewrite begins while its owning reuse decision is `TBD_AT_OWNING_WP`;
- deterministic Core owns financial/accounting truth and money-path enforcement;
- AI never replaces deterministic calculations or receives direct broker-write authority;
- verified broker HTML account report import is the V10 accounting target; screenshot/OCR portfolio ingestion is not the target;
- MOEX current-market enrichment remains distinct from broker period-end accounting truth;
- GitHub is engineering Control Plane, not secret/private-portfolio custody and never broker authority;
- Lenovo is the first replaceable Personal runtime node and authoritative heavy Windows/continuity lane;
- Real READ, Sandbox and Real TRADING credentials remain isolated;
- transfer/withdrawal, margin/short and autonomous Real execution remain forbidden;
- `REAL_TRADING_ENABLED=false` remains the master Real rollback until a responsible later package explicitly changes and proves that boundary;
- `app:app` remains the protected gateway entrypoint until a responsible migration package explicitly replaces it;
- no direct push to `main`; changes use focused branch -> PR -> exact-head gates -> resolved review threads -> squash merge.

## Merge discipline — mandatory

For every V10 implementation PR from WP11 onward:

1. Do not merge merely because files exist or because some tests passed.
2. The current WP binary Exit Gate must be satisfied on the **exact PR head SHA** with repository-required evidence.
3. Any source/test/security failure must be diagnosed and corrected before merge; do not weaken the gate to obtain green status.
4. External CI/account/infrastructure failures must be explicitly classified with evidence and handled only through an already accepted fallback/continuity rule; never silently reinterpret them as source PASS.
5. Unresolved review threads must be zero.
6. Merge method is squash only.
7. After merge, mandatory post-merge Regression Shield must pass before the next WP is credited/started.
8. If post-merge validation discovers a real regression, stop the next WP and repair/revert through a new focused branch/PR; never force-rewrite protected `main`.

This discipline is the default operating rule; OWNER involvement is requested only for genuinely non-delegable physical/admin/secret/product-policy actions.

## Current authorized next step — WP11

WP11 is the only authorized implementation package after accepted WP10/Block C.

### Goal

Extract the accepted V9 financial engines from mandatory Custom GPT presentation coupling while preserving deterministic V9 behavior and rollback compatibility.

### Required deliverables

- inventory all accepted V9 WP1–WP14 engines and their actual dependencies on `app`/GPT wrappers;
- bind each material component to the V10 parity ledger and component reuse matrix before material rewrite;
- define stable Python Core service interfaces/DTOs;
- preserve legacy compatibility while parallel regression comparisons are active;
- remove UI/GPT assumptions from internal engines only where required, without changing financial formulas absent separate proof;
- preserve protected V9 runtime/recovery behavior until the WP11 Exit Gate is accepted.

### Required validation

- Golden V9 fixtures: equivalent input must produce deterministic equivalent output before/after extraction;
- no-GPT integration path must exercise `portfolio -> risk -> optimizer -> plan` without OpenAI/Custom GPT dependency;
- existing V9 regression/security tests remain passing;
- explicit negative checks for accidental broker-authority expansion, secret access expansion and public contract drift;
- exact-head authoritative CI/security evidence before merge.

### WP11 Exit Gate

**PASS only if:**

- Core can execute the required deterministic path without Custom GPT and without OpenAI;
- accepted V9 rollback remains operational;
- parity evidence is deterministic and documented;
- no protected broker/security/runtime boundary is weakened;
- all required exact-head gates pass and review threads are resolved.

### WP11 explicit non-goals

WP11 does **not** authorize:

- WP12 canonical tenant/data model implementation;
- WP13 production schema/migrations;
- WP14 durable job system;
- WP15 new read-only broker layer;
- Web/Telegram/Cortex/Ollama runtime activation;
- changing public GPT Actions without an explicit compatibility/migration requirement;
- changing broker Real-money authority;
- changing `app:app`, `trading_methods=false` or `REAL_TRADING_ENABLED=false` as a shortcut.

WP11 must use `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md` before material coding. WP12 remains locked until WP11 Exit Gate and post-merge acceptance are complete.

## Money/safety rule

GitHub access, AI output, research result, Watchtower alert, Telegram message/button, `START V10`, development approval, update availability, backup availability or model output is never broker-submit authorization.

Current V9 money-path invariants, `app:app`, `trading_methods=false`, secret separation and kill switches remain binding until an explicitly responsible later V10 work package replaces a boundary and passes its Exit Gate.
