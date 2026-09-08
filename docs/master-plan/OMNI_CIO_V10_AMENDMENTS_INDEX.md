# Omni-CIO V10 — Amendments Index

Status: **ACTIVE PROGRAM INDEX**

This index exists so future engineering/AI sessions restore OWNER-approved V10 clarifications from GitHub instead of depending on chat memory.

Documentation lifecycle: `../DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`.

## Authority rule

The synchronized V10 Master Plan remains the canonical base program:

- `OMNI_CIO_V10_MASTER_PLAN.md`;
- `Omni-CIO_V10_Master_Plan_RU.pdf`;
- `OMNI_CIO_V10_MASTER_PLAN.sha256`.

Accepted amendments supplement, narrow or explicitly supersede parts of the base plan without silently renumbering blocks or changing block weights. When amendments conflict, the later explicit OWNER-approved amendment governs the conflicting implementation choice. Historical evidence remains historical.

Unmerged/closed draft PR text is not accepted authority. Current progress/current-next execution authority is read only from `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## Active amendments

### 1. Account Independence / Deployment Portability

`OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md`

Historical OWNER-approved amendment already consolidated into the base plan; retained for audit/provenance.

### 2. Concrete Execution Plan / AI Cortex / Autonomy

`OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md`

Companion: `../architecture/V10_AI_CORTEX_CONTRACT.json`.

Locks deterministic Core as financial truth, verified broker-report accounting, bounded research/AI authority, event-driven autonomy, typed tools, recovery and no direct AI broker-write/admin authority. Earlier local-first/Personal-Node assumptions are superseded only where Amendment 10 explicitly changes the final public production topology.

### 3. GitHub Pro / Migration Implementation Contract

`OMNI_CIO_V10_GITHUB_PRO_AND_MIGRATION_IMPLEMENTATION_AMENDMENT.md`

Companions include GitHub utilization, V9→V10 parity, component reuse and release-manifest contracts. Locks GitHub as engineering source of truth, controlled migration rather than greenfield rewrite, reproducibility, release provenance and WP implementation discipline. Amendment 12 supersedes only its one-PR-per-WP delivery-granularity assumption; migration order, parity, reuse, reproducibility and recovery requirements remain active.

### 4. Telegram Product / Interaction / Delivery Contract

`OMNI_CIO_V10_TELEGRAM_PRODUCT_AND_INTERACTION_AMENDMENT.md`

Companions include Telegram product/message registries and implementation checklist. Telegram remains an adapter to the same Core/Web product. Historical OWNER-only product wording is superseded by Amendment 9: final Telegram is USER-scoped to the authenticated Omni-CIO account/tenant.

### 5. Autonomous Portfolio Governance / Zero-Custody / Commercial Model

`OMNI_CIO_V10_AUTONOMOUS_PORTFOLIO_GOVERNANCE_AND_COMMERCIAL_MODEL_AMENDMENT.md`

Companions include governance, sanctions/universe, legal and license/update contracts.

Portfolio-governance, sanctions/custody, optimizer, immutable proposal/approval, Real-execution safeguards and legal gates remain active. Its 7-day trial, fixed-term paid access, premium-expiry behavior and mandatory Personal-Node zero-custody topology are **superseded for the initial public launch where they conflict with Amendment 10**. Future monetization remains deferred optional scope.

### 6. Identity / Multi-Tenant Account / Authentication

`OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md`

Companions:

- `../architecture/ADR-0010-identity-multitenant-authentication.md`;
- `../architecture/V10_IDENTITY_AUTHENTICATION_CONTRACT.json`;
- `../operations/V10_IDENTITY_AND_BROKER_CONNECTION_SECURITY_NOTES.md`.

Locks internal Omni-CIO account identity, Telegram/VK authentication, one-account/one-tenant baseline, server-side sessions, database-enforced tenant isolation and tenant-owned `BrokerConnection` READ/optional TRADE credentials. Its prohibition on a centrally hosted tenant-private data model is superseded only by Amendment 10's explicit managed-cloud public baseline, subject to security/privacy/legal/broker gates.

### 7. Browser-Only Phone Engineering / Headless Node Operations

`OMNI_CIO_V10_PHONE_ONLY_ENGINEERING_AND_HEADLESS_NODE_OPERATIONS_AMENDMENT.md`

Companions:

- `../architecture/V10_PHONE_ONLY_ENGINEERING_CONTRACT.json`;
- `../operations/V10_PHONE_ENGINEERING_RUNBOOK.md`.

Keeps OWNER engineering browser-first and Lenovo headless for CI/recovery. Its earlier interpretation of Lenovo/replacement Personal Node as the final V10 private runtime is superseded for **public production** by Amendment 10. Lenovo remains engineering/self-hosted-CI/acceptance/recovery/rollback and must not be the public availability anchor.

### 8. Engineering Quality / Pre-CI / Green Merge

`OMNI_CIO_V10_ENGINEERING_QUALITY_AND_GREEN_MERGE_AMENDMENT.md`

Machine/governance companions:

- `../architecture/V10_ENGINEERING_QUALITY_GATE_CONTRACT.json`;
- `../operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md`;
- `../operations/V10_CI_COST_CONTROL_STANDARD.md`;
- `../operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`;
- `.github/workflows/v10-engineering-governance.yml` through repository root.

Locks root-cause-first engineering, all applicable exact-head checks actually `success`, no fake PASS, exact-head invalidation after commits, coherent reviewable PRs, squash merge, post-merge verification and bounded OWNER handoffs. This governance remains fully active for later amendments except where Amendment 16 explicitly supersedes its expensive-CI deferral language. Root-cause, blast-radius, exact-head, security/recovery and merge requirements remain active.

### 9. Product User / Engineering Authority Boundary

`OMNI_CIO_V10_PRODUCT_USER_AND_ENGINEERING_AUTHORITY_BOUNDARY_AMENDMENT.md`

Locks the 2026-08-17/18 OWNER decision that PROJECT OWNER is an ordinary product USER on the same `OmniCIOUserAccount -> Tenant -> Session` path, while GitHub/cloud-provider/Windows/CI authority stays outside product identity.

### 10. Public Free Multi-User Hosted Runtime

`OMNI_CIO_V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_AMENDMENT.md`

Machine-readable companion: `../architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json`.

Locks the public modern multi-user Web target, managed-cloud production independent of OWNER home availability, free initial access, tenant-scoped broker credentials, fail-closed public activation and preserved broker/Real-money boundaries.

### 11. WP22A Technical Closeout / Public Production Activation Separation

`OMNI_CIO_V10_WP22A_TECHNICAL_CLOSEOUT_AND_PUBLIC_ACTIVATION_SEPARATION_AMENDMENT.md`

Machine-readable companion: `../architecture/V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_CONTRACT.json`.

Locks technical WP22A acceptance separately from later public-provider/user activation and preserves Telegram/VK-only human authentication plus all tenant/session/security/recovery requirements.

### 12. Integrated System Update Execution Law

`OMNI_CIO_V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_AMENDMENT.md`

Machine/governance companions:

- `../architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json`;
- `../updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md`;
- `.github/ISSUE_TEMPLATE/v10_integrated_system_update.yml` through repository root;
- `../../scripts/check_v10_integrated_system_update_governance.py`;
- `.github/workflows/v10-engineering-governance.yml` through repository root.

Locks `FOCUSED_CHANGE` / `INTEGRATED_SYSTEM_UPDATE`, ordered branch-local member milestones, one integrated branch/final PR by default, accepted-main-only progress, mandatory split triggers, working ledgers/dashboard and exact-main acceptance. Amendment 16 later supersedes only its Single Remote Publication, wait-all HEAD FREEZE and batch-only correction defaults; execution-unit grouping/order/split triggers remain active.

### 13. Live User Operability & Progressive Capability Activation

`OMNI_CIO_V10_LIVE_USER_OPERABILITY_AND_PROGRESSIVE_CAPABILITY_ACTIVATION_AMENDMENT.md`

Machine/governance companions include `../architecture/V10_PROGRESSIVE_CAPABILITY_ACTIVATION_CONTRACT.json`, activation ledger/dashboard and governance guard.

Locks capability states `IMPLEMENTED / LIVE_OPERABLE / BLOCKED_EXTERNAL / REAL_MONEY_AUTHORIZED`, progressive user activation after owning gates, tenant isolation, independent READ capability and preserved Real-money authority.

### 14. Cloudflare Platform & Continuous Release Authority

`OMNI_CIO_V10_CLOUDFLARE_PLATFORM_AND_CONTINUOUS_RELEASE_AUTHORITY_AMENDMENT.md`

Machine/governance companions:

- `../architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json`;
- `../../scripts/check_v10_cloudflare_platform_authority.py`;
- `.github/workflows/v10-engineering-governance.yml` through repository root.

Locks GitHub as engineering/source/review/provenance authority rank 1, Cloudflare Workers Paid as new-V10 managed application/edge/build platform rank 2, continuous exact-main candidate/release identity and preserved PostgreSQL/V9/security boundaries.

### 15. Cloudflare Public Product Integrated Delivery

`OMNI_CIO_V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_DELIVERY_AMENDMENT.md`

Machine/governance companions:

- `../architecture/V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_CONTRACT.json`;
- `../../scripts/check_v10_cloudflare_public_product_integrated.py`;
- `.github/workflows/v10-engineering-governance.yml` through repository root.

Locks current Cloudflare implementation as one `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED` System Update with ordered `CF-A -> CF-B -> CF-C -> CF-D` internal milestones and preserved fail-closed provider/security/cutover boundaries.

### 16. Green Checkpoint & Targeted CI Repair Law

`OMNI_CIO_V10_GREEN_CHECKPOINT_AND_TARGETED_CI_REPAIR_AMENDMENT.md`

Machine/governance companions:

- `../architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json`;
- `../operations/V10_GREEN_CHECKPOINT_CI_RUNBOOK.md`;
- `../../scripts/check_v10_green_checkpoint_ci_repair.py`;
- `../../tests/test_v10_green_checkpoint_ci_repair.py`;
- `.github/workflows/v10-targeted-repair.yml` through repository root;
- `.github/workflows/v10-engineering-governance.yml` through repository root.

Locks the 2026-09-08 OWNER engineering-discipline decision that:

- every published logical checkpoint must become `CERTIFIED_GREEN` before the next functional checkpoint begins;
- any material RED immediately puts the branch in `RED_REPAIR_ONLY`; unrelated feature development is forbidden until repair certification;
- diagnosis starts as soon as useful RED evidence exists and does not wait for all independent jobs merely to begin ordinary repair;
- same-SHA targeted rerun is allowed only when repository source/config is unchanged and the failure is evidence-based transient/infrastructure-only;
- GitHub specific-job rerun is preferred for that unchanged-SHA case;
- code/config/test/governance repair necessarily creates a replacement SHA; old final evidence is stale;
- the same logical checkpoint is repaired by amend/history replacement when safe, or a repair commit when rewrite is unsafe, but no new feature scope is allowed in `RED_REPAIR_ONLY`;
- targeted recheck proves the reported defect; then the replacement exact SHA must receive full applicable certification before new functional work;
- Sonar Quality Gate must pass when applicable, default new-code issues are zero, unresolved new Security Hotspots are zero and material changed-code findings are resolved;
- `PENDING / RED_REPAIR_ONLY / TARGET_REPAIRED / CERTIFIED_GREEN / MAIN_RED_STOP` are the canonical checkpoint states;
- DRAFT→READY does not automatically require duplicate full same-SHA certification unless an applicable state-dependent workflow/ruleset requires it;
- post-merge RED on current `main` means `MAIN_RED_STOP` and blocks ordinary feature progress until an accepted focused repair restores GREEN;
- root-cause, blast-radius, analogous-pattern, producer/consumer, adjacent-failure, regression-guard, SUCCESS-only merge, full review, squash, post-merge, security/recovery, tenant and broker/Real-money laws remain unchanged.

Amendment 16 explicitly supersedes only conflicting CI cadence/publication/wait-all repair language in Amendments 8/12 and live guidance. It does not change execution-unit grouping, Master Plan order/weights, current Cloudflare authority, product scope, activation authority or financial/security boundaries.

## Draft/superseded planning material

Open or historical PR descriptions must not be treated as active plan authority merely because they contain V10 ideas. Closed-unmerged PR #327 is superseded by Amendments 9/10 and is historical only. Older unmerged Personal-Node/cloud migration or OWNER-only external-access planning is likewise non-authoritative when it conflicts with accepted amendments.

## Required reading order for new V10 engineering sessions

1. `../../AGENTS.md`;
2. `../../README.md`;
3. `../DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`;
4. `../../knowledge/00_PROJECT_MASTER_CONTEXT.md`;
5. `OMNI_CIO_V10_PROGRAM_LOCK.md`;
6. `OMNI_CIO_V10_MASTER_PLAN.md`;
7. this Amendments Index;
8. all active amendments listed here, especially 9/10/11/12/13/14/15/16 for current product/public-hosting/delivery/activation/platform/engineering semantics;
9. machine-readable contracts;
10. `OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
11. `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
12. current execution-unit architecture/runbook/ledger when authorized;
13. current `main`, open PR/issues and GitHub Actions.
