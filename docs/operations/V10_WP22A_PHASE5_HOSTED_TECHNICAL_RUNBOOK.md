# Omni-CIO V10 — WP22A Phase 5 Hosted Technical Closeout Runbook

Status: **IMPLEMENTATION DRAFT / CURRENT WP22A PHASE 5 / NOT ACCEPTED**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**  
Accepted base at branch start: `4824593e00455155079f3ecb1e62a762fccf3a4e`  
Public-production activation: **LOCKED**

## 1. Purpose

This runbook describes the integrated Phase-5 technical-closeout runtime that reuses
the accepted zero-cost Render Free + Neon PostgreSQL 18 hosted technical boundary.
It does not turn that boundary into final public production and does not authorize
Cloud.ru apply, production DNS, real public-user cutover, paid infrastructure or
broker-backed public functionality.

The only human product-authentication path is:

`browser -> Telegram Login | VK ID -> verified external identity -> OmniCIOUserAccount -> Tenant -> server-side Session`

There is no preview, private, OWNER, administrator, developer or demo route that can
mint a product session. The PROJECT OWNER uses the same Telegram/VK product path as
an ordinary USER.

## 2. Protected authority

Keep all of the following unchanged during this technical closeout:

- protected V9 entrypoint `app:app`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- `REAL_TRADING_ENABLED=false`;
- `TRADING_METHODS=false`;
- broker write OFF;
- public T-Invest functionality `FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION`;
- current recurring infrastructure authorization `0 RUB/month` / `0 USD/month`;
- Cloud.ru Evolution provider apply, production DNS/edge mutation and real-user
  cutover remain forbidden until the separate public-production activation gate.

## 3. Hosted entrypoint

The technical environment continues to use the existing source-controlled entrypoint:

`uvicorn apps.api.hosted_preview:create_app --factory --host 0.0.0.0 --port $PORT`

No second Web App, API, identity stack, database authority or deployment stack is
created.

`apps.api.hosted_preview:create_app` composes:

1. the accepted PostgreSQL 18 least-privilege runtime connection;
2. durable server-side sessions;
3. durable browser-bound provider authorization transactions;
4. provider configuration from runtime-only environment variables;
5. verified provider identity -> internal account/tenant binding;
6. hardened Telegram/VK provider routes;
7. browser/API security and bounded abuse controls.

Missing provider configuration is a valid fail-closed technical state: both login
providers are shown disabled and no product session can be created. Partial provider
configuration aborts startup instead of enabling a weaker fallback.

## 4. Runtime-only provider configuration

The source contract recognizes these environment variable names only; values are
never committed, logged, placed in CI artifacts or copied into this runbook:

- `OMNI_V10_TELEGRAM_OIDC_CLIENT_ID`;
- `OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET`;
- `OMNI_V10_VK_ID_CLIENT_ID`;
- `OMNI_V10_IDENTITY_BINDING_KEY_HEX`;
- `OMNI_V10_CSRF_BINDING_KEY_HEX`.

Telegram client ID and secret are all-or-nothing. When any real provider is
configured, the identity-binding and CSRF-binding keys are mandatory 32-byte values
represented by exactly 64 hexadecimal characters.

The canonical callback URIs are derived only from the reviewed HTTPS origin:

- `/api/v10/web/auth/telegram/callback`;
- `/api/v10/web/auth/vk_id/callback`.

No query, fragment, alternate port, userinfo or client-supplied redirect URI is
accepted as callback authority.

Real OWNER-held provider credentials and provider-console callback registration are
not required for the synthetic technical gate under Amendment 11 and remain a later
public-production activation action unless a non-synthesizable technical fact
explicitly requires them.

## 5. Human routes and browser behavior

The deployed human auth routes are exactly:

- `POST /api/v10/web/auth/telegram/start`;
- `GET /api/v10/web/auth/telegram/callback`;
- `POST /api/v10/web/auth/vk_id/start`;
- `GET /api/v10/web/auth/vk_id/callback`.

The React login shell uses native POST forms for provider start. A GET navigation is
not used to create state-changing provider pre-auth state.

The following historical routes must remain absent from deployed Phase-5 routing:

- `/api/v10/web/preview-login`;
- `/api/v10/web/private-test-login`;
- `/api/v10/web/private-external-login`.

`GET /api/v10/web/preview-mode` may remain as non-authoritative technical-environment
metadata only. It cannot create a session and reports `enabled=false`.

## 6. Pre-auth and provider security

Provider start creates one durable PostgreSQL transaction containing only bounded
server-side authorization material. Raw provider state and the initiating-browser
proof are retained only as digests; the PKCE verifier and nonce remain server-side.

Callback consumption is atomic and one-time through the accepted
`DELETE ... RETURNING` transaction store. Wrong provider, browser proof, replay,
expiry or missing transaction fails closed without changing tenant authority.

Telegram uses Authorization Code + PKCE + nonce and a fixed Telegram origin. The
deployed Telegram verifier uses single-flight JWKS refresh with provider network I/O
outside the shared refresh lock, bounded wait, failure cooldown and bounded unknown
`kid` rotation probing.

VK ID uses Authorization Code + PKCE, exact state and required `device_id`, fixed VK
origins and the minimal verified numeric provider user ID as authentication subject.
Provider profile data is not used as tenant authority.

## 7. Session and CSRF boundary

Successful provider verification yields a verified external identity only. The
server then resolves or binds the internal account/tenant and issues a fresh opaque
server-side session. Current/pre-auth session tokens are revoked before fresh issue
to prevent fixation.

Browser cookies use the `__Host-` boundary:

- `__Host-omni_v10_session` — Secure, HttpOnly;
- `__Host-omni_v10_csrf` — Secure and session-bound by server HMAC;
- provider-specific short-lived HttpOnly browser-proof cookies for Telegram/VK.

Authentication/session/refresh/provider tokens are never persisted in browser Web
Storage. Logout revokes the current session. Revoke-all revokes every live session
for the authenticated USER.

## 8. Browser/API request security

The hosted boundary requires HTTPS, canonical Host and exact same-origin validation
for unsafe requests. State-changing browser requests use exact `Origin` plus
session-bound CSRF. Fetch Metadata rejects unsafe `cross-site` and `same-site`
requests as defense in depth while requests without Fetch Metadata fall back to the
exact Origin/CSRF policy.

Provider start is the only unsafe unauthenticated exception to session CSRF; it still
requires exact same-origin browser initiation and creates only bounded pre-auth state.
Provider callback remains GET because it consumes provider authorization state and is
protected by provider-specific state, PKCE/nonce as applicable and the independent
initiating-browser proof.

Private/API responses remain `no-store`. HSTS, CSP, nosniff, referrer and opener
headers remain enabled. `Vary: Origin, Sec-Fetch-Site` prevents request-security
metadata from being ignored by intermediary caches.

Render terminates public TLS at its managed load balancer and forwards the request to
the Web Service application port over HTTP; Render documents that forwarded port as
not directly reachable from the public Internet. The application therefore does not
read `X-Forwarded-Proto` (or another client-supplied forwarded header) as TLS
authority. The reviewed Render entrypoint explicitly composes the source-level
`trusted_edge_tls_terminated=True` boundary for the accepted `.onrender.com` host.
Outside that exact composition the default remains direct HTTPS-required and a
spoofed `X-Forwarded-Proto: https` cannot satisfy the gate.

A future provider/origin topology must establish its own reviewed proxy trust model;
it must not inherit the Render trust assertion implicitly.

## 9. Abuse and capacity controls

The technical boundary has separate bounded dimensions for:

- a global product-API ingress cap that executes before any session-store lookup;
- anonymous API requests;
- authenticated session requests, keyed by SHA-256 of the opaque session token only
  after the server-side session registry resolves that token to a live session;
- Telegram/VK provider starts;
- Telegram/VK callbacks;
- pending durable provider transactions;
- outbound provider concurrency.

Session-cookie syntax is only a cheap bounded prelookup guard. Malformed values never
reach the session store, while a shape-valid but unresolved/revoked/expired token is
collapsed into the shared anonymous bucket and never receives authenticated capacity.
The global cap is consumed before durable lookup so rotating fake session candidates
cannot create unbounded PostgreSQL verification work.

Rate/capacity rejection is fail-closed with HTTP `429` and bounded `Retry-After`.
Provider outbound-capacity rejection happens before provider code exchange so it does
not consume the valid browser transaction. The provider-proof cookie is preserved for
a bounded retry. `/healthz` is intentionally not starved by ordinary product-rate
limits and has its own bounded monitoring capacity so monitoring can distinguish
overload from application outage.

## 10. Recovery rule for authentication authority

Normal restart/redeploy keeps durable in-flight provider transactions and durable
sessions according to their bounded lifetimes. Backup restore is different: a
point-in-time snapshot can predate a provider transaction consume or a session
revocation.

Therefore replacement-database recovery must use the Phase-5 recovery sequence:

1. validate the accepted Phase-3 archive/integrity/tenant/RLS contract;
2. restore only into a separate replacement database;
3. before exposing the recovered runtime, delete every restored
   `omni_cio_v10.provider_auth_transactions` row;
4. delete every restored `omni_cio_v10.web_sessions` row;
5. verify both counts are exactly zero;
6. reapply/verify runtime ACL and FORCE-RLS boundaries;
7. prove unscoped and cross-tenant negatives;
8. only then expose the replacement runtime.

Implementation:

- `omni_cio.persistence.phase5_auth_recovery_v1.build_phase5_restore_commands`;
- `validate_phase5_post_restore_auth_evidence`.

This intentionally invalidates login state only. It does not delete user accounts,
tenants, broker-connection records or other durable product truth. Users authenticate
again after recovery.

## 11. Synthetic hosted acceptance boundary

Until real provider secrets are separately authorized, the Render/Neon environment
remains synthetic. It may prove routing, disabled-provider fail-closed behavior,
browser/request security, durable PostgreSQL contracts, provider doubles below the
human routing/network boundary, recovery and exact release provenance.

It must never contain:

- real broker READ/TRADE credentials;
- private portfolio/account payloads;
- real provider secrets merely to make CI green;
- a human-accessible provider double or demo session issuer.

## 12. Pre-CI validation funnel

Before the comprehensive DRAFT cycle, run all applicable focused checks, including:

- provider transaction, route, Telegram OIDC/JWKS and VK OAuth tests;
- PostgreSQL provider-auth and product-identity tests;
- hosted request-security, rate-limit and recovery tests;
- Web contract tests, typecheck, lint and Playwright acceptance;
- repository governance/security/documentation guards;
- `ruff`, `mypy` and the repository Python test baseline;
- full branch diff and secret/private-data review.

Known failures must be fixed before another expensive exact-head cycle.

The project GREEN definition remains `success` only. `skipped`, `neutral`,
`cancelled`, queued/pending/in-progress and infrastructure failures are not GREEN for
an applicable gate.

## 13. Acceptance and rollback

This implementation remains unaccepted until the integrated branch completes:

1. exact-head DRAFT GREEN;
2. independent review required by the Phase-5 gate;
3. fresh unchanged-head READY GREEN;
4. zero unresolved blocking review threads and full diff/security/recovery review;
5. squash merge;
6. exact-new-main Regression Shield with every applicable required job `success`.

Only after that chain may a small evidence/status PR claim Phase-5 technical
acceptance or WP22A completion. This runbook never unlocks WP23 or public production
by itself.

Rollback is the last accepted protected `main`/release. No rollback may weaken the
protected V9 `app:app`, broker/Real locks, tenant isolation, provider-only human login
rule or exact-head evidence requirements.
