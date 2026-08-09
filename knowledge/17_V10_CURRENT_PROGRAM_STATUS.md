# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-09

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / WP9A COMPLETE / BLOCK C IN PROGRESS / WP10 NEXT**.

Accepted implementation progress remains **14%**. Block C is credited only after WP10 and the Block C Exit Gate complete.

Accepted completed work:

- Block A / WP0 — **COMPLETE (5%)**;
- Block B / WP1 — **COMPLETE**;
- Block B / WP2 — **COMPLETE**;
- Block B / WP3 — **COMPLETE**;
- Block B / WP4 — **COMPLETE (Block B accepted at 9%)**;
- Block C / WP5 — **COMPLETE**;
- Block C / WP6 — **COMPLETE**;
- Block C / WP7 — **COMPLETE**;
- Block C / WP8 — **COMPLETE**;
- Block C / WP9 — **COMPLETE**;
- Block C / WP9A — **COMPLETE**;
- GitHub Pro hybrid CI / Lenovo continuity hardening — **COMPLETE infrastructure hardening**;
- V10 release/build provenance, protected `v10.*` tag identity, immutable-release operating contract and fail-closed deployment provenance — **COMPLETE**;
- accepted V10 planning amendments remain binding but do not credit later runtime implementation before their owning WPs pass.

Current authorized implementation work package is now:

**WP10 — Backup, restore и off-device recovery.**

WP10 may define and implement measurable RPO/RTO, automated PostgreSQL backup, integrity hashes, retention/rotation, encrypted owner-controlled off-device copy, private non-secret configuration/model/RAG metadata backup, corrupt-backup detection, and an executed restore/recovery rehearsal. Recovery must preserve separation among GitHub-controlled source, encrypted private durable state and separately restored runtime secrets.

WP10 does **not** authorize starting WP11/Core extraction, activating later Core/Web/Telegram/Cortex/Ollama product runtimes, placing secret values in GitHub/CI/backups, changing broker/Real-money authority, weakening WP6–WP9A privilege/secret/supervision/operations boundaries, or changing `app:app` / `trading_methods=false`.

Owner start command: **`START V10`** received 2026-08-05.

Starting or advancing V10 never expands broker/Real-money authority by itself.

## Canonical authority

Base program:

- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`;
- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`.

Accepted planning elaborations are indexed by `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`. Binding execution/navigation sources additionally include:

- `AGENTS.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` for protected V9 runtime state;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/master-plan/OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_GITHUB_PRO_AND_MIGRATION_IMPLEMENTATION_AMENDMENT.md`;
- accepted architecture/security/recovery contracts under `docs/architecture/` and `docs/operations/`.

Protected production/recovery baseline remains **Omni-CIO v9.0.0 — COMPLETE / owner-accepted / controlled maintenance** until the responsible later V10 parity/decommission gate.

## Progress

| Block | Planned weight | Accepted state |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | COMPLETE — WP1 / WP2 / WP3 / WP4 |
| C. Lenovo Omni-CIO Node / infrastructure | 12% | IN PROGRESS — WP5 / WP6 / WP7 / WP8 / WP9 / WP9A COMPLETE / WP10 NEXT |
| D. V10 Core and data | 14% | NOT STARTED |
| E. Omni-CIO Web Platform | 14% | NOT STARTED |
| F. Telegram | 8% | NOT STARTED — product/interaction contract pre-approved only |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED — autonomous portfolio-governance role pre-approved only |
| I. Personal Real Execution | 7% | NOT STARTED — cash-only confirmed execution policy pre-approved only |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED — commercial/license/update/legal-gate planning pre-approved only |
| **TOTAL** | **100% planned** | **14% ACCEPTED** |

Block B's full 9% weight is accepted because WP4 and the Block B Exit Gate are complete. Block C's 12% weight is not credited yet: WP5–WP9A are accepted, while WP10 and the Block C Exit Gate remain.

## Accepted implementation evidence

- WP0 PR #228 -> `7c5de954eed10dd406e743c38f7bdef6b0634108`;
- WP1 PR #229 -> `dbd459b280de84d3f571b458b46f1039880312ca`;
- WP2 PR #230 -> `3e3a89791d7f1594e4e1ba52125f8361708ae29d`;
- WP3 PR #236 -> `289ff563e99a64bbf8b5a289e84668dde58ef42a`;
- WP4 primary PR #248 -> `cc37bdce69331e8b03f5fd46554dc486616414f6`;
- WP4 artifact-transport hardening PR #249 -> `6c97df17f0de21a27ec0d12ee9699d2a00fab53f`; post-merge Regression Shield run `31181814984` — **SUCCESS**;
- WP5 PR #251 -> `d0b80f91a434e93e5facb244a92b17b066ccdf2a`; post-merge Regression Shield run `31252745722` — **SUCCESS**;
- WP6 PR #253 -> `c55fb0a32b309628fb86a7abf9182b95af4beca2`; post-merge Regression Shield run `31270545874` — **SUCCESS**;
- WP7 PR #255 -> `82225eef984f6c14c254108bada0627c1f0368a4`; exact-head Windows/Lenovo gates passed and post-merge Regression Shield run `31281148813` — **SUCCESS**;
- WP8 PR #257 -> `422ef68864050eec858e32d980165c995d9e7ecb`; exact-head secret-store/Windows/Lenovo gates passed and post-merge Regression Shield run `31284931677` — **SUCCESS**;
- WP9 PR #259 -> `b43da57e74e6c5d4735c2b4e96b6839a52b4d1dc`; post-merge Regression Shield run `31291892741` — **SUCCESS**;
- WP9A PR #261 -> `0e5a7ec750ef3d3c20bb3f01c0f53804017cd938`; post-merge Regression Shield #1445 / run `31294998878` — **SUCCESS**.

### WP9A accepted evidence

WP9A exact head `535c9d9e9983efb8f53ee164458272afe96d5281` passed the ready-for-review exact-head gates:

- V10 Fast PR Checks `31294760903`;
- V10 WP9A Operations Compatibility `31294760954`;
- V10 Toolchain Compatibility `31294760901`;
- authoritative Self-Hosted Windows CI `31294760884`;
- inherited V10 WP9 Supervision Compatibility `31294760943`;
- inherited V10 WP9 Supervision Audit `31294760904`;
- authoritative V10 WP9A Operations Audit `31294760894`.

The accepted Lenovo audit reported no WP9A blockers: Windows Update service remained enabled and Windows Update Agent reported no reboot required; Windows Time was running with measured offset `0 ms`; the self-hosted runner was healthy with default updater enabled; PostgreSQL 18.4 was ready; NVIDIA/resource telemetry remained within inherited WP5 limits; Ollama remained intentionally absent/`NOT_READY`; inherited WP9 health stayed fresh and truthfully `DEGRADED`; privacy flags remained false. Non-blocking diagnostics were limited to legacy pending-file-rename metadata and absence of historical runner self-update diagnostics.

WP9A established controlled Windows/update/reboot policy, runner/NVIDIA/PostgreSQL/Ollama update boundaries, inherited fail-closed time/resource guards, bounded restart/crash-loop OWNER-alert semantics, and privacy-safe local operations evidence. Its deterministic JSONL operations journal is bounded by field allowlist, file size/count/retention and SHA-256 hash-chain tamper evidence; external OWNER notification remains intentionally deferred to the responsible interaction WP rather than activating later Telegram/Web product runtimes early.

WP9A was squash-merged as `0e5a7ec750ef3d3c20bb3f01c0f53804017cd938`. Post-WP9A Regression Shield #1445 / run `31294998878` on that exact `main` SHA completed **SUCCESS**, including quality/contracts/coverage, dependency audit, SAST and tracked-content secret scan.

## Accepted engineering and product locks

The following remain binding while later WPs are implemented:

- V10 is controlled migration/productization of accepted V9, not a greenfield rewrite; default decision preference is `REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`;
- deterministic Core owns financial/accounting truth and money-path enforcement; AI never replaces deterministic calculations or receives direct broker-write authority;
- verified broker HTML account report import is the V10 accounting target; screenshot/OCR portfolio ingestion is not the target;
- MOEX current-market enrichment remains distinct from broker period-end accounting truth;
- local-first Cortex baseline remains Qwen3.5-4B via replaceable Ollama provider, but runtime installation/activation follows its owning later WP;
- research/evidence must carry provenance/freshness/identity binding and retrieved external text is untrusted data;
- GitHub is engineering Control Plane, not secret/private-portfolio custody and never broker authority;
- Lenovo is the first replaceable Personal runtime node and the authoritative heavy Windows/continuity lane;
- Telegram remains a later OWNER-only companion to the same Core/Web/Cortex and owns no financial calculation or broker-write authority;
- Real READ, Sandbox and Real TRADING credentials remain isolated; transfer/withdrawal, margin/short and autonomous Real execution remain forbidden;
- `REAL_TRADING_ENABLED=false` remains the master Real rollback until a responsible later package explicitly changes and proves the boundary.

## Current authorized next step — WP10

WP10 is now the only authorized implementation package after accepted WP9A and its successful post-merge Regression Shield.

WP10 goal: prove that private durable state and operational metadata can be backed up, verified and restored after corruption or node loss without relying on GitHub for private data or secrets.

WP10 must cover at minimum:

- explicit, measurable RPO and RTO derived from accepted WP5 hardware/storage evidence;
- automated PostgreSQL backup with integrity hash and bounded retention/rotation;
- encrypted off-device copy to an OWNER-controlled target;
- backup of approved private non-secret configuration and model/RAG metadata without raw runtime secrets;
- corrupt/tampered backup detection before restore;
- automated or deterministic restore rehearsal to a controlled replacement/recovery database/location;
- post-restore integrity/migration/reconciliation validation;
- clear separation of GitHub source recovery, encrypted durable-state recovery and separately restored runtime secrets;
- recovery runbook for SSD/Lenovo loss that keeps Real execution disabled until its own later recovery/readiness acceptance.

WP10 must preserve all accepted WP6–WP9A privilege, secret, supervision, privacy and operations boundaries. CI/runner identities must not gain access to private production backup payloads. Backup/recovery tooling must not place real secret values, full private portfolio dumps or recovery keys in GitHub, CI logs or artifacts. WP11 remains locked until WP10 Exit Gate and the Block C Exit Gate pass.

The Master Plan explicitly requires an OWNER-controlled off-device storage location for final WP10 acceptance. Repository design, deterministic tests, local backup/restore rehearsal tooling and all safely automatable gates should be completed before requesting that physical/non-delegable OWNER action.

## Money/safety rule

GitHub access, AI output, research result, Watchtower alert, Telegram message/button, `START V10`, development approval, update availability, backup availability or model output is never broker-submit authorization.

Current V9 money-path invariants, `app:app`, `trading_methods=false`, secret separation and kill switches remain binding until an explicitly responsible later V10 work package replaces a boundary and passes its Exit Gate.