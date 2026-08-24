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

Unmerged/closed draft PR text is not accepted authority. Current progress/current-next WP is read only from `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

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

Companions include GitHub utilization, V9→V10 parity, component reuse and release-manifest contracts. Locks GitHub as engineering source of truth, controlled migration rather than greenfield rewrite, reproducibility, release provenance and WP implementation discipline.

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

Locks root-cause-first engineering, all applicable exact-head checks actually `success`, no fake PASS, exact-head invalidation after commits, focused PRs, squash merge, post-merge verification and bounded OWNER handoffs. This governance remains fully active for Amendments 9/10 and subsequent implementation. Its runtime-hosting subsection is updated by Amendment 10 from Personal-Node-final hosting to the managed-cloud/no-home public-production boundary while preserving the V9 Render baseline and OWNER budget discipline.

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

### 11. WP22A Technical Closeout / Public Activation Separation

`OMNI_CIO_V10_WP22A_TECHNICAL_CLOSEOUT_AND_PUBLIC_ACTIVATION_SEPARATION_AMENDMENT.md`

This sequencing amendment records the 2026-08-24 OWNER decision that:

- WP22A may close only after its complete technical External Web Access / Product Authentication Security Gate is implemented and accepted on the reviewed hosted technical boundary;
- the only human product-login protocols are Telegram Login and VK ID; OWNER/admin/developer/demo/preview/private-test/private-external session-minting bypasses are forbidden in deployed product mode;
- deterministic provider doubles are permitted only below the deployed routing/network authority boundary when real secrets/provider-console actions are genuinely non-delegable, and can never become a human login/session bypass;
- technical closeout still requires browser-bound durable pre-auth transactions, provider verification, account/tenant binding, production-grade server-side sessions, application + PostgreSQL tenant isolation, CSRF/origin/host/proxy/cache controls, abuse/capacity behavior, recovery/rollback and exact release evidence;
- final Cloud.ru Evolution provider mutation, real provider secret provisioning/callback registration, real-user public cutover, `PUBLIC_MULTI_USER_ENABLED=true`, recurring paid spend and production privacy/legal/capacity/monitoring approval remain a later independent fail-closed activation gate;
- public T-Invest remains `FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION`, broker write stays OFF, `trading_methods=false` and `REAL_TRADING_ENABLED=false`;
- Amendment 11 does not itself mark Phase 5 accepted, WP22A COMPLETE, WP23 unlocked or the Web visual-refresh runtime authorized.

Amendment 11 narrows sequencing only. Amendments 9 and 10 remain binding for USER identity, tenant isolation, final public/free/managed-cloud product direction and all non-conflicting security/recovery/legal/broker boundaries.

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
8. all active amendments listed here, especially 9, 10 and 11 for product/public-hosting and WP22A sequencing semantics;
9. machine-readable contracts;
10. `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
11. current-WP architecture/runbook;
12. current `main`, open PR/issues and GitHub Actions.
