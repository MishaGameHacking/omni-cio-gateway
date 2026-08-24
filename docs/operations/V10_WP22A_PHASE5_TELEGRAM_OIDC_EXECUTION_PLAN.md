# Omni-CIO V10 — WP22A Phase 5 Telegram OIDC Provider Adapter

Status: **IMPLEMENTATION DRAFT / PHASE 5 ONLY / LANDING FAIL-CLOSED**  
Block: **E — Omni-CIO Web Platform**  
WP: **WP22A — External Web Access / Product Authentication Security Gate**  
Branch base: `5343de4ae6f8e9c33f3c8d8fd85566946995eb8d`

## 1. WP identity and authority

This is the second focused WP22A Phase-5 source increment. It is authorized by
`knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`,
`V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_AUTHORIZATION.md`, and the Phase-5
provider-auth transaction execution plan.

The prior transaction-core increment is accepted through PR #384, protected
squash merge `5343de4ae6f8e9c33f3c8d8fd85566946995eb8d`, and permanent canonical
Regression Shield #1530 SUCCESS with both required jobs GREEN.

WP22A is not complete, WP23+ remains locked, and the Premium Spatial visual
refresh remains planning-only until separate accepted canonical authority
explicitly unlocks that named runtime increment.

## 2. Purpose

Implement the smallest dormant Telegram OIDC provider adapter required to turn
an already-consumed server-side authorization transaction into a
`VerifiedExternalIdentityV1`:

`transaction core -> Telegram auth URL -> server-side code exchange -> fixed Telegram JWKS -> RS256 + claim validation -> VerifiedExternalIdentityV1`

This increment stops before API route/composition wiring, product-account session
issuance, public registration, provider credential provisioning or deployment.

## 3. Current external protocol basis

Current official Telegram Login documentation was revalidated on 2026-08-24.
It specifies standard OIDC Authorization Code flow with PKCE, the fixed issuer
`https://oauth.telegram.org`, authorization endpoint `/auth`, token endpoint
`/token`, JWKS endpoint `/.well-known/jwks.json`, required `openid` scope,
server-side token exchange with Client ID/Secret and PKCE verifier, and
cryptographic ID-token verification. Telegram documents RS256 as the default
signing algorithm and supports a server-generated nonce included in the
resulting ID token.

The adapter intentionally pins the accepted RS256 profile rather than accepting
a provider- or token-selected algorithm family. A later algorithm change is a
reviewed configuration/protocol change, not an automatic compatibility path.

The local RS256 implementation is protected by the official RFC 7515 Appendix
A.2 RSASSA-PKCS1-v1_5 SHA-256 known-answer vector plus tamper rejection.

## 4. Accepted implementation reused

- `omni_cio/web/provider_auth_v1.py` — accepted bounded one-time state, PKCE,
  nonce and exact callback transaction boundary;
- `omni_cio/web/identity_v1.py` — canonical provider enum and
  `VerifiedExternalIdentityV1`;
- `omni_cio/web/product_identity_v1.py` — downstream verified identity ->
  internal account/tenant/session boundary, not wired by this increment;
- locked runtime dependency `httpx==0.28.1` — bounded provider HTTPS transport;
- existing `apps/web` / `apps/api` remain the one product path.

No dependency or lock-file change is required.

## 5. Allowed changes

The functional increment changes only:

1. `omni_cio/web/telegram_oidc_v1.py`;
2. `tests/test_v10_wp22a_phase5_telegram_oidc.py`;
3. this execution-plan record.

After the first DRAFT exact-head cycle exposed a reusable static-contract
preflight miss, governance additionally requires the additive engineering-memory
record:

4. `docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER_FL038.md`.

That fourth file records the failed validation cycle only; it does not widen
product/runtime scope. No migration or durable persistence change is introduced.

## 6. Security and authority contract

The adapter must fail closed on every ambiguous provider result.

Required properties:

- exact fixed Telegram issuer/auth/token/JWKS origins;
- exact HTTPS callback URI with default TLS port and no credentials, query or
  fragment;
- minimal `openid` scope only; no phone/profile/message permission request;
- server-generated state, S256 PKCE challenge and nonce from the accepted
  transaction registry;
- PKCE verifier and Client Secret never enter the authorization URL;
- callback authorization code must be bounded visible ASCII;
- state is consumed before provider network exchange, so a failed/ambiguous
  provider call cannot replay the same login transaction;
- provider redirects are not followed;
- token/JWKS responses require HTTP 200 + `application/json` and are bounded by
  explicit byte limits;
- duplicate JSON members are rejected;
- token response access/refresh payload is not persisted and is cleared after
  extracting the ID token;
- JWT compact serialization and base64url components are strictly bounded;
- header `alg` is exactly `RS256`; `crit`, `jku`, embedded `jwk`, `x5u`, `x5c`
  and `b64` override surfaces are rejected;
- JWK must be a bounded RSA signing key, optional JWK `alg` may only be RS256,
  optional `key_ops` must permit verification, duplicate `kid` is rejected,
  leading-zero modulus/exponent encodings are rejected, RSA modulus is
  2048–4096 bits and exponent is bounded/odd;
- signature verification uses exact EMSA-PKCS1-v1_5 SHA-256 encoding and
  constant-time final byte comparison;
- claims require exact issuer, exact audience/client ID, exact transaction
  nonce, bounded subject, integer `iat`/`exp`, sensible temporal ordering,
  expiry validation and bounded clock skew; `nbf`, when present, is enforced;
- JWKS cache is short-lived; refresh is serialized so concurrent cache misses do
  not amplify into one provider request per login, and an unknown `kid` while
  the cache is fresh fails without repeated network fetch;
- config representation omits the Client Secret;
- the only successful product output is
  `VerifiedExternalIdentityV1(provider=telegram, subject=<verified sub>)`.

No raw Telegram Client Secret, token, user profile, phone, access/refresh token,
tenant selector or broker secret is committed, logged or persisted by this
component.

## 7. Explicit non-goals

This increment does **not**:

- wire `/api/v10/web/auth/telegram/start` or callback routes;
- provision BotFather/OIDC credentials or request an OWNER secret;
- enable Telegram provider descriptors in production;
- create an Omni-CIO session directly;
- enable public registration or `PUBLIC_MULTI_USER_ENABLED`;
- implement VK ID yet;
- mutate Render, Neon, Cloud.ru, DNS or public ingress;
- add recurring provider spend;
- alter T-Invest/public broker permission;
- enable broker write, `trading_methods` or `REAL_TRADING_ENABLED`;
- start WP23 Telegram Bot Foundation;
- implement the Premium Spatial visual refresh.

## 8. Data, persistence and recovery

Migration required: **NO**.

All provider transaction state remains ephemeral and fail-closed as already
accepted. A runtime restart invalidates in-flight login attempts. JWKS cache is
in-memory and safely refetched after restart. No provider token is durable.
Rollback is source-only: remove the dormant adapter/tests or revert the squash
merge; no database/private-state recovery is required.

## 9. Pre-CI readiness and first DRAFT correction

Cheap scratch preflight before opening repository CI:

- Python compile of adapter and focused tests: PASS;
- 23 focused deterministic tests: PASS;
- maximum changed Python line length <= 88: PASS;
- dependency/lock changes: NONE;
- provider/network calls: synthetic `httpx.MockTransport` only;
- official Telegram OIDC protocol revalidated from current primary docs;
- RFC 7515 RS256 known-answer and tamper negative: PASS;
- high-entropy public RFC fixtures split into short fragments so the repository
  secret scanner can evaluate the changed surface without a secret-shaped
  standalone literal;
- no real secrets/private identities/tenant/broker payloads used.

The first exact-head DRAFT cycle on `a1f65a98492e0d6558615223f57f0494bb1a1fc6`
correctly found a missing static-contract preflight condition. `V10 WP20 Research
Dossier Audit` run `32679858247` passed its frontend/browser/audit stages and then
failed repository-wide mypy because `_b64url_decode` declared `str` while the
JWK `n`/`e` callers correctly provided untrusted `Any | None` values from JSON.

Root-cause review confirmed that `_b64url_decode` itself is the runtime type
validator. Its input contract was corrected to `object`, preserving the existing
`isinstance(value, str)` fail-closed narrowing rather than adding casts, ignores
or mypy suppression. The scratch compile + focused suite remained GREEN after
that correction. FL-038 records the reusable lesson. Any evidence from the old
head is non-final and invalidated by the corrective commit.

Exact repository Ruff, mypy, tracked-content secret scan, SAST, dependency audit
and all other applicable workflows remain independent CI evidence; scratch
preflight is not substituted for those gates.

## 10. Normal-path acceptance tests

Focused tests must prove:

- authorization URL uses only the fixed Telegram endpoint, `openid`, state,
  S256 challenge and nonce;
- Client Secret and PKCE verifier are absent from the browser URL;
- callback consumes state exactly once and performs server-side token exchange;
- token exchange uses the exact fixed endpoint and Basic authentication;
- verified ID token produces only Telegram `VerifiedExternalIdentityV1`;
- fixed official JWKS URL is the only key-fetch origin;
- concurrent JWKS cache miss performs one bounded fixed-origin refresh;
- RFC 7515 RS256 known-answer validates.

## 11. Negative/failure tests

Focused tests cover:

- invalid Client ID/callback/code;
- provider redirect/non-200, network failure and oversized response;
- one-time transaction destruction after provider/network failure;
- invalid/tampered signature;
- `HS256`/JWK algorithm-confusion attempts;
- external/embedded JWK/header override attempts;
- issuer/audience/nonce/subject/time mismatch;
- unknown `kid` request-amplification resistance while cache is fresh;
- concurrent cache-miss request-amplification resistance;
- duplicate provider JSON members;
- secret omission from config representation.

Any unexpected material CI RED after this preflight requires root-cause,
blast-radius, analogous-pattern, coupled-consumer and adjacent-failure review
before another expensive final cycle, with failure-learning update when reusable.

## 12. Fault isolation / degraded mode

Telegram OIDC is an optional authentication dependency during this dormant
increment. Provider timeout/network/invalid response yields only a fail-closed
authentication error; deterministic Core, V9 `app:app`, existing Web data and all
broker safety boundaries remain unchanged. There is no retry loop in this
component and no automatic algorithm/origin fallback.

## 13. CI routing and Exit Gate

The branch may land only after:

1. all applicable exact-head DRAFT checks actually execute and conclude
   `success` on the post-correction head;
2. focused provider-auth/OIDC tests, Ruff format/lint, mypy, dependency/security
   and repository governance gates are GREEN;
3. full four-file diff is reviewed against exact accepted base;
4. Gitar/security review has no unresolved material finding;
5. unresolved blocking review threads = 0 and no P0/P1 blocker remains;
6. a fresh READY cycle on the unchanged head has every applicable check
   `success`;
7. protected squash merge only;
8. exact new `main` is captured and permanent canonical post-merge Regression
   Shield is proven `success` with both required jobs GREEN.

`failure`, `cancelled`, `queued`, `pending`, `in_progress`, `timed_out`,
`action_required`, `neutral` or `skipped` are not GREEN for an applicable gate.
Any new commit invalidates previous final exact-head evidence.

## 14. OWNER participation

OWNER action required before merge: **NO**.

No real Telegram Client ID/Secret is required for this dormant deterministic
increment. Credential provisioning, provider Allowed URL registration or other
non-delegable provider action belongs only to a later focused Phase-5 binding /
deployed-acceptance increment after its own source gate.

## 15. Rollback and next authorized work

Before merge: close the PR; accepted `main` remains unchanged.  
After merge: adapter remains dormant until a separately reviewed route/composition
increment binds it to the existing Web API and product authentication service.

Acceptance of this increment does not itself authorize VK ID, public activation,
WP23 or visual-refresh runtime work. The exact next Phase-5 increment is selected
only from then-current accepted `main` and canonical status after this increment's
post-merge Regression Shield is GREEN.
