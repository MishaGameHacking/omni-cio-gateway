# Omni-CIO V10 — WP22A Phase 5 Public-Hosted Acceptance Authorization

Status: **PHASE 5 AUTHORIZED / TECHNICAL CLOSEOUT AUTHORIZED BY AMENDMENT 11 / PUBLIC PRODUCTION ACTIVATION LOCKED**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**

## Purpose

Phase 5 closes the technical browser/product-authentication security boundary required by WP22A while preserving a separate later gate for real-user public-production activation.

The sequencing split is governed by:

`docs/master-plan/OMNI_CIO_V10_WP22A_TECHNICAL_CLOSEOUT_AND_PUBLIC_ACTIVATION_SEPARATION_AMENDMENT.md`.

The final product target remains unchanged:

`ordinary Internet browser -> public HTTPS -> Omni-CIO Web/API -> Telegram Login or VK ID -> verified external identity -> OmniCIOUserAccount -> Tenant -> server-side Session -> tenant-scoped product state`

Provider/GitHub/Windows/CI authority remains outside product identity. The PROJECT OWNER is an ordinary product USER when using Omni-CIO.

This authorization does not start WP23 Telegram Bot Foundation, AI/Cortex, broker write or Real execution.

## Accepted prerequisite

Phase 4 is accepted only through `V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.md` plus its machine-readable contract and exact-base public acceptance evidence.

The current Phase-5 source baseline also includes the accepted provider-auth transaction core, dormant Telegram OIDC adapter and dormant VK ID OAuth 2.1 adapter. Their existence does not by itself make the public auth flow accepted.

## Two independent gates

### A. WP22A technical-closeout gate

This gate is the current Phase-5 implementation authority.

It proves the complete technical Web/BFF authentication/session/tenant/security/recovery behavior on the accepted hosted technical boundary. It may use deterministic provider doubles only where real provider credentials, callback registration or provider-console actions are genuinely non-delegable.

Provider doubles must be injected below the deployed product routing/network authority boundary. They must never become a human-accessible login, demo, OWNER, admin, private-test or other session-minting bypass.

The real source implementation must match the current official Telegram/VK protocol contracts and fail closed when provider configuration is absent or invalid.

### B. Later public-production activation gate

This gate remains independently locked after WP22A technical completion. It owns real Cloud.ru/public provider mutation, real provider secret provisioning/production callback registration, real-user public cutover, recurring paid infrastructure decisions, `PUBLIC_MULTI_USER_ENABLED=true`, and production privacy/legal/capacity/monitoring approval.

WP22A technical completion never silently satisfies this later gate.

## Authorized Phase-5 technical work

Phase 5 may implement and verify the complete technical public-hosted acceptance/security/recovery surface required to close WP22A:

1. ordinary supported phone/tablet/desktop browser operation under reviewed HTTPS semantics without OWNER home infrastructure as an availability dependency;
2. exactly Telegram Login and VK ID as human product-authentication protocols;
3. verified provider result -> internal account binding only; provider identity never becomes a tenant, role or engineering authority;
4. durable/shared one-time pre-auth transactions with state/proof digests, server-side PKCE verifier/nonce as applicable, exact provider/redirect binding, bounded TTL/capacity and atomic consume;
5. an independent high-entropy initiating-browser proof so a callback cannot be completed in a different browser context merely by possessing callback parameters;
6. distinct Telegram and VK start/callback trust boundaries with provider mix-up, replay and browser-swapping negatives;
7. Telegram JWKS concurrency/key-rotation hardening before live route composition;
8. verified identity -> `OmniCIOUserAccount` -> Tenant -> durable server-side Session composition using the accepted PostgreSQL identity/session architecture;
9. fixation protection, fresh session issuance after authentication, bounded idle/absolute lifetime, logout and true revoke-all-sessions;
10. tenant scope derived only from authenticated server-side session state;
11. application authorization plus PostgreSQL RLS/FORCE-RLS cross-tenant negatives over applicable private surfaces and recovery paths;
12. coherent CSRF/Origin/Referer/Fetch-Metadata/CORS/Host/trusted-proxy/TLS/private-cache/security-header behavior;
13. bounded unauthenticated/login/session/provider-outbound abuse and capacity controls with fail-closed degradation;
14. frontend cutover so unauthenticated product UI has exactly Telegram and VK ID actions and no demo/OWNER/admin fallback;
15. retirement from deployed product mode of `preview-login`, `private-test-login`, `private-external-login` and equivalent human session-minting bypasses;
16. USER-facing `/system` diagnostics without product-admin authority;
17. restart/redeploy/replacement-runtime, migration/recovery/restore-isolation and rollback acceptance;
18. exact release provenance, health-before-traffic evidence and post-merge Regression Shield.

## Product authentication authority

The only ordinary human login methods are:

- Telegram Login;
- VK ID.

There is no product OWNER/admin/developer login. Free access means billing is disabled, not authentication.

Provider callback/assertion data establishes only a verified external identity. Internal account and tenant authority are selected server-side from the accepted account-binding repository/service.

No client-supplied `tenant_id`, `user_id`, provider display name, provider engineering identity, URL object ID or frontend state may grant tenant authority.

## Browser-bound provider transaction requirements

The final deployed auth route must not rely only on a process-local state registry when technical acceptance claims restart/multi-instance tolerance.

Required properties include:

- server-generated high-entropy transaction state;
- S256 PKCE where required by/currently used for the provider;
- nonce where required by the provider/OIDC contract;
- separate high-entropy browser proof;
- only digests for state/browser proof at the durable lookup boundary;
- server-only PKCE verifier/nonce;
- exact provider and exact redirect URI binding;
- atomic one-time consume;
- expiry and bounded capacity;
- deterministic cleanup;
- failure on replay, provider mix-up, wrong browser proof, stale state, ambiguous callback or invalid provider response.

The short-lived pre-auth browser-proof cookie may use `SameSite=Lax` for a cross-site top-level safe callback navigation. That is separate from the post-auth product session cookie and is not permission to weaken the post-auth session's normal `SameSite` policy.

## Provider-specific boundary

Telegram and VK are independent trust boundaries.

Telegram acceptance requires current official OIDC/Login behavior, Authorization Code + PKCE, fixed provider endpoints, strict ID-token signature/issuer/audience/nonce/time validation and safe JWKS key rotation/concurrency behavior.

VK ID acceptance requires current official OAuth 2.1 behavior, fixed provider endpoints, state + PKCE, required provider callback fields such as `device_id` where the current contract requires them, exact returned-state verification and a stable verified provider subject.

Provider access/refresh/profile material is authentication transport only. Do not collect or persist unrelated profile fields merely because a provider can return them.

## Server-side session boundary

Required product-session properties:

- opaque high-entropy session identifier;
- durable server-side authority;
- digest-only session-token persistence;
- host-scoped `Secure`, `HttpOnly` cookie with reviewed `SameSite` policy;
- no product/provider auth/session/refresh token in browser Web Storage;
- fixation protection and fresh token issuance after authentication;
- explicit bounded idle and absolute lifetime based on the public financial-risk model;
- explicit logout;
- true revoke-all-sessions;
- stale/revoked/expired session fail closed;
- private/auth responses use reviewed `Cache-Control: no-store` behavior.

## CSRF, origin and browser request firewall

State-changing browser endpoints must not use GET.

The stateful BFF must use one coherent reviewed CSRF design combined with:

- exact Origin validation;
- reviewed Referer fallback where required;
- Fetch Metadata as defense in depth with explicit compatibility fallback;
- deny-by-default CORS;
- canonical Host/origin validation;
- forwarded metadata trusted only from the reviewed proxy boundary.

SameSite is defense in depth and not the sole CSRF control.

OAuth callback GETs are a narrow documented exception because they are protected by the provider transaction, PKCE/nonce as applicable, provider binding and independent initiating-browser proof.

## Tenant and private-data boundary

A normal USER may access only that USER's tenant.

Acceptance must prove application authorization and database-enforced isolation, including applicable IDOR/cross-tenant/stale-session/job/cache/recovery negatives.

The hosted runtime PostgreSQL role must remain least privilege and may not gain SUPERUSER/BYPASSRLS authority.

Raw broker credentials and tenant-private payloads:

- remain USER/tenant owned;
- are never returned to the browser after submission;
- are never stored in browser Web Storage;
- never enter GitHub, CI logs, artifacts or screenshots;
- remain inaccessible to another tenant;
- do not become provider/OAuth test fixtures.

## Abuse, capacity and degraded behavior

The technical gate requires bounded controls for:

- unauthenticated/pre-auth attempts;
- provider-specific login attempts;
- authenticated session/user mutations;
- provider-outbound concurrency;
- durable pre-auth transaction capacity.

Timeout, provider outage, DB failure or saturation must fail closed without request amplification, unbounded memory, anonymous/demo fallback or weakened tenant/session controls.

Use `429`/`Retry-After` or another explicit bounded contract where appropriate.

Do not add Redis or another infrastructure service merely by convention. Add a new dependency only after measured evidence shows the existing PostgreSQL + bounded process controls cannot meet the accepted technical gate.

## Recovery and release boundary

Technical closeout must prove:

- account/session state survives runtime replacement;
- in-flight auth either survives through the durable pre-auth boundary or explicitly fails closed and restarts safely;
- migration/bootstrap idempotency and compatibility;
- database restore preserves tenant isolation;
- secret/key recovery/rotation contracts remain safe;
- exact release Git SHA is observable;
- health/readiness is established before traffic acceptance;
- rollback to the last accepted release remains possible;
- V9 `app:app` remains the protected rollback baseline until its later owning cutover/decommission gate.

No backup/recovery capability may be called PASS without actual evidence.

## Production-provider and cost boundary

The selected final production provider remains **Cloud.ru Evolution**.

The later public-production activation gate is not pre-authorized to spend money.

Current recurring infrastructure authorization remains:

- `0 RUB/month`;
- `0 USD/month`;
- no payment/card charge by implication;
- no automatic paid overage;
- no silent paid fallback;
- provider apply false.

Immediately before a later Cloud.ru production apply, engineering must revalidate exact current SKU/region/price/free-or-bonus eligibility, smallest safe topology and deletion/shutdown path. Any recurring amount above zero requires explicit OWNER cost approval.

A stale zero-cost/provider attestation fails closed and may block provider mutation without invalidating independently proven source/technical evidence that does not require that mutation.

## Broker/legal boundary

Public account/Web acceptance and public T-Invest-backed functionality remain separate gates.

Until accepted broker/partner permission or another explicitly accepted compliant architecture exists:

- public T-Invest-backed functionality remains `FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION`;
- broker write remains OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- transfer/withdrawal/margin/uncovered-short authority remains forbidden.

## Public-production activation boundary

`PUBLIC_MULTI_USER_ENABLED=false` remains the implementation state through WP22A technical closeout.

Only a later focused production-activation gate may authorize it to become true after all owning provider/secret/privacy/legal/capacity/monitoring/recovery requirements are accepted on the real production architecture.

Initial USER access remains free:

- `BILLING_ENABLED=false`;
- `TRIAL_ENABLED=false`;
- `SUBSCRIPTION_ENFORCEMENT=false`;
- `PREMIUM_FEATURE_GATING=false`.

## Web visual-refresh boundary

The OWNER-approved design specification remains:

`docs/architecture/V10_WEB_VISUAL_DESIGN_REFRESH_IMPLEMENTATION_BRIEF.md`

It remains planning-only during Phase-5 technical implementation. Amendment 11 does not authorize its CSS/TSX/runtime implementation.

Only the later evidence-backed WP22A closeout may explicitly authorize that named next increment in sequence.

## Explicit non-goals

Phase 5 must not:

- start WP23 Telegram Bot Foundation;
- start AI/Cortex WPs;
- enable broker write or Real execution;
- create a second Web App/API/Core/identity/database/broker stack;
- treat Render/Cloud.ru/GitHub/Windows identity as product authentication;
- expose real secret/private payloads in source, CI, logs, screenshots or artifacts;
- make Lenovo/home Internet the public production availability anchor;
- accept a paid provider commitment without the required OWNER cost decision;
- enable `PUBLIC_MULTI_USER_ENABLED=true` as part of technical closeout;
- claim the Premium Spatial Web redesign is authorized merely because its brief exists.

## Phase-5 technical Exit Gate

Phase-5 technical implementation is accepted only after all applicable source work is complete and the final technical hosted acceptance proves, at minimum:

- the complete browser -> Telegram/VK -> verified identity -> internal account -> tenant -> durable server-session path;
- no deployed human product-session bypass outside Telegram/VK;
- browser-bound durable one-time auth transactions;
- provider mix-up/replay/browser-swapping failures fail closed;
- verified login/logout/session lifecycle including true revoke-all;
- deployed/deterministic tenant isolation and cross-tenant negatives;
- private-data/credential custody boundaries;
- recovery/replacement-runtime/restore isolation;
- measured abuse/capacity/provider-degradation behavior;
- accepted trusted-proxy/Host/TLS/CORS/Origin/Referer/CSRF/private-cache/security-header behavior;
- exact release and rollback evidence;
- no OWNER-home availability dependency in the accepted hosted technical path;
- no unresolved P0/P1 or blocking review thread;
- exact-head DRAFT GREEN;
- independent Gitar/Sonar review resolved;
- fresh unchanged-head READY GREEN;
- squash merge;
- exact-main permanent Regression Shield GREEN.

Provider/cost/legal/broker items may remain `PENDING/LOCKED` after technical acceptance only when Amendment 11 explicitly assigns that item to the later public-production activation gate. No technical browser/auth/session/tenant/security/recovery requirement may be deferred under this clause.

Phase-5 technical acceptance still does not automatically mark WP22A COMPLETE. A final WP22A closeout must map the technical Exit-Gate evidence and only then may canonical status unlock the next package.