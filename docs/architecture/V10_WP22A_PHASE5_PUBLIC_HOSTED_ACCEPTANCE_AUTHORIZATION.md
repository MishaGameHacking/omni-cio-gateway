# Omni-CIO V10 — WP22A Phase 5 Technical Closeout Authorization

Status: **WP22A TECHNICAL CLOSEOUT AUTHORIZED / PUBLIC PRODUCTION ACTIVATION LOCKED / PROVIDER COST APPLY FAIL-CLOSED**
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**
Sequencing authority: `../master-plan/OMNI_CIO_V10_WP22A_TECHNICAL_CLOSEOUT_AND_PUBLIC_ACTIVATION_SEPARATION_AMENDMENT.md`

## Purpose

This contract authorizes one integrated Phase-5 implementation package after Amendment 11 is accepted on protected `main`.

Phase 5 closes the complete technical browser/product-auth/session/tenant/security/recovery boundary on the accepted hosted technical environment. A separate later gate owns final Cloud.ru Evolution apply, real provider secret provisioning, production DNS/edge mutation and real public-user activation.

The normal product path remains:

`ordinary Internet browser -> hosted HTTPS Omni-CIO Web/BFF -> Telegram Login or VK ID -> verified external identity -> OmniCIOUserAccount -> Tenant -> server-side Session -> tenant-scoped product state`

Provider/GitHub/Windows/CI authority remains outside product identity. The PROJECT OWNER is an ordinary product USER when using Omni-CIO.

## Accepted prerequisite

Phase 4 is accepted only through `V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.md`, its machine-readable contract and the exact-head public acceptance workflow. PR #386 is accepted only through exact protected main `bda8f51ad495520a92bd2715182684e216f76000` plus Regression Shield #1532 / run `32760188417` with both required jobs completed `success`.

Amendment 11 becomes authority only after its own exact-head GREEN PR, squash merge and exact-new-main Regression Shield. No integrated implementation branch may treat an unmerged amendment as source authority.

## WP22A technical-closeout acceptance

Phase 5 may implement and verify the complete technical surface needed to close WP22A:

1. one hosted React/FastAPI/PostgreSQL Web/BFF product, with no second frontend/API/identity/database stack;
2. exactly Telegram Login and VK ID as human product-authentication protocols;
3. browser-bound, one-time, durable/shared pre-auth transactions with protected state/proof material, server-side PKCE verifier/nonce, exact provider/redirect binding, expiry, capacity and atomic consume;
4. provider-specific fixed start/callback trust boundaries, mix-up/replay/browser-swapping defenses and hardened Telegram JWKS concurrency/key rotation;
5. verified external identity -> internal account -> isolated tenant -> persistent server-side session composition;
6. opaque session lifecycle with fixation protection, fresh issuance/rotation, bounded idle/absolute lifetime, logout and true revoke-all;
7. tenant authority derived only from authenticated server-side session state plus application and PostgreSQL RLS/FORCE-RLS enforcement;
8. deployed/session-level cross-tenant negatives for every applicable private surface and recovery/restore path;
9. centralized CSRF, Origin/Referer, Fetch Metadata, CORS, Host, trusted-proxy, TLS, cache and security-header controls;
10. bounded unauthenticated/pre-auth/provider/authenticated/outbound-provider abuse controls and fail-closed degradation;
11. sanitized observability with no provider, auth, session, broker or tenant-private secrets;
12. restart/redeploy, migration, replacement-runtime, backup/restore-isolation, rollback and exact release evidence;
13. deterministic phone/tablet/desktop browser acceptance on the hosted technical boundary;
14. complete preflight, full-diff/security/recovery review, exact-head DRAFT/READY gates and post-merge Regression Shield.

No technical/security/recovery requirement may be deferred merely because public-production activation is separate.

## Only human product-authentication path

Telegram/VK provider data is authentication input only. It must never become a tenant identifier or an engineering/admin bypass.

Required properties:

- no deployed `preview-login`, `private-test-login`, `private-external-login`, OWNER/admin/developer/demo route or equivalent session-minting path;
- exactly two human login actions in the product UI: Telegram and VK ID;
- unconfigured/unavailable providers remain disabled/fail-closed, with no demo fallback;
- no client-supplied tenant selector as authorization;
- no provider/product auth/session/refresh token in browser Web Storage;
- callback success yields only a verified external identity before server-side account/tenant/session composition;
- invalid, replayed, stale, contradictory, mixed-up or browser-mismatched state fails closed;
- free access means billing disabled, not anonymous access.

Test fixtures/provider doubles may be injected only below deployed routing and outbound-network boundaries. They must not be human-accessible, selectable by production requests or capable of bypassing the real route/session composition.

## Hosted technical environment

The accepted Render Free + Neon PostgreSQL 18 Phase-4 topology may be used for deterministic hosted technical acceptance while it stays within its accepted zero-cost/synthetic boundary.

This allowance does not authorize:

- real broker credentials or protected private portfolio/account payloads in the synthetic environment;
- a browser-accessible synthetic login/session issuer;
- representing synthetic provider evidence as real-provider/public-user acceptance;
- paid overage or a provider mutation outside the accepted zero-cost workflow boundary.

Provider adapters and deployed routes must still implement the current real Telegram/VK contracts and fail closed without valid configuration.

## Session, tenant and private-data boundary

Required product-auth/session properties:

- opaque high-entropy server-side session identifier with only its protected digest stored durably;
- Secure, HttpOnly, correctly host/path/SameSite-scoped cookies;
- a separate short-lived browser proof for cross-site provider callback binding;
- fixation protection and fresh session issuance after authentication;
- bounded idle and absolute expiry;
- explicit logout and revoke-all-sessions;
- no client-provided `user_id`, `tenant_id` or object ID as authority;
- no raw credential/session/provider token returned to the browser or persisted in Web Storage;
- no cross-tenant access through application, database, jobs/caches or restore/recovery boundaries.

Raw broker credentials remain USER/tenant owned, encrypted/opaque inside the accepted custody boundary and unavailable to another tenant, frontend, Cortex, ordinary CI or unrelated jobs.

## Browser/API security and degraded behavior

The integrated implementation must prove:

- no state-changing GET;
- a coherent server/session-bound CSRF design plus exact Origin/Referer validation and Fetch Metadata defense-in-depth for unsafe requests;
- narrowly scoped provider callback exceptions protected by provider state/PKCE/nonce/browser proof;
- same-origin CORS and canonical Host/origin/TLS enforcement;
- no trust in arbitrary client-supplied forwarded headers;
- no-store private/auth responses plus reviewed HSTS/CSP/nosniff/referrer/isolation headers;
- bounded rate/capacity dimensions and outbound provider concurrency;
- explicit `429`/retry behavior where applicable;
- provider, database or capacity failure never falls back to anonymous/demo access;
- structured event codes/correlation IDs without sensitive payloads.

## Separate later public-production activation

Amendment 11 deliberately leaves these actions in a later independent fail-closed gate:

- final Cloud.ru Evolution production resource apply;
- production DNS/edge/hostname mutation;
- production Telegram/VK credential provisioning and callback registration requiring OWNER-held secrets/provider-console authority;
- real public-user cutover;
- `PUBLIC_MULTI_USER_ENABLED=true`;
- production privacy/personal-data/legal/capacity/monitoring/incident acceptance;
- any recurring paid infrastructure commitment;
- public T-Invest-backed functionality before its separate broker-terms permission gate.

Technical WP22A completion must not be represented as satisfying this production gate.

## Production-provider and cost boundary

The selected final production provider remains **Cloud.ru Evolution**.

Current recurring infrastructure authorization remains:

- `0 RUB/month`;
- `0 USD/month`;
- `provider_apply_authorized=false`;
- `real_user_cutover_authorized=false`;
- no payment/card charge, automatic paid overage or silent paid fallback.

Immediately before any later Cloud.ru apply, engineering must revalidate the exact current region/SKU/price/free-or-bonus eligibility, prove the smallest safe topology, state the recurring cap and deletion path, and obtain explicit OWNER approval for any commitment above the current zero cap.

## Broker/legal boundary

Public site/account/tenant technical acceptance and public T-Invest-backed production functionality remain separate gates.

Until accepted broker/partner permission or another explicitly accepted compliant architecture exists:

- public T-Invest-backed functionality remains `FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION`;
- broker write remains OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- transfer/withdrawal/margin/leverage/uncovered-short authority remains forbidden.

## Initial free-access boundary

Initial USER access remains free:

- `BILLING_ENABLED=false`;
- `TRIAL_ENABLED=false`;
- `SUBSCRIPTION_ENFORCEMENT=false`;
- `PREMIUM_FEATURE_GATING=false`.

These flags remove billing gates only. They never permit anonymous/demo product sessions.

## Web visual-refresh and WP23 boundary

The OWNER-approved design specification remains at:

`docs/architecture/V10_WEB_VISUAL_DESIGN_REFRESH_IMPLEMENTATION_BRIEF.md`

It remains **planning-only** during the integrated WP22A technical implementation. This authorization does not start WP23, AI/Cortex, broker-write/Real work or a visual redesign.

Only a later evidence-backed WP22A closeout/status PR may mark WP22A complete and authorize the named next implementation increment. This file never unlocks WP23 or the visual runtime by itself.

## Integrated implementation shape

After Amendment 11 is accepted, remaining Phase-5 source work should use one integrated implementation branch/PR with logical commits. Split only when evidence proves a deploy-before-code migration, independently reversible rollout, security-isolation boundary or objectively unreviewable final diff. Ordinary module/file boundaries are not a reason to return to micro-PR sequencing.

Remote CI, Gitar, Sonar and branch deployment are final independent verification surfaces, not interactive debuggers. Cheap/focused deterministic checks, migration/security review and the complete diff must be clean before the first comprehensive DRAFT cycle.

## WP22A technical Exit Gate

The integrated Phase-5 implementation is accepted only after all applicable technical items are proven on exact source/runtime evidence, including:

- hosted HTTPS normal-browser reachability on the technical boundary;
- exactly Telegram/VK verified login composition and no deployed session bypass;
- browser-bound durable pre-auth and provider replay/mix-up defenses;
- normal USER login/logout/session lifecycle;
- tenant isolation and cross-tenant negatives;
- private-data/credential custody boundaries;
- recovery/replacement-runtime/restore-isolation evidence;
- rate/abuse/capacity controls and fail-closed degraded behavior;
- security headers/cache/origin/session/proxy protections;
- exact release and rollback evidence;
- no OWNER-home availability dependency;
- no unresolved P0/P1 or blocking review thread;
- exact-head DRAFT GREEN, independent Gitar/Sonar review, fresh READY GREEN, squash merge and exact-main Regression Shield GREEN.

Provider/cost/legal/broker facts may remain explicitly `PENDING` or `LOCKED` only when Amendment 11 assigns the real production mutation to `PUBLIC_PRODUCTION_ACTIVATION`. No missing technical/security evidence qualifies for this deferral.

After the integrated implementation is accepted, a small evidence/status PR must map every technical item before setting `wp22a_technical_gate_complete=true` or `wp22a_complete=true`. Until then both remain false, WP23 remains locked and public production remains inactive.
