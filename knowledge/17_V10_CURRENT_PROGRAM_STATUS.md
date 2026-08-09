# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-09

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / WP9 COMPLETE / BLOCK C IN PROGRESS / WP9A NEXT**.

Accepted implementation progress remains **14%**. Block C is credited only after WP9A, WP10 and the Block C Exit Gate complete.

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
- GitHub Pro hybrid CI / Lenovo continuity hardening — **COMPLETE infrastructure hardening**;
- V10 release/build provenance, protected `v10.*` tag identity, immutable-release operating contract and fail-closed deployment provenance — **COMPLETE**;
- accepted V10 planning amendments remain binding but do not credit later runtime implementation before their owning WPs pass.

Current authorized implementation work package is now:

**WP9A — Runtime patching, time, observability и controlled restart policy.**

WP9A may establish the operations contract required before 24/7 operation: controlled Windows/security maintenance and reboot windows, GitHub Runner update health, NVIDIA/PostgreSQL/Ollama update policy, bounded restart/crash-loop/OWNER-alert policy, NTP/time-drift monitoring, CPU/RAM/GPU/VRAM/temperature/disk thresholds, and structured privacy-safe logging/rotation/retention/crash-dump policy. Any update capable of changing calculations, AI behavior, database compatibility or broker execution behavior must first pass the responsible compatibility/security/regression/eval gate and have documented rollback.

WP9A does **not** authorize installing/activating later Core/Web/Telegram/Cortex/Ollama product runtimes, real secrets in GitHub/CI, broker-write/Real-money execution, service-account privilege expansion, WP10 work, or any change to `app:app` / `trading_methods=false`.

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
| C. Lenovo Omni-CIO Node / infrastructure | 12% | IN PROGRESS — WP5 / WP6 / WP7 / WP8 / WP9 COMPLETE / WP9A NEXT |
| D. V10 Core and data | 14% | NOT STARTED |
| E. Omni-CIO Web Platform | 14% | NOT STARTED |
| F. Telegram | 8% | NOT STARTED — product/interaction contract pre-approved only |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED — autonomous portfolio-governance role pre-approved only |
| I. Personal Real Execution | 7% | NOT STARTED — cash-only confirmed execution policy pre-approved only |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED — commercial/license/update/legal-gate planning pre-approved only |
| **TOTAL** | **100% planned** | **14% ACCEPTED** |

Block B's full 9% weight is accepted because WP4 and the Block B Exit Gate are complete. Block C's 12% weight is not credited yet: WP5–WP9 are accepted, while WP9A, WP10 and the Block C Exit Gate remain.

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
- WP9 PR #259 -> `b43da57e74e6c5d4735c2b4e96b6839a52b4d1dc`.

### WP9 accepted evidence

WP9 exact head `c5e79b0f4ab1f7c4b4df9e232841e5d91293530d` and reviewed merge checkout `e934236a13e6597748405a8324c06dfb8039d724` passed:

- V10 Fast PR Checks `31291638901`;
- V10 WP9 Supervision Compatibility `31291638860`;
- V10 WP9 Recovery Compatibility `31291638903`;
- V10 Toolchain Compatibility `31291638876`;
- authoritative Self-Hosted Windows CI `31291638888`;
- inherited V10 WP8 Secret Store Compatibility `31291638887`;
- inherited V10 WP8 Secret Store Audit `31291638877`;
- V10 WP9 Supervision Audit `31291638933` after the reviewed OWNER reboot.

The reviewed OWNER rehearsal completed bounded synthetic kill/recovery, dependency recovery and a full Windows reboot. The self-hosted runner returned automatically. Fresh post-reboot Lenovo evidence reported `status=PASS`, empty reasons/blockers, `idempotence_verified=true`, `restart_rehearsal_pass=true`, `dependency_rehearsal_pass=true`, `post_reboot_fresh_status=true`, all five future product slots valid but disabled/sealed, no execution task, disabled/non-admin runtime and execution role anchors, no LocalService WP8 protected-payload grant, no real secrets and no Real-money authority change. `health_status=DEGRADED` is truthful and expected because later Core/Web/Telegram/Watchtower/AI product runtimes remain intentionally inactive.

WP9 was squash-merged as `b43da57e74e6c5d4735c2b4e96b6839a52b4d1dc`. Post-WP9 Regression Shield #1443 / run `31291892741` on that exact `main` SHA completed **SUCCESS**, including quality/contracts/coverage, dependency audit, SAST and tracked-content secret scan.

WP9 therefore establishes the accepted Windows Task Scheduler / `LOCAL SERVICE` supervision boundary, bounded crash/recovery rehearsal, dependency-aware health evidence, automatic runner return after reboot, truthful `HEALTHY/DEGRADED` semantics, and sealed later product slots without expanding Real-money authority.

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

## Current authorized next step — WP9A

WP9A is now the only authorized implementation package after accepted WP9 and its successful post-merge Regression Shield.

WP9A goal: establish a single operations contract required before 24/7 use, without silently changing product or money behavior.

WP9A must cover at minimum:

- Windows security updates with a predictable maintenance/reboot window;
- GitHub Runner update health;
- NVIDIA driver update policy;
- PostgreSQL minor/security update policy;
- Ollama runtime/model update policy without prematurely installing/activating the later AI runtime;
- bounded service restart/backoff, crash-loop detection and OWNER alert policy building on accepted WP9 supervision;
- NTP/time-drift monitoring, with dangerous drift fail-closed for future short-lived confirmations, Telegram freshness checks and Real execution;
- CPU/RAM/GPU/VRAM/temperature/disk operating thresholds using accepted node evidence rather than invented capabilities;
- structured logging with a private-data allowlist, masking/omission, rotation/retention, crash-dump policy and audit-log integrity requirements;
- staging/regression/security/eval requirements and documented rollback for any update capable of changing calculations, AI behavior, DB compatibility or broker execution behavior.

WP9A must preserve all accepted WP6–WP9 privilege, secret, supervision, privacy and reboot boundaries. It must not activate later product slots, install the later AI/Cortex stack merely because an update policy exists, start WP10 early, expose secrets/private payloads, weaken CI, or expand Real-money authority.

Only after WP9A Exit Gate passes may WP10 begin.

## Money/safety rule

GitHub access, AI output, research result, Watchtower alert, Telegram message/button, `START V10`, development approval, update availability or model output is never broker-submit authorization.

Current V9 money-path invariants, `app:app`, `trading_methods=false`, secret separation and kill switches remain binding until an explicitly responsible later V10 work package replaces a boundary and passes its Exit Gate.
