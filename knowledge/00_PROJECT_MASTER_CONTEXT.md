# 00 — OMNI-CIO PROJECT MASTER CONTEXT

Дата актуализации: 2026-08-26

Этот файл хранит короткую долговременную память **одного проекта**: защищённого owner-accepted V9 runtime и последовательно развиваемой автономной платформы V10.

**Lifecycle:** long-lived product/context authority, **not a competing progress ledger**. Exact current V10 percentage, accepted WP state and authorized next package are read only from `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` on accepted `main`. Documentation classification: `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`.

## 1. Product identity

Текущий applied production/recovery baseline остаётся:

`Omni-CIO API | Управляющий и аналитик v9.0.0` → protected Gateway `app:app` → protected broker contours.

V9 WP0–WP15 are complete and owner-accepted. Protected V9 remains controlled maintenance/recovery while V10 is built. Do not create a second GPT, duplicate Gateway, competing Web App, second Core or parallel broker/execution stack.

V10 target is one **public modern multi-user Omni-CIO Web product**. A supported USER with ordinary Internet access must eventually be able to open the public HTTPS site from a normal phone/desktop browser, authenticate, and use only that USER's isolated tenant state.

## 2. Current V10 program state

OWNER issued `START V10` on 2026-08-05.

Canonical status is **54% accepted implementation**, WP0–WP22A accepted COMPLETE and **WEB-VISUAL-A** as the current authorized functional package. WP23+ remains locked. This sentence is a convenience snapshot only; `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` is the dynamic authority.

WP22A remains the completed **External Web Access / Product Authentication Security Gate**. Its technical closeout is separate from public-production activation: the latter still owns final Cloud.ru provider apply, production provider secrets/DNS/edge, real public-user cutover and `PUBLIC_MULTI_USER_ENABLED=true`.

The current `WEB-VISUAL-A` package is the Premium Spatial Financial OS **Increment A — Design-system foundation** only. It may update canonical Web tokens/base styling and directly related tests without changing product, identity, tenant, broker or execution semantics. Increment B and WP23 remain out of scope until their own accepted sequence opens them.

## 3. USER versus PROJECT OWNER

Canonical product path:

`OmniCIOUserAccount -> Tenant -> Session -> tenant-scoped product state`

The PROJECT OWNER is not a special Omni-CIO product user/admin. When using Omni-CIO, the PROJECT OWNER is an ordinary USER on the same account/tenant/session path as supported users.

GitHub, CI, cloud-provider, Windows, recovery, legal/business and deployment authority live in an engineering/operations plane outside normal product identity. Such authority never grants a cross-tenant product session or broker-secret access.

## 4. Public production topology

The final public production service must not depend on the PROJECT OWNER's:

- home public IP;
- Wi-Fi/cable/mobile home Internet;
- router/NAT/port forwarding;
- LAN/private subnet;
- Lenovo laptop as production origin;
- home power/Internet availability.

The final public Web/API and required hosted private-data services must run on an **approved managed cloud production runtime** selected through the V10 service-selection/security/recovery process. The selected final production provider remains Cloud.ru Evolution, but provider apply is not authorized by technical WP22A completion.

Lenovo remains important for engineering, authoritative self-hosted CI, controlled acceptance, recovery rehearsal and protected rollback. It is not the public availability anchor.

Cloudflare may be selected for DNS/TLS/WAF/DDoS/edge transport. A Cloudflare Tunnel whose sole production origin is the OWNER's home Lenovo/network does not satisfy the final hosted-product requirement. Provider identity remains engineering authority, not product authentication.

## 5. Identity, tenant isolation and sessions

Ordinary product login methods remain Telegram Login and VK ID, both mapped to the internal Omni-CIO account. Neither provider identity is itself a tenant/business identifier.

One normal account owns one isolated tenant in the baseline model. Tenant scope is derived from authenticated server-side session state, never from a client-supplied user/tenant selector.

Before real public activation, API plus database-enforced tenant isolation and cross-tenant negative tests must remain intact across private records, jobs, queues, caches, notifications, exports, backups/recovery and later AI/RAG memory.

Sessions remain server-side, revocable and protected by Secure/HttpOnly/SameSite cookies, bounded idle/absolute lifetime, fixation protection, rotation, logout and revoke-all semantics.

## 6. Broker credentials are USER/tenant owned

For public V10 there is no global/shared user broker token.

Canonical ownership:

`USER -> Tenant -> BrokerConnection -> READ / TRADE_OPTIONAL -> verified broker account binding`

Each USER enters/replaces/revokes only their own broker credentials through authenticated Web settings. USER A's token must never be usable by Tenant B.

Raw credentials are never returned to the browser after submission, never stored in browser Web Storage, never committed to GitHub/CI/artifacts, and must be encrypted at rest inside the approved tenant-scoped cloud secret/data boundary. Cortex, ordinary CI and unrelated tenants never receive raw broker secrets.

Optional execution remains fail-closed:

`EXECUTABLE_ACCOUNTS = VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`

for the same tenant, with all existing immutable-plan, USER confirmation, preflight, idempotency, reconciliation, own-cash/own-position and no-transfer/no-margin safeguards.

`trading_methods=false` and `REAL_TRADING_ENABLED=false` remain unchanged until their owning accepted execution gates explicitly change them.

## 7. Free initial launch

Initial public USER access is free:

- `BILLING_ENABLED=false`;
- `TRIAL_ENABLED=false`;
- `SUBSCRIPTION_ENFORCEMENT=false`;
- `PREMIUM_FEATURE_GATING=false`;
- no payment method required for registration/login;
- no 7-day trial or 1/3/6/12-month entitlement required for initial access.

Earlier paid/trial architecture is retained as historical/future optional planning only. Future monetization is `DEFERRED_OPTIONAL` and requires a new explicit OWNER-approved decision plus applicable legal/payment implementation.

Infrastructure costs are separate engineering/provider budget decisions and do not mean users are charged.

## 8. T-Invest public-service gate

Current official T-Invest API terms/FAQ keep public T-Invest-backed production functionality behind a separate fail-closed broker-permission gate. A user-supplied token does not by itself waive broker terms.

Therefore public Omni-CIO Web/account technical acceptance and public T-Invest connector activation remain separate gates. Until a contractually valid broker/partner permission or another explicitly accepted compliant architecture exists, T-Invest-backed public production functionality remains fail-closed.

## 9. Deterministic Core / Cortex

V10 remains a controlled V9→V10 productization, not a greenfield rewrite.

Deterministic Core owns financial/accounting truth, exact calculations, permissions and money-path enforcement. Cortex owns bounded research, explanation, orchestration and user interaction where useful; it never receives direct broker-write/admin/bypass authority or raw TRADE secrets.

Canonical migration preference remains:

`REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`.

## 10. GitHub and engineering process

Repository: `MishaGameHacking/omni-cio-gateway`.

GitHub is engineering source of truth. Significant work follows:

`restore accepted authority -> one current WP/defect -> focused branch -> root-cause/blast-radius preflight -> implementation/tests -> full diff -> all applicable exact-head checks SUCCESS -> zero blockers -> squash merge -> exact main -> post-merge Regression Shield -> status/acceptance -> next WP`.

Red is red. Skipped/pending/queued is not PASS. OWNER physical/secret evidence is never synthesized. OWNER participation is limited to genuinely non-delegable account/consent/secret/admin/physical decisions.

WP22A technical closeout has its own immutable acceptance evidence. Current development may proceed only as `WEB-VISUAL-A`; public activation, final provider mutation, broker-write expansion, Increment B and WP23 remain independently gated.

## 11. Authority navigation

Always restore context from:

- `AGENTS.md`;
- `README.md`;
- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`;
- `docs/master-plan/OMNI_CIO_V10_PRODUCT_USER_AND_ENGINEERING_AUTHORITY_BOUNDARY_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_AMENDMENT.md`;
- `docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json`;
- `docs/architecture/V10_WP22A_PHASE5_TECHNICAL_ACCEPTANCE_EVIDENCE.md`;
- `docs/architecture/V10_WEB_VISUAL_DESIGN_REFRESH_IMPLEMENTATION_BRIEF.md`;
- `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
- current package architecture/security/recovery files;
- current `main`, open PRs/issues and GitHub Actions.

Chat memory, screenshots, stale PR descriptions and historical package records never override accepted GitHub authority.
