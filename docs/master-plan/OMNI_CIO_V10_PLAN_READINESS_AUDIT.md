# Omni-CIO V10 — Plan Readiness Audit

Audit date: **2026-08-05**  
Audited branch: **`v10/program-lock`**  
Program state: **0% / DEVELOPMENT NOT STARTED**  
Readiness verdict at this audit: **NOT READY TO START FEATURE IMPLEMENTATION YET**

## 1. Purpose

This is a pre-development release-readiness audit of the V10 plan itself. It does not start V10 implementation and does not change V9 runtime authority.

The goal is to prevent plan defects, contradictory sources of truth and missing safety requirements from being discovered only after Web/Telegram/AI/real-money implementation has already started.

## 2. What is already strong / accepted in the plan

The current V10 program already has the correct high-level sequence and safety architecture:

- V9 remains protected as reference/rollback;
- GitHub is the engineering Control Plane and long-term source of truth;
- Lenovo is the first replaceable runtime node, not the owner of the project architecture;
- Web is one repository-controlled primary application;
- Telegram is an alert/entry surface to the same Core/Web system, not a second financial brain;
- GPT knowledge is migrated before Custom GPT may be retired;
- one shared Omni-CIO AI Copilot/Agent Orchestrator is planned for Web and Telegram;
- AI has no direct broker-write authority;
- evidence, Risk, Optimizer, immutable Plans and execution remain controlled/deterministic boundaries;
- Research uses trusted-source provenance, freshness, contradiction handling and bounded autonomous AI research;
- read-only / Sandbox / Real credentials remain separated;
- Real execution remains immutable-plan, explicit-owner-approved, idempotent, drift-stopped and broker-reconciled;
- Shadow Mode precedes Real execution;
- backup, restore, fault injection, security acceptance, soak testing and disaster recovery are explicit final gates;
- Account Independence / Deployment Portability is a mandatory V10 invariant;
- public multi-user, billing and public Real execution are intentionally excluded from V10 Personal.

## 3. Hard pre-development blockers found

The following items must be corrected before the first V10 feature-development WP is authorized.

### B1 — Mandatory amendment is not yet consolidated into the canonical paired Master Plan

`OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md` is owner-approved mandatory scope, but the hashed canonical Master Plan Markdown/PDF pair still predates this amendment.

The Program Lock and Current Program Status already correctly require consolidation before feature implementation.

**Required fix:** merge the amendment into the canonical Master Plan Markdown, regenerate the owner-readable PDF, regenerate SHA-256 manifest, and remove the split-plan state before starting WP0 feature work.

### B2 — Progress weights are internally inconsistent inside the Master Plan

The authoritative progress table currently totals 100% using:

- A 5
- B 9
- C 12
- D 14
- E 14
- F 8
- G 18
- H 8
- I 7
- J 5

However, several block headings still show older weights (`B 10%`, `C 15%`, `D 15%`, `E 15%`) and Appendix A still contains the pre-AI-amendment weight template including `G 12%`.

**Required fix:** use exactly one weight set everywhere. The current status table above is the canonical 100% allocation unless the owner explicitly changes it.

### B3 — Current-status filename is inconsistent inside the Master Plan

The Master Plan still contains references to `knowledge/V10_CURRENT_PROGRAM_STATUS.md`, while the actual canonical status file is `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

**Required fix:** normalize every program reference to `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

### B4 — Plan status wording is inconsistent

The Master Plan header still says `DRAFT / разработка не начата`, while Program Lock and Current Status say `OWNER-APPROVED / PROGRAM LOCKED / DEVELOPMENT NOT STARTED`.

**Required fix:** after this readiness audit is closed, the canonical Master Plan header/PDF must use one unambiguous planning status. Feature implementation must not start while the canonical artifacts disagree about whether the plan is draft or locked/approved.

### B5 — PR #227 is still draft and is not in accepted `main`

The V10 program exists on `v10/program-lock`; it is not yet the accepted-main program baseline.

**Required fix:** after all plan corrections, paired Markdown/PDF consolidation, regenerated hashes, green exact-head CI and zero unresolved review threads, PR #227 must be owner-accepted and squash-merged before feature-development branches start from the V10 plan.

### B6 — Exact-head Regression Shield is not yet fully green at audit time

Security job is green, but the quality/contracts/coverage job is still running at the time this audit file is written.

**Required fix:** documentation/program-lock head must have the required green exact-head gates before final plan acceptance.

## 4. Important safety details that must become explicit during canonical-plan consolidation

These are not new product features. They are pre-agreed safety/operations acceptance details that should be made explicit so they are not forgotten during implementation.

### S1 — Data-at-rest protection for a lost/stolen Lenovo or SSD

The plan protects secrets and encrypted backups but does not currently make full-disk/private-database at-rest protection explicit.

Add to Node/Security acceptance:

- verify Windows full-disk encryption (for example BitLocker where supported) or an equivalent owner-approved at-rest control;
- define recovery-key ownership/storage separately from GitHub;
- ensure DB, local private Journal/state and secret-store threat model includes physical disk loss.

### S2 — Explicit RPO / RTO targets

Backup/restore is present, but recovery objectives are not quantified.

Add to WP10/WP49:

- target Recovery Point Objective (maximum acceptable private-state loss);
- target Recovery Time Objective (maximum acceptable restoration time);
- backup frequency/retention derived from those targets;
- test evidence against the targets.

Exact numbers may be chosen at WP0/WP10 after hardware/storage audit; the requirement to define and test them is mandatory.

### S3 — External Web ingress / TLS / owner authentication gate

The plan already says external HTTPS ingress is activated only after a security gate and Telegram `initData` must be validated. Before external access is enabled, architecture must explicitly define:

- TLS termination/certificate lifecycle;
- direct-browser OWNER authentication (not only Telegram Mini App identity);
- session lifetime/rotation/revocation;
- CSRF/origin/host controls;
- rate limits for externally reachable auth/API surfaces;
- safe remote-access fallback if public ingress is not needed.

No Real approval surface may be exposed externally before this gate passes.

### S4 — Runtime/OS/model update policy

Dependency policy is strong, but the long-lived Lenovo node also needs an operational patch policy covering:

- Windows security updates/reboot handling;
- GitHub runner updates;
- NVIDIA driver updates;
- PostgreSQL minor/security updates;
- Ollama/model updates and model hash/license provenance;
- rollback after a bad infrastructure/model update.

Updates must be staged/verified rather than automatically changing real-money behavior without regression evidence.

### S5 — Logging/privacy/retention contract

Logs are already required to redact secrets, but V10 should define before production use:

- which portfolio/user/system fields may be logged;
- which fields must always be masked/omitted;
- log retention/rotation;
- crash-dump policy;
- audit-log integrity expectations;
- separation between developer diagnostics and private OWNER financial data.

## 5. External technical-baseline verification performed

The plan's major technology assumptions were checked against current official documentation during this audit:

- GitHub self-hosted runners remain supported and GitHub recommends private repositories for self-hosted runners;
- Telegram Mini Apps still require server-side validation of `initData` and allow freshness checking through `auth_date`;
- Ollama supports tool calling and JSON-schema structured outputs;
- T-Invest documents a read-only token that cannot place trading orders and supports account-specific token scoping;
- OWASP ASVS 5.0.0 is the current stable Web/AppSec verification baseline;
- OWASP AISVS 1.0 is live for AI-enabled security verification;
- React 19.2, Vite 8.1 and PostgreSQL 18.4 are current/supported reference lines at the audit date, but exact versions must still be rechecked at WP2 implementation time.

These checks support the plan direction; they do not replace implementation-time compatibility/security review.

## 6. Readiness rule

The plan may be declared **READY — WAITING FOR OWNER COMMAND TO START V10** only when all B1–B6 are closed and S1–S5 are incorporated into the canonical Master Plan/architecture acceptance criteria.

The final readiness sequence is:

`fix plan inconsistencies -> consolidate all mandatory amendments -> regenerate Markdown/PDF hashes -> exact-head CI green -> zero review blockers -> owner accepts/squash-merges PR #227 -> V10 remains 0% until a separate explicit START V10 command`

## 7. No-development rule

Until this audit is closed:

- do not begin WP0 feature implementation;
- do not create V10 Web/Telegram/AI runtime code;
- do not alter V9 production authority;
- do not enable new Real-money permissions;
- do not start V11 or a competing roadmap.

This audit is governance/documentation only.
