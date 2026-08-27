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

Locks root-cause-first engineering, all applicable exact-head checks actually `success`, no fake PASS, exact-head invalidation after commits, coherent reviewable PRs, squash merge, post-merge verification and bounded OWNER handoffs. This governance remains fully active for Amendments 9/10/11/12 and subsequent implementation. Amendment 12 changes only delivery granularity: “focused PR” means one coherent PR per authorized execution unit rather than mandatory one PR per individual member WP/increment. Its runtime-hosting subsection is updated by Amendment 10 from Personal-Node-final hosting to the managed-cloud/no-home public-production boundary while preserving the V9 Render baseline and OWNER budget discipline.

### 9. Product User / Engineering Authority Boundary

`OMNI_CIO_V10_PRODUCT_USER_AND_ENGINEERING_AUTHORITY_BOUNDARY_AMENDMENT.md`

Locks the 2026-08-17/18 OWNER decision that:

- PROJECT OWNER is not a special Omni-CIO product role;
- PROJECT OWNER uses the same `OmniCIOUserAccount -> Tenant -> Session` path as every supported USER;
- GitHub/cloud-provider/Windows/CI authority stays outside product identity;
- WP22 `/system` is USER-facing diagnostics, not a cross-tenant OWNER/admin cabinet;
- WP22A is interpreted as **External Web Access / Product Authentication Security Gate**;
- Telegram and product-domain approval/negotiation are USER-scoped;
- provider/edge identity must not silently mint/select an Omni-CIO tenant session.

This amendment carries forward the valid intent of closed-unmerged PR #327; that PR itself is historical and not accepted authority.

### 10. Public Free Multi-User Hosted Runtime

`OMNI_CIO_V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_AMENDMENT.md`

Machine-readable companion:

`../architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json`

Locks the 2026-08-18 OWNER launch direction:

- final product is a public modern multi-user Web service reachable from ordinary Internet browsers/phones;
- one account = one USER = one isolated tenant baseline;
- public production must not depend on OWNER home public IP, Wi-Fi, router, LAN, cable/mobile uplink or Lenovo;
- final production origin is an approved managed cloud runtime selected through the service-selection gate;
- Lenovo remains engineering/self-hosted CI/controlled acceptance/recovery/rollback, not public production availability;
- initial registered-user access is free: `BILLING_ENABLED=false`, `TRIAL_ENABLED=false`, `SUBSCRIPTION_ENFORCEMENT=false`, `PREMIUM_FEATURE_GATING=false`;
- future monetization is `DEFERRED_OPTIONAL`, not part of initial access;
- each USER enters/replaces/revokes their own tenant-scoped broker READ and optional TRADE credentials in authenticated Web settings;
- no broker credential is global/shared across users or returned to the browser after submission;
- READ/TRADE exact broker-account intersection and all Real-money safeguards remain fail-closed;
- managed hosted tenant-private state/secret custody is allowed only after exact security/privacy/personal-data/broker/legal gates accept the design;
- public multi-user is now the approved **target**, while `PUBLIC_MULTI_USER_ENABLED=false` remains the implementation default until the corrected WP22A/launch gates pass;
- current T-Invest public-service terms remain a separate fail-closed gate: user-supplied tokens do not waive broker restrictions;
- payment/KKT gates are not required merely for free access, but become applicable if monetization is later enabled.

Amendment 10 explicitly supersedes conflicting Personal-Node-final-product, permanent-private, initial-paid-access and central-private-data prohibitions in Amendments 5/6/7 and older WP22A wording. Non-conflicting safety, tenant isolation, legal, broker separation, recovery and engineering rules remain active.

### 11. WP22A Technical Closeout / Public Production Activation Separation

`OMNI_CIO_V10_WP22A_TECHNICAL_CLOSEOUT_AND_PUBLIC_ACTIVATION_SEPARATION_AMENDMENT.md`

Machine-readable companion:

`../architecture/V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_CONTRACT.json`

Locks the 2026-08-24 OWNER sequencing correction that:

- WP22A may close its complete technical External Web Access / Product Authentication Security Gate on the accepted hosted technical/synthetic boundary without first purchasing/applying final production infrastructure or provisioning OWNER-held production provider secrets;
- exactly Telegram Login and VK ID remain the only human product-authentication protocols, and no OWNER/admin/developer/demo/preview/private session-minting bypass may exist in deployed product mode;
- deterministic provider doubles are permitted only below deployed routing/network boundaries and may never become a human-accessible session issuer;
- the technical gate still requires browser-bound durable pre-auth, provider mix-up/replay defenses, internal account/tenant/session composition, tenant/RLS negatives, browser/API security, abuse/capacity controls, recovery, rollback and exact release evidence;
- final Cloud.ru Evolution apply, real provider provisioning, production DNS/edge/public-user cutover, `PUBLIC_MULTI_USER_ENABLED=true` and production legal/operations acceptance remain a later independent fail-closed activation gate;
- current recurring infrastructure authority remains `0 RUB/month` / `0 USD/month`, provider apply remains forbidden and automatic paid fallback remains forbidden;
- public T-Invest remains fail-closed, broker write remains OFF, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, WP23 remains locked and protected V9 `app:app` rollback remains intact;
- Amendment 11 changes sequencing only and does not weaken Amendments 9/10, mark WP22A complete or authorize the visual-refresh runtime by itself.

### 12. Integrated System Update Execution Law

`OMNI_CIO_V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_AMENDMENT.md`

Machine/governance companions:

- `../architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json`;
- `../updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md`;
- `.github/ISSUE_TEMPLATE/v10_integrated_system_update.yml` through repository root;
- `../../scripts/check_v10_integrated_system_update_governance.py`;
- `.github/workflows/v10-engineering-governance.yml` through repository root.

Locks the 2026-08-26 OWNER delivery-discipline decision that:

- each material change is either `FOCUSED_CHANGE` or `INTEGRATED_SYSTEM_UPDATE`;
- an integrated update keeps ordered WP/increments as branch-local internal milestones while using one integrated branch and one final PR by default;
- accepted V10 progress changes only after final squash merge plus required exact-main post-merge acceptance;
- integrated work is not published for external verification before `INTEGRATION_READY`;
- after a verification SHA is published, **HEAD FREEZE** applies while the safe independent verification batch reaches terminal state;
- RED findings are consolidated and diagnosed by root cause/blast radius before one coherent correction batch; symptom-by-symptom CI iteration is not the default;
- temporary verifier commits/PRs and `continue-on-error` fake GREEN are forbidden;
- every integrated update has a branch Execution Ledger and GitHub-visible System Update dashboard, both explicitly non-authoritative for accepted progress;
- mandatory split triggers preserve DB/migration sequencing, security/authority changes, dependency/toolchain boundaries, OWNER/provider actions, live/temporal evidence, production cutover, Real-money authority and reviewability;
- the prepared first integrated update is `WEB-VISUAL-INTEGRATED` with ordered `WEB-VISUAL-A -> B -> C -> D -> E -> F -> G` member milestones;
- acceptance of Amendment 12 itself does **not** start product work: canonical post-acceptance state is `PRODUCT IMPLEMENTATION PAUSED`, `OWNER START REQUIRED`, and the exact command is `START V10 WEB VISUAL SYSTEM UPDATE`;
- protected `app:app`, `PUBLIC_MULTI_USER_ENABLED=false`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, broker write OFF, tenant isolation, secret exclusion, squash merge and exact-head SUCCESS-only policy remain unchanged.

Amendment 12 supersedes only conflicting **delivery granularity** wording in Program Lock Section 7, Amendment 3, Amendment 8 and Visual Refresh Brief Section 17. It does not reorder the Master Plan, change block weights, alter product scope or unlock a later major System Update.

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
8. all active amendments listed here, especially 9/10/11/12 for current product/public-hosting/delivery semantics;
9. machine-readable contracts;
10. `OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
11. `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
12. current execution-unit architecture/runbook/ledger when authorized;
13. current `main`, open PR/issues and GitHub Actions.
