# Omni-CIO V10 — WP22A Technical Closeout / Public Production Activation Separation Amendment

Status: **OWNER-APPROVED PLANNING AUTHORITY — EFFECTIVE ON MERGE TO PROTECTED `main`**
Decision date: **2026-08-24**.
Scope: WP22A Phase-5 sequencing, technical acceptance, product authentication and the later public-production activation boundary.

## 1. Purpose and precedence

This amendment corrects sequencing only. It allows WP22A to close its technical **External Web Access / Product Authentication Security Gate** after the complete browser, provider, account, tenant, session, security, recovery and abuse boundary is implemented and accepted on the existing hosted technical environment.

It does not reduce or replace:

- Amendment 9's separation of product USER identity from PROJECT OWNER/engineering authority;
- Amendment 10's final public, free, multi-user, managed-cloud product target;
- the no-OWNER-home production dependency;
- tenant isolation, private-data custody, recovery, security, broker/legal or V9 rollback requirements.

Where the Phase-5 authorization/status layer previously coupled technical closure to real provider secrets, paid production infrastructure or public real-user cutover, this later amendment separates those actions into an independent fail-closed production-activation gate.

## 2. WP22A technical-closeout definition

WP22A technical closeout proves this complete product path:

`ordinary browser -> hosted HTTPS Omni-CIO Web/BFF -> Telegram Login | VK ID -> verified external identity -> OmniCIOUserAccount -> isolated Tenant -> persistent server-side Session -> tenant-scoped product state`

The technical gate must prove source, runtime composition, migrations, deterministic browser behavior, security controls, recovery and rollback. It may close WP22A without purchasing or applying the final production provider and without provisioning OWNER-held production provider secrets.

Technical closeout is not public-production activation. It does not make real public users, paid infrastructure, production DNS/edge/provider state or legally gated broker functionality active.

## 3. One human product-authentication path

The only supported human product-login protocols are:

1. Telegram Login;
2. VK ID.

Both establish only a verified external identity. Internal account binding, tenant selection and product authority are resolved server-side through the accepted Omni-CIO account/session boundary.

Deployed product mode must not expose an OWNER, administrator, developer, demo, preview, private-test or private-external route capable of minting a product session. The PROJECT OWNER authenticates as an ordinary USER through Telegram or VK ID and receives only that USER's tenant-scoped session.

Free initial access means billing/subscription enforcement is disabled. It does not mean anonymous access or synthetic session minting.

Test fixtures and provider doubles may exist only below deployed human routing/network boundaries. They must not become a browser-accessible login endpoint, callback bypass or product-session issuer.

## 4. Hosted technical acceptance boundary

The accepted Render/Neon zero-cost Phase-4 topology may be reused as the deterministic hosted technical acceptance environment while it remains within its accepted zero-cost/synthetic/private-data boundary.

The integrated implementation must still implement the current real Telegram and VK provider contracts and fail closed when provider configuration is absent or invalid. When real provider secrets, provider-console callback registration or another non-delegable action is unavailable, deterministic provider doubles may prove protocol composition only when all of the following hold:

- the double is injected below deployed routing and outbound-network boundaries;
- no human-accessible route can select or invoke it;
- it produces only the same bounded verified-identity contract as the real adapter;
- negative evidence proves that deployed bypass routes cannot mint a session;
- no real secret, raw provider subject, auth code, token or tenant-private payload enters source, CI, logs, screenshots or artifacts.

Synthetic hosted acceptance does not authorize real broker credentials or protected private portfolio/account payloads in that environment.

## 5. Technical Exit Gate

WP22A technical closeout requires evidence for all applicable items below. No technical/security item may be reclassified as a deferred production-activation concern merely to obtain closure.

### 5.1 Authentication and browser binding

- exactly Telegram Login and VK ID human product-authentication routes;
- provider-specific fixed start/callback trust boundaries and mix-up defense;
- transaction-specific state, PKCE and nonce as applicable;
- a separate short-lived initiating-browser proof checked before provider exchange/session issue;
- durable/shared bounded pre-auth transactions containing only protected state/proof material, server-side verifier/nonce, exact provider/redirect binding, expiry and atomic one-time consume;
- replay, stale state, provider confusion and browser/session swapping rejected fail-closed;
- Telegram JWKS refresh/key-rotation concurrency hardened without unbounded refresh or network I/O under the shared cache lock.

### 5.2 Account, session and tenant authority

- verified provider result -> internal account -> one isolated tenant -> server-side session composition;
- opaque high-entropy session tokens with only protected digests stored server-side;
- Secure, HttpOnly, host/path/SameSite-scoped cookies and no provider/product token in browser Web Storage;
- fresh session issuance/fixation protection, rotation, bounded idle and absolute expiry, logout and true revoke-all;
- tenant authority only from resolved server-side session state;
- application authorization plus PostgreSQL RLS/FORCE-RLS and deterministic cross-tenant/IDOR/stale-session/restore-isolation negatives.

### 5.3 Browser/API security and abuse controls

- no state-changing GET route;
- coherent CSRF token, exact Origin/Referer and Fetch Metadata policy for unsafe browser requests, with only narrowly justified provider-callback exceptions;
- same-origin CORS, canonical Host/origin/TLS and explicitly trusted proxy semantics without trusting arbitrary forwarded headers;
- no-store private/auth responses and reviewed HSTS/CSP/nosniff/referrer/isolation headers;
- bounded unauthenticated, pre-auth/provider, authenticated session/USER and outbound-provider controls;
- `429`/bounded retry semantics where applicable and fail-closed behavior under provider, database or capacity degradation;
- sanitized structured events/correlation IDs with no auth, session, provider, broker or tenant-private secrets.

### 5.4 Recovery, release and acceptance

- migration idempotency and PostgreSQL 18 rehearsal;
- restart/redeploy and replacement-runtime behavior without OWNER home availability;
- durable account/session state and defined fail-closed handling of in-flight authentication;
- backup/restore integrity with tenant isolation preserved;
- rollback to the last accepted release and exact release provenance;
- phone, tablet and desktop browser acceptance on the hosted technical boundary;
- complete source/security/recovery diff review;
- exact-head DRAFT GREEN, independent Gitar/Sonar evidence, fresh READY GREEN, squash merge and exact-new-main Regression Shield GREEN.

## 6. Separate public-production activation

The following remain owned by a later independent `PUBLIC_PRODUCTION_ACTIVATION` gate and are not made true by WP22A completion:

- final Cloud.ru Evolution production apply and managed service creation;
- production DNS/edge/hostname mutation and real public-user cutover;
- production Telegram/VK credential provisioning and callback registration where OWNER-held secrets/provider-console authority is required;
- `PUBLIC_MULTI_USER_ENABLED=true`;
- recurring paid infrastructure commitment;
- production privacy, personal-data, legal, capacity, monitoring, incident and operations sign-off;
- public T-Invest-backed functionality before its independent broker-terms permission gate.

Until that gate is explicitly authorized and accepted:

- `PUBLIC_MULTI_USER_ENABLED=false`;
- `provider_apply_authorized=false`;
- `real_user_cutover_authorized=false`;
- production provider/DNS/edge mutation is forbidden;
- synthetic technical acceptance must not be represented as real public-production activation.

## 7. Cost and provider lock

The final production provider remains **Cloud.ru Evolution**. Current recurring infrastructure authority remains:

- `0 RUB/month`;
- `0 USD/month`;
- no automatic paid fallback, overage or card charge.

Immediately before any later provider apply, engineering must revalidate the exact current region/SKU/price/free-or-bonus eligibility and smallest safe topology. Any recurring commitment above the current zero cap requires explicit OWNER approval with the exact cost and deletion/shutdown path before mutation.

## 8. Broker and Real-execution locks

This amendment does not change:

- public T-Invest status `FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION`;
- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no transfer, withdrawal, margin, leverage or uncovered-short authority;
- tenant-owned READ/optional TRADE credential separation and exact verified-account intersection.

## 9. WP23 and visual sequencing

This amendment does not mark Phase 5 accepted, mark WP22A complete, unlock WP23 or authorize runtime implementation of the Premium Spatial Web visual-refresh brief.

The required sequence remains:

1. accept this governance amendment;
2. implement and accept one integrated WP22A technical-closeout branch unless a documented migration, rollout, security-isolation or objective reviewability reason requires a split;
3. merge a small evidence/status closeout only after all technical Exit-Gate evidence exists;
4. authorize the named next implementation increment through accepted canonical status;
5. execute public-production activation later through its own explicit provider/cost/secret/legal gate.

## 10. One product and protected rollback

Implementation reuses the existing `apps/web`, `apps/api`, `omni_cio`, PostgreSQL and accepted deployment/recovery boundaries. A second frontend, API, Core, identity system, database authority or broker stack is forbidden.

Protected V9 `app:app` rollback remains untouched until its responsible parity/decommission gate. GitHub source, runtime secrets and tenant-private state remain separate.

## 11. Current standards baseline

Technical implementation and review must revalidate current primary sources when the branch is written. The accepted baseline includes:

- RFC 9700, OAuth 2.0 Security Best Current Practice;
- RFC 10017 / BCP 212, OAuth 2.0 for Browser-Based Applications, including the server-side BFF pattern;
- current Telegram Login/OIDC and first-party VK ID protocol behavior;
- current NIST session guidance and OWASP ASVS/CSRF/session/authorization/secrets guidance;
- PostgreSQL 18 RLS/FORCE-RLS and current FastAPI/Uvicorn/provider proxy/TLS behavior.

This standards baseline informs the technical gate; it does not create a certification claim.

## 12. Acceptance effect

On merge to protected `main`, this amendment authorizes the integrated WP22A technical-closeout implementation package and the technical/production gate split described above.

It leaves accepted progress at **40%** and keeps WP22A current. WP23 remains locked, public production remains inactive and all provider/cost/broker/Real/visual locks stay in place.
