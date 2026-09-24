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

Locks root-cause-first engineering, all applicable exact-head checks actually `success`, no fake PASS, exact-head invalidation after commits, coherent reviewable PRs, squash merge, post-merge verification and bounded OWNER handoffs. This governance remains fully active for Amendments 9/10/11/12/13/14/15 and subsequent implementation. Amendment 12 changes only delivery granularity: “focused PR” means one coherent PR per authorized execution unit rather than mandatory one PR per individual member WP/increment. Amendment 13 changes only user-capability activation granularity and does not weaken exact-head/security/Real-money gates. Amendment 14 changes current/future V10 managed-platform authority without weakening V9 rollback or the same GREEN/review law. Amendment 15 changes only the delivery granularity of the already-selected Cloudflare implementation and preserves the same exact-head/review/security law.

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
- current T-Invest public-service terms remain a separate fail-closed broker gate: user-supplied tokens do not waive broker restrictions;
- payment/KKT gates are not required merely for free access, but become applicable if monetization is later enabled.

Amendment 10 explicitly supersedes conflicting Personal-Node-final-product, permanent-private, initial-paid-access and central-private-data prohibitions in Amendments 5/6/7 and older WP22A wording. Non-conflicting safety, tenant isolation, legal, broker separation, recovery and engineering rules remain active. Amendment 13 later supersedes only the assumption that all normal user capabilities must wait for one monolithic final activation event. Amendment 14 later selects Cloudflare Workers Paid as the new-V10 managed application/edge/build target while preserving the no-home/public-hosting and security requirements recorded here.

### 11. WP22A Technical Closeout / Public Production Activation Separation

`OMNI_CIO_V10_WP22A_TECHNICAL_CLOSEOUT_AND_PUBLIC_ACTIVATION_SEPARATION_AMENDMENT.md`

Machine-readable companion:

`../architecture/V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_CONTRACT.json`

Locks the 2026-08-24 OWNER sequencing correction that:

- WP22A may close its complete technical External Web Access / Product Authentication Security Gate on the accepted hosted technical/synthetic boundary without first purchasing/applying final production infrastructure or provisioning OWNER-held production provider secrets;
- exactly Telegram Login and VK ID remain the only human product-authentication protocols, and no OWNER/admin/developer/demo/preview/private session-minting bypass may exist in deployed product mode;
- deterministic provider doubles are permitted only below deployed routing/network boundaries and may never become a human-accessible session issuer;
- the technical gate still requires browser-bound durable pre-auth, provider mix-up/replay defenses, internal account/tenant/session composition, tenant/RLS negatives, browser/API security, abuse/capacity controls, recovery, rollback and exact release evidence;
- final provider apply, real provider provisioning, production DNS/edge/public-user cutover, `PUBLIC_MULTI_USER_ENABLED=true` and production legal/operations acceptance remain a later independent fail-closed activation gate;
- the accepted 2026-08-24 Cloud.ru/Render provider wording is historical and is superseded for new V10 provider selection by Amendment 14 without rewriting WP22A evidence;
- public T-Invest remains fail-closed, broker write remains OFF, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, WP23 remains locked and protected V9 `app:app` rollback remains intact;
- Amendment 11 changes sequencing only and does not weaken Amendments 9/10, mark WP22A complete or authorize the visual-refresh runtime by itself.

Amendment 13 later decomposes the monolithic activation interpretation into capability-specific activation gates. Amendment 14 changes current/future provider authority only; neither amendment fabricates provider/legal/operations evidence or activates a capability by itself.

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
- the prepared first product integrated update is `WEB-VISUAL-INTEGRATED` with ordered `WEB-VISUAL-A -> B -> C -> D -> E -> F -> G` member milestones;
- acceptance of Amendment 12 itself does **not** start product work: canonical post-acceptance state is `PRODUCT IMPLEMENTATION PAUSED`, `OWNER START REQUIRED`, and the exact command is `START V10 WEB VISUAL SYSTEM UPDATE`;
- protected `app:app`, `PUBLIC_MULTI_USER_ENABLED=false`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, broker write OFF, tenant isolation, secret exclusion, squash merge and exact-head SUCCESS-only policy remain unchanged at Amendment-12 acceptance.

Amendment 12 supersedes only conflicting **delivery granularity** wording in Program Lock Section 7, Amendment 3, Amendment 8 and Visual Refresh Brief Section 17. It does not reorder the Master Plan, change block weights, alter product scope or unlock a later major System Update. Amendment 13 later changes only the future activation granularity of completed user-facing capabilities; Amendment 14 uses its mandatory split triggers for provider/security authority, build integration, runtime compatibility and production cutover. Amendment 15 later supersedes only the four-separate-merge delivery granularity for the selected Cloudflare transition while preserving those ordered internal authority gates and all real split triggers.

### 13. Live User Operability & Progressive Capability Activation

`OMNI_CIO_V10_LIVE_USER_OPERABILITY_AND_PROGRESSIVE_CAPABILITY_ACTIVATION_AMENDMENT.md`

Machine/governance companions:

- `../architecture/V10_PROGRESSIVE_CAPABILITY_ACTIVATION_CONTRACT.json`;
- `../updates/V10_CAPABILITY_ACTIVATION_LEDGER_TEMPLATE.md`;
- `.github/ISSUE_TEMPLATE/v10_capability_activation.yml` through repository root;
- `../../scripts/check_v10_progressive_capability_activation.py`;
- `.github/workflows/v10-engineering-governance.yml` through repository root.

Locks the 2026-08-27 OWNER activation-policy decision that:

- one canonical Omni-CIO Web is the ordinary real-user product surface; a second user-facing staging product is not required merely to test completed capability behavior;
- engineering CI/provider doubles/Sandbox/Shadow remain allowed safety contours but never become an auth/tenant bypass or a second product;
- implemented user-facing capabilities use exact states `IMPLEMENTED / LIVE_OPERABLE / BLOCKED_EXTERNAL / REAL_MONEY_AUTHORIZED`;
- a capability whose own technical/security/external gates pass becomes `LIVE_OPERABLE` without waiting unrelated future blocks or final `V10.0.0`;
- “V10 is not finished” is not a valid external blocker;
- Telegram Login, VK ID and multi-user access may activate progressively after their own real-provider/runtime/privacy/capacity/monitoring gates;
- T-Invest READ/live portfolio/positions/operations are independent of unfinished Real execution and may become `LIVE_OPERABLE` after real broker-terms/permission plus tenant secret-custody/security/privacy/live-connection acceptance;
- a future tenant-scoped TRADE credential may be connected/validated after its own provisioning/security gate, but `TRADE credential connected != real broker submit authorized`;
- execution eligibility remains `VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`;
- real broker submit requires `REAL_MONEY_AUTHORIZED` after Shadow/Sandbox, immutable plan, USER approval, drift/preflight, reconciliation, kill switches and actual broker permission;
- transfer/withdrawal, margin/leverage and uncovered-short authority remain outside this activation freedom;
- real-user operability and multi-user isolation become part of Definition of Done where live proof is possible;
- emergency kill switches remain safety mechanisms, not permanent artificial locks after a capability's gates pass;
- capability activation ledger/dashboard are working evidence only and never replace canonical current status;
- Amendment 13 itself is governance-only: current `PUBLIC_MULTI_USER_ENABLED=false`, broker write OFF, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and public T-Invest fail-closed state remain unchanged until later capability-specific gates actually accept a transition;
- product implementation remains PAUSED and `START V10 WEB VISUAL SYSTEM UPDATE` remains required before WEB-VISUAL-INTEGRATED source work.

Amendment 13 explicitly supersedes only conflicting **activation granularity/timing** wording in Amendments 10/11/12 and live guidance. It does not change Master Plan order/weights, fabricate provider/broker/legal/privacy evidence, authorize Real money, weaken tenant/security/recovery boundaries or start any product System Update. Amendment 14 later changes managed-platform/cost authority while preserving this capability-specific fail-closed activation law.

### 14. Cloudflare Platform & Continuous Release Authority

`OMNI_CIO_V10_CLOUDFLARE_PLATFORM_AND_CONTINUOUS_RELEASE_AUTHORITY_AMENDMENT.md`

Machine/governance companions:

- `../architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json`;
- `../../scripts/check_v10_cloudflare_platform_authority.py`;
- `.github/workflows/v10-engineering-governance.yml` through repository root.

Locks the 2026-08-29 OWNER provider/release correction that:

- GitHub remains engineering/source/review/provenance authority rank 1;
- Cloudflare Workers Paid is platform rank 2 and the selected primary managed application/edge/build target for **new V10 work**;
- Cloud.ru Evolution is no longer the selected new-V10 provider target;
- Render is no longer an active new-V10 deployment, zero-charge attestation, hosted-release-alignment or recovery target;
- accepted WP22A Render/Neon evidence remains historical technical evidence and protected V9 Render `app:app` remains intact;
- Amendment 14 acceptance itself performs no Cloudflare deploy, DNS/domain mutation, API-token/secret creation, public-user activation or production cutover;
- each accepted protected `main` SHA becomes a new product revision candidate, but promotion occurs only after exact-main post-merge and candidate acceptance gates;
- production remains last-known-good and visibly out-of-sync when a newer `main` is not promotable;
- public release identity uses event-derived CalVer `YYYY.MM.DD.N` plus exact source SHA/Cloudflare version metadata without a source-code version-bump commit;
- one canonical Web/product identity stack remains mandatory; Cloudflare Access/security never becomes Omni-CIO product identity;
- existing React/Vite and FastAPI/PostgreSQL architecture is migrated by reuse/adapter preference, with Python Worker/native-dependency and PostgreSQL 18/Hyperdrive compatibility proved rather than assumed;
- Workers Paid included build capacity may be used after the dedicated repository integration gate, while mutable limits must be revalidated and automatic paid overage/higher-plan expansion is forbidden without fresh OWNER approval;
- portable verification targets Workers Builds after integration, while Windows/PowerShell/ACL/PostgreSQL-18-native semantics remain on trusted Lenovo runners until equivalent semantics are accepted;
- the original mandatory split sequence is `CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION -> CLOUDFLARE-RUNTIME-COMPATIBILITY -> CLOUDFLARE-CANDIDATE-DEPLOYMENT -> CLOUDFLARE-PUBLIC-CUTOVER`;
- `PUBLIC_MULTI_USER_ENABLED=false`, broker write OFF, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and WP23 lock remain unchanged by this governance amendment.

Amendment 14 supersedes conflicting **current/future provider-selection, active Render release-target and monolithic public-release timing** wording in Amendments 8/10/11/13 and current guidance. It does not erase historical evidence, change Master Plan block weights/order, start WEB-VISUAL source work, fabricate external provider/legal evidence or authorize Real-money execution. Amendment 15 supersedes only the requirement to land the four Cloudflare implementation stages as four separately accepted main states; their order, internal gates, security/runtime/provider boundaries and continuous-release law remain active.

### 15. Cloudflare Public Product Integrated Delivery

`OMNI_CIO_V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_DELIVERY_AMENDMENT.md`

Machine/governance companions:

- `../architecture/V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_CONTRACT.json`;
- `../../scripts/check_v10_cloudflare_public_product_integrated.py`;
- `.github/workflows/v10-engineering-governance.yml` through repository root.

Locks the 2026-08-29 OWNER delivery correction that:

- current Cloudflare implementation is one `INTEGRATED_SYSTEM_UPDATE` named `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`;
- default implementation branch is `system/cloudflare-public-product`;
- one final PR is the default;
- `CF-A / CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION -> CF-B / CLOUDFLARE-RUNTIME-COMPATIBILITY -> CF-C / CLOUDFLARE-CANDIDATE-DEPLOYMENT -> CF-D / CLOUDFLARE-PUBLIC-CUTOVER` remains the mandatory internal order;
- each internal milestone must pass its branch-local Exit Gate before dependent work begins;
- separate protected-main merge/acceptance between CF-A…CF-D is not required;
- any concrete Amendment-12 DB/security/dependency/OWNER/live/cutover/Real-money/reviewability split trigger still forces a stop/split;
- prefer appropriate Cloudflare services over replaceable external infrastructure only when semantics, security, recovery and cost remain acceptable;
- existing React/Vite targets Workers Static Assets, while Python Workers require dependency compatibility proof and Cloudflare Containers may be used only for a proven full-Linux/native runtime need;
- D1 does not silently replace financial PostgreSQL; PostgreSQL/Neon 18/RLS may remain until an explicit equivalent migration is proved; Hyperdrive PG18 compatibility is not assumed;
- active new-V10 Render code/config/dependencies are retired only after replacement parity plus consumer/recovery review; historical WP22A Render/Neon evidence and protected V9 Render `app:app` stay preserved;
- GitHub remains engineering authority rank 1; no paid overage/higher-plan expansion is authorized by this amendment;
- public capability activation remains evidence-based and fail-closed; broker write, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and WP23 lock remain unchanged;
- `WEB-VISUAL-INTEGRATED` is excluded and still requires the exact separate OWNER command `START V10 WEB VISUAL SYSTEM UPDATE`.

Amendment 15 supersedes only conflicting **Cloudflare implementation delivery granularity** from Amendment 14/current guidance. It does not weaken the internal order, candidate/public-cutover authority gates, continuous exact-main release law, protected V9 recovery, tenant/data/security rules or Real-money locks.

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

### 17. Russian PostgreSQL Data-Residency Migration Authority

`OMNI_CIO_V10_RU_POSTGRES_DATA_RESIDENCY_MIGRATION_AMENDMENT.md`

Machine/governance companions:

- `../architecture/V10_RU_POSTGRES_DATA_RESIDENCY_MIGRATION_CONTRACT.json`;
- `../../scripts/check_v10_ru_postgres_data_residency_migration.py`;
- `../../tests/test_v10_ru_postgres_data_residency_migration.py`;
- issue #559;
- `.github/workflows/v10-engineering-governance.yml` through repository root.

Locks the 2026-09-19 OWNER data-residency/provider-migration direction that:

- preserve PostgreSQL 18, migrations, tenant isolation, RLS/FORCE RLS and logical recovery rather than rewriting the persistence layer;
- prove Timeweb Cloud Managed PostgreSQL 18 in a Russian region as the first replacement candidate;
- do not accept the minimum Timeweb tariff merely because it is cheapest when it cannot prove the separate least-privilege runtime identity;
- keep current Neon production authority until explicit equivalent migration/cutover evidence exists;
- use synthetic data only before accepted production cutover;
- execute the migration through mandatory split stages RU-PG-A -> RU-PG-B -> RU-PG-C -> RU-PG-D -> RU-PG-E;
- preserve Cloudflare application/edge/build authority while replacing only the PostgreSQL provider adapter after proof;
- retain all public-user, Telegram/VK, broker-write, Real-money, V9 recovery and WEB-VISUAL locks.

Amendment 17 supersedes only the assumption that Neon is the permanent future production PostgreSQL provider. It does not self-certify Russian legal compliance, activate users, authorize provider purchase by itself, weaken security roles/RLS/recovery or erase historical Neon evidence.


### 18. Timeweb-Only Platform Consolidation & Telegram-Only Login Authority

`OMNI_CIO_V10_RU_PUBLIC_REGISTRATION_AND_RUSSIAN_INGRESS_AMENDMENT.md`

Machine/governance companions:

- `../architecture/V10_RU_PUBLIC_REGISTRATION_INGRESS_CONTRACT.json`;
- `../../scripts/check_v10_ru_public_registration_ingress.py`;
- `../../tests/test_v10_ru_public_registration_ingress.py`;
- issue #580;
- database migration issue #559;
- Telegram activation issue #549;
- `.github/workflows/v10-engineering-governance.yml`.

Locks the 2026-09-21 OWNER final simplification direction:

- active general service set = ChatGPT + GitHub + Timeweb Cloud + Telegram Login;
- GitHub remains source/review/CI/release-provenance authority;
- Timeweb Cloud is the only selected future/current V10 production infrastructure platform;
- Timeweb Managed PostgreSQL 18 is the final relational authority;
- Telegram Login is the only selected human product login provider;
- Cloudflare, Neon, Render, Cloud.ru and VK ID are retirement targets and receive no new feature authority;
- external CI/review SaaS must be replaced by equivalent-or-stronger GitHub-executed checks before removal;
- `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED` is the next authorized System Update after this amendment is accepted;
- one integrated source branch is preferred, while database cutover, DNS/public cutover, external-provider decommission, OWNER/legal actions and recovery boundaries remain mandatory independent acceptance gates;
- historical provider files remain archive-in-place by default; after accepted cutover their live actions/required-check role/secrets may be disabled or revoked without mass repository deletion;
- protected Git history is not rewritten.

Amendment 18 supersedes Amendments 14/15 only for current/future provider selection and release target. Their accepted Cloudflare evidence remains historical. It also narrows human product login from Telegram/VK to Telegram only. It does not activate users, mutate providers or authorize Real money.

### 19. Timeweb No-OWNER-Laptop Manual Dependency

`OMNI_CIO_V10_TIMEWEB_NO_OWNER_LAPTOP_DEPENDENCY_AMENDMENT.md`

Machine/governance companions:

- `../architecture/V10_TIMEWEB_NO_OWNER_LAPTOP_DEPENDENCY_CONTRACT.json`;
- `../../scripts/check_v10_timeweb_no_owner_laptop_dependency.py`;
- `../../tests/test_v10_timeweb_no_owner_laptop_dependency.py`;
- `.github/workflows/v10-wp17-owner-read-vault-audit.yml`;
- `.github/workflows/v10-wp17-local-read-vault-historical-audit.yml`.

Locks the 2026-09-23 OWNER direction that Timeweb consolidation must not require manual Administrator-shell work on the OWNER laptop merely to advance a PR. The Windows WP17 READ-vault/ACL evidence remains historical/local-only. Current Timeweb source must not depend on that vault, live broker credential mutation remains fail-closed until hosted tenant secret custody is accepted, and the required WP17 check becomes a deterministic hosted source-security audit rather than a machine-local ACL proof. This amendment does not activate public users, broker write, Real money, WEB-VISUAL or WP23+.

### 20. V9-to-V10 Convergence and Legacy Working-Tree Retirement

`OMNI_CIO_V10_V9_TO_V10_CONVERGENCE_AND_LEGACY_RETIREMENT_AMENDMENT.md`

Machine/governance companions:

- `../architecture/V10_V9_TO_V10_CONVERGENCE_CONTRACT.json`;
- `../../scripts/check_v10_v9_to_v10_convergence.py`;
- `../../tests/test_v10_v9_to_v10_convergence.py`;
- `.github/workflows/v10-engineering-governance.yml`;
- `../updates/TIMEWEB_PLATFORM_CONSOLIDATION_EXECUTION_LEDGER.md`.

Locks the 2026-09-24 OWNER direction that accepted V9 behavior is migrated into the
single forward V10/Timeweb runtime inside PR #584. The accepted V9 target is already in
the main lineage, so stale `v9/*` branches are not merged. Remaining useful
root-level source is reused/extracted into canonical V10 packages before legacy
working-tree paths are deleted; Git history remains the archive. The internal sequence
is V9C-A through V9C-F, and PR #584 still requires a new explicit OWNER instruction
before merge to `main`. This amendment does not activate public users, deploy TW-C,
cut over production data/DNS, authorize broker write/Real money, start WEB-VISUAL or
unlock WP23+.

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
8. all active amendments listed here, especially 9/10/11/12/13/14/15/16/17/18/19/20 for current product/public-hosting/delivery/activation/platform/engineering/data-residency/Russia-ingress/convergence semantics;
9. machine-readable contracts;
10. `OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
11. `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
12. current execution-unit architecture/runbook/ledger when authorized;
13. current `main`, open PR/issues and GitHub Actions.
