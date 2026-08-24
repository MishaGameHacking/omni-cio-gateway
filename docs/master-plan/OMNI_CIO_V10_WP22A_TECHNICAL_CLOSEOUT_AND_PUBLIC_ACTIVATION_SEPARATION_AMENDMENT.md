# Omni-CIO V10 — WP22A Technical Closeout / Public Activation Separation Amendment

Status: **OWNER-APPROVED PLANNING AUTHORITY — EFFECTIVE ON MERGE TO PROTECTED `main`**  
Decision date: **2026-08-24**  
Scope: **WP22A Phase 5 sequencing only; technical External Web Access / Product Authentication Security closeout versus later public-production activation**

## 1. Purpose and precedence

This amendment corrects the sequencing of the final WP22A work without reducing the final Omni-CIO public-product target or weakening any security, privacy, tenant, recovery, broker, cost or V9 rollback boundary.

The later accepted amendments remain authoritative where they supersede older assumptions:

- Amendment 9 — Product USER / Engineering Authority Boundary;
- Amendment 10 — Public Free Multi-User Hosted Runtime.

The final product remains one public modern multi-user Omni-CIO Web product with the product identity path:

`Telegram Login | VK ID -> verified external identity -> OmniCIOUserAccount -> Tenant -> server-side Session -> tenant-scoped product state`

The final public-production origin remains the accepted managed-cloud target selected for WP22A, currently Cloud.ru Evolution. The PROJECT OWNER's home infrastructure is not allowed to become the public-production availability anchor.

This amendment changes only **when production-provider mutation and real-user public cutover are required**. It does not declare either one complete.

## 2. WP22A technical-closeout definition

WP22A may be closed after its complete technical External Web Access / Product Authentication Security Gate is implemented and accepted on the reviewed hosted technical boundary, even while a later real-user public-production activation gate remains deliberately fail-closed.

Technical acceptance must prove the real application architecture and the complete browser/auth/session/tenant/security/recovery behavior. It must not be reduced to mocked UI or documentation existence.

The technical gate may use the accepted zero-cost hosted Render/Neon topology for deterministic acceptance while final production-provider mutation remains locked. Provider doubles/fixtures are allowed only when real provider secrets, callback registration or provider-console operations are genuinely non-delegable; such doubles must remain below the deployed routing/network authority boundary and must never create a human-accessible alternate login or session-minting endpoint.

The source implementation must still conform to the current real Telegram/VK provider contracts and fail closed when provider configuration is absent.

## 3. Single product-authentication authority

The only supported human product-login protocols are:

1. Telegram Login;
2. VK ID.

No third human login path exists.

The following are forbidden in deployed product mode:

- OWNER login;
- admin/developer login;
- public demo/preview session minting;
- `private-test-login` session minting;
- `private-external-login` session minting;
- hidden alternate tenant/session selectors;
- engineering/provider identity being converted directly into an Omni-CIO product tenant session.

When the PROJECT OWNER uses Omni-CIO, the OWNER authenticates as an ordinary USER through Telegram or VK ID and receives only that USER's tenant-scoped session.

Initial access may remain free of billing. `BILLING_ENABLED=false`, `TRIAL_ENABLED=false`, `SUBSCRIPTION_ENFORCEMENT=false` and `PREMIUM_FEATURE_GATING=false` mean no payment entitlement is required; they do not authorize anonymous or demo access.

## 4. Hosted technical-acceptance boundary

The existing source-controlled React/FastAPI/PostgreSQL product is the only implementation basis. No second frontend, API, identity service, database authority, Core or broker stack is authorized.

WP22A technical closeout may use the accepted hosted zero-cost technical/synthetic boundary to prove the complete source/runtime behavior provided that:

- no real broker credential/private portfolio payload is introduced;
- no human-accessible synthetic/OWNER/admin session bypass exists;
- provider fixtures are injected only below the deployed authentication routing boundary;
- provider adapters/routes remain compatible with current official Telegram/VK protocols;
- absent or invalid provider configuration fails closed;
- tenant/application/database isolation is exercised with deterministic multi-user fixtures;
- restart/replacement-runtime/recovery behavior is exercised against durable PostgreSQL state;
- exact release and rollback evidence remains repository-controlled.

A successful technical gate does not by itself assert that production provider accounts, real provider credentials, DNS or public users have been activated.

## 5. WP22A technical Exit Gate

Before the later WP22A closeout may mark WP22A COMPLETE, the integrated Phase-5 implementation must prove at minimum:

### 5.1 Browser and provider transaction security

- ordinary modern phone/tablet/desktop browser operation over reviewed HTTPS semantics;
- transaction-specific state, PKCE and nonce as applicable to the provider;
- a separate high-entropy initiating-browser proof bound to the pre-auth transaction;
- durable/shared pre-auth transaction persistence suitable for restart/multi-instance routing;
- provider identity + exact redirect binding;
- one-time atomic consume, bounded TTL/capacity and deterministic cleanup;
- distinct Telegram and VK callback trust boundaries;
- provider mix-up, replay and browser-swapping negative tests;
- fixed provider origins and bounded network/response behavior.

### 5.2 Telegram/VK verification

- current Telegram Login/OIDC Authorization Code + PKCE behavior implemented and verified server-side;
- current VK ID OAuth 2.1 behavior implemented and verified server-side;
- provider callback result establishes only `VerifiedExternalIdentityV1` or its accepted successor contract;
- provider tokens/profile fields do not become tenant/business authority;
- Telegram JWKS refresh/key-rotation behavior is hardened for live concurrency without provider amplification or lock-held network I/O.

### 5.3 Account, tenant and durable session

- verified provider identity maps only through the accepted internal account-binding service;
- raw provider subject remains protected according to the accepted binding design;
- tenant authority derives only from the resolved server-side session;
- opaque high-entropy session identifier with digest-only durable storage;
- Secure/HttpOnly/host-scoped cookie behavior;
- explicit fixation protection and fresh session issuance after authentication;
- bounded idle and absolute lifetime;
- logout and true revoke-all-sessions semantics;
- no provider/product auth/session token in browser Web Storage;
- private/auth responses use reviewed no-store behavior.

### 5.4 Browser request firewall

- no state-changing GET endpoints;
- coherent CSRF protection suitable for the stateful BFF model;
- exact Origin validation with reviewed Referer fallback where required;
- Fetch Metadata defense in depth with explicit compatibility fallback;
- narrow documented OAuth callback exception protected by the provider transaction and browser proof;
- deny-by-default CORS;
- canonical Host/origin handling;
- forwarded/proxy metadata trusted only from the reviewed proxy boundary;
- HSTS/CSP/nosniff/referrer/COOP and other accepted security headers retained where applicable.

### 5.5 Tenant/private-data isolation

- application authorization derives tenant scope only from server session;
- PostgreSQL RLS/FORCE-RLS remains a second independent isolation boundary;
- runtime role has no SUPERUSER/BYPASSRLS authority;
- guessed-ID/IDOR/cross-tenant/stale-session/cache/job/recovery negatives are deterministic where applicable;
- backup/restore/replacement-runtime evidence preserves tenant isolation;
- broker/private state and credentials remain tenant-owned and are never returned to unrelated tenants or browser storage.

### 5.6 Abuse, capacity and degradation

- bounded unauthenticated/pre-auth/login limits;
- bounded authenticated session/user mutation limits;
- bounded provider-outbound concurrency/anti-amplification behavior;
- provider/DB timeout, saturation and outage fail closed;
- `429`/`Retry-After` or an equivalent explicit bounded contract is used where applicable;
- degradation never falls back to demo/anonymous/OWNER access;
- no new Redis/queue/provider dependency is added without measured need and an accepted dependency/provider decision.

### 5.7 Recovery, release and evidence

- migration/bootstrap idempotency and compatibility are proven;
- runtime restart/redeploy/replacement behavior is proven without OWNER home availability;
- restore isolation and rollback to last accepted release are proven;
- exact Git SHA/release provenance and health-before-traffic behavior are proven;
- no auth code, PKCE verifier, nonce, cookie, provider token, client secret, raw provider subject, broker secret or tenant-private payload appears in source/CI/logs/artifacts;
- all applicable exact-head DRAFT checks execute and conclude `success`;
- independent Gitar/Sonar review is resolved;
- a fresh unchanged-head READY cycle executes and concludes `success`;
- unresolved blocking review threads = 0;
- squash merge is followed by exact-main permanent Regression Shield success.

Technical/security requirements in this section cannot be reclassified as later public-production activation work merely to close WP22A.

## 6. Separate public-production activation gate

The following remain a later independent fail-closed gate after WP22A technical completion:

- final Cloud.ru Evolution production apply/cutover;
- production DNS/edge/provider mutation;
- real Telegram/VK production credential provisioning and callback registration when those actions require OWNER-held provider secrets or provider-console access;
- real-user public-production cutover;
- `PUBLIC_MULTI_USER_ENABLED=true`;
- recurring paid infrastructure commitment above the currently authorized zero-cost cap;
- production privacy/personal-data/legal/capacity/monitoring/incident sign-off;
- public T-Invest-backed functionality until its independent broker-terms permission gate is accepted.

No WP22A technical acceptance or GitHub merge implicitly authorizes these actions.

## 7. Provider and cost lock

The final production-provider target remains **Cloud.ru Evolution**.

Current recurring infrastructure authority remains:

- `0 RUB/month`;
- `0 USD/month`;
- provider apply not authorized;
- no automatic paid fallback;
- no automatic paid overage;
- no card/payment mutation by implication.

Before any later paid production-provider mutation, engineering must revalidate the exact current SKU, region, price/free-or-bonus status, deletion/shutdown path and smallest safe topology, then obtain explicit OWNER approval for any recurring amount above the current zero cap.

A stale or unavailable cost attestation fails closed. It does not authorize a weaker security topology.

## 8. Broker and Real-execution locks

This amendment does not widen broker or money authority.

Until an independent accepted broker permission decision changes it:

- public T-Invest-backed functionality remains `FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION`;
- broker write remains OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- transfer/withdrawal authority is forbidden;
- margin/leverage/uncovered-short authority is forbidden.

Development, CI, provider authentication and public account work do not constitute broker-submit authorization.

## 9. WP23 and visual-refresh sequencing

This amendment does not by itself mark Phase 5 accepted, does not mark WP22A COMPLETE and does not unlock WP23.

After the integrated Phase-5 technical implementation is accepted through merge + exact-main Regression Shield, a small evidence/status closeout must map every technical Exit-Gate requirement to accepted evidence. Only that later closeout may set:

- `WP22A = COMPLETE`;
- the next Master Plan package as unlocked;
- the OWNER-approved `docs/architecture/V10_WEB_VISUAL_DESIGN_REFRESH_IMPLEMENTATION_BRIEF.md` as a named runtime implementation increment when the canonical sequence explicitly authorizes it.

Until then the visual brief remains planning authority only.

## 10. One-product and rollback rule

Reuse the existing:

- `apps/web` frontend;
- `apps/api` application surface;
- `omni_cio` Core/Web identity/session modules;
- PostgreSQL persistence/migrations;
- accepted deployment/recovery architecture.

The protected V9 production/recovery baseline remains `app:app` and must remain rollback-capable until its owning later parity/decommission gate is accepted.

This amendment does not authorize a greenfield rewrite or a competing product stack.

## 11. Engineering sequence after acceptance

After this amendment itself is accepted on protected `main` and its exact-main Regression Shield is GREEN, the next Phase-5 source work should be one integrated technical-closeout implementation branch/PR unless a concrete schema rollout, dependency/toolchain, security-isolation or objective reviewability constraint proves that a split is safer.

Ordinary module/file boundaries are not sufficient reason to return to many micro-PRs.

The integrated branch must be completed and reviewed as one coherent trust/data flow:

`Browser -> Telegram/VK -> Verified Identity -> OmniCIOUserAccount -> Tenant -> PostgreSQL Session -> tenant-scoped API/state`

and the reverse logout/revoke/degradation/recovery paths.

## 12. Effectiveness

This amendment becomes accepted authority only after its focused PR is merged to protected `main` through the repository exact-head GREEN law and the resulting exact-main permanent Regression Shield completes successfully.

Until then it is planning authority only and cannot be used to start the integrated closure implementation branch.