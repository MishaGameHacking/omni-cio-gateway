# Omni-CIO V10 — Plan Readiness Audit

Audit date: **2026-08-05**  
Audited branch: **`v10/program-lock`**  
Program state: **0% / DEVELOPMENT NOT STARTED**  
Readiness verdict: **PLAN CONTENT COMPLETE — FINAL EXACT-HEAD CI + MERGE TO MAIN REQUIRED**

## 1. Purpose

This is the pre-development release-readiness audit of the V10 plan itself. It does not start V10 implementation and does not change V9 runtime authority.

The objective is to prevent contradictory requirements, hidden account dependencies and safety omissions from being discovered only after Web/Telegram/AI/real-money implementation starts.

## 2. Architecture accepted by the audit

The canonical V10 program now explicitly requires:

- V9 retained as protected reference/rollback until V10 final acceptance;
- private GitHub repository as engineering Control Plane/source of truth;
- Lenovo as the first replaceable Personal V10 runtime node, not the architectural owner;
- one repository-controlled Web application and one Omni-CIO Core;
- Telegram as alert/entry surface, not a second financial brain;
- migration of current Custom GPT Instructions/Knowledge/Actions before any decommission;
- one Omni-CIO AI Copilot/Agent Orchestrator shared by Web and Telegram;
- replaceable AI provider with deterministic Core operation when AI is unavailable;
- AI denied direct broker-write authority;
- evidence provenance/freshness/identity binding before strong conclusions;
- Risk/Optimizer/immutable Plan/confirmation/execution as deterministic authority boundaries;
- separated read-only, Sandbox and Real credentials;
- Shadow Mode before Personal Real execution;
- idempotent execution, no automatic retry after possible-submit ambiguity, and broker reconciliation;
- external Web ingress blocked until TLS/OWNER-auth/session/CSRF/origin/host/rate-limit gate passes;
- developer GitHub access separated from broker-secret/real-money authority;
- full-disk/private-state at-rest protection and physical-loss threat handling;
- measurable RPO/RTO and tested backup/restore;
- controlled Windows/runner/NVIDIA/PostgreSQL/Ollama/model update and rollback policy;
- UTC/time-sync/clock-drift controls for timestamps and short-lived approvals;
- logging/privacy/retention/crash-dump/audit-integrity contract;
- AI model provenance, digest/quantization/license/eval/rollback evidence;
- source retrieval/terms/retention governance;
- clean-room Account Independence / Deployment Portability rehearsal;
- final evidence matrix mapping each released capability to implementation/tests/security/runtime/recovery evidence;
- public multi-user, billing and public Real execution intentionally excluded from V10 Personal.

## 3. Findings from the first audit and closure status

### B1 — Account Independence amendment not consolidated

**CLOSED.** The mandatory Account Independence / Deployment Portability requirements are now embedded directly in `OMNI_CIO_V10_MASTER_PLAN.md` and its regenerated PDF. The standalone amendment remains only as historical owner-approved audit evidence.

### B2 — Progress weights inconsistent

**CLOSED.** The canonical allocation is exactly:

| Block | Weight |
|---|---:|
| A | 5% |
| B | 9% |
| C | 12% |
| D | 14% |
| E | 14% |
| F | 8% |
| G | 18% |
| H | 8% |
| I | 7% |
| J | 5% |
| **TOTAL** | **100%** |

Block headings, progress table and status template are normalized to the same allocation.

### B3 — Current-status filename inconsistent

**CLOSED.** Canonical V10 progress authority is only:

`knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`

### B4 — Plan status wording inconsistent

**CLOSED.** Canonical plan status is:

`OWNER-APPROVED / PROGRAM LOCKED / DEVELOPMENT NOT STARTED`

### B5 — Program not yet accepted into `main`

**PROCEDURAL GATE.** PR #227 must be squash-merged after final exact-head CI/security is green and zero review blockers remain. The merge records the plan as accepted-main authority; it does not start implementation.

### B6 — Exact-head Regression Shield

**PROCEDURAL GATE.** Final branch head after cleanup must pass the existing Regression Shield/security checks before merge.

## 4. Safety findings and closure status

### S1 — Data at rest / physical loss

**INCORPORATED.** V10 now requires full-disk encryption (BitLocker where supported or owner-approved equivalent), separate recovery-key custody and physical disk-loss coverage for secrets/private DB/Journal state.

### S2 — RPO / RTO

**INCORPORATED.** WP10/WP49 must define measurable Recovery Point Objective and Recovery Time Objective, derive backup frequency/retention from them and prove restoration against those targets.

### S3 — External Web ingress / TLS / OWNER auth

**INCORPORATED.** WP22A requires explicit decision whether public ingress is needed, TLS/certificate lifecycle, ordinary-browser OWNER authentication, server-side sessions, rotation/revocation, CSRF/Origin/Host/CORS controls, external rate limits and step-up/recent authentication for Real-plan approval.

### S4 — Long-lived node update policy

**INCORPORATED.** Windows, GitHub Runner, NVIDIA driver, PostgreSQL, Ollama and AI model updates are controlled changes with compatibility/security/eval evidence and rollback. Model/runtime auto-update cannot silently change real-money behavior.

### S5 — Logging/privacy/retention

**INCORPORATED.** V10 requires private-data logging allowlists/masking, rotation/retention, crash-dump policy, diagnostic separation and audit-log integrity expectations.

### Additional prevention controls

**INCORPORATED.** Canonical plan additionally covers system clock/NTP drift, UTC timestamp semantics, AI model provenance, external-source terms/retention governance, prompt-injection/RAG/tool escalation boundaries, durable-state health before Real submit and clean-room portability.

## 5. Technical-baseline verification

At the audit date, official documentation was rechecked for the main V10 assumptions. The canonical plan records these as planning references only; exact versions and behavior must be rechecked at the implementation gate rather than assumed forever.

The verification confirmed the continued viability of the selected architecture: GitHub self-hosted runners; Telegram Mini Apps server-side identity validation; Ollama tool calling/structured JSON; T-Invest read-only credential separation; OWASP ASVS/AISVS verification baselines; current stable React/Vite/PostgreSQL lines.

## 6. Canonical artifacts after consolidation

The plan is controlled by:

- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` — searchable canonical plan;
- `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf` — synchronized owner-readable copy;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256` — integrity manifest;
- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md` — precedence/exclusivity/safety lock;
- `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` — progress authority;
- this readiness audit — acceptance evidence;
- `OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md` — historical audit trail, not a competing canonical source.

## 7. Final readiness gate

The substantive content of the V10 plan is complete. The plan becomes formally **READY — WAITING FOR OWNER `START V10` COMMAND** only when all of the following are true on accepted `main`:

1. canonical Markdown/PDF pair and manifest are present;
2. their content/integrity checks pass;
3. temporary plan-generation tooling is removed;
4. exact-head Regression Shield/security is green;
5. no unresolved PR review thread/blocker remains;
6. PR #227 is squash-merged to `main`;
7. V10 progress still reads **0% / DEVELOPMENT NOT STARTED**.

The merge of the plan is documentation/governance acceptance only. **It does not authorize Web/Telegram/AI/runtime feature implementation and does not expand Real-money authority.** A separate explicit owner command is still required to start WP0.
