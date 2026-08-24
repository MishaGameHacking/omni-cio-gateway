# Omni-CIO V10 — WP22A Phase 5 Provider Auth Transaction Core

Status: **IMPLEMENTATION DRAFT / PHASE 5 ONLY / LANDING FAIL-CLOSED**  
Block: **E — Omni-CIO Web Platform**  
WP: **WP22A — External Web Access / Product Authentication Security Gate**  
Branch base: `00d6ac63ef9d5822cf24aa1ea148864f60eabd38`

## 1. Authority and prerequisite

`knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` and
`V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_AUTHORIZATION.md` authorize Phase 5
source and acceptance work after the accepted Phase-4 transition. This increment
stays inside that Phase 5 scope.

The branch base contains PR #381, which records Phase-4 acceptance and Phase-5
authorization. Direct exact-main Regression Shield evidence for the base SHA is
still a mandatory landing prerequisite. If that evidence cannot be proved from
the real GitHub Actions/API surface, this PR remains unmerged; no synthetic
verification commit/branch/PR may be created to manufacture evidence.

## 2. Purpose

Create the smallest reusable server-side OAuth/OIDC authorization transaction
boundary needed before real Telegram Login or VK ID adapters can be bound:

`provider start -> random state + PKCE + nonce -> bounded server-side pending state -> one-time callback consume -> verified-provider adapter`

This increment deliberately stops before provider network calls and credentials.

## 3. Accepted implementation reused

- `omni_cio/web/identity_v1.py` owns `telegram`, `vk_id` and
  `VerifiedExternalIdentityV1`.
- `omni_cio/web/product_identity_v1.py` owns verified external identity ->
  internal account/tenant binding and fixation-safe server-side session issuance.
- `omni_cio/web/session_v1.py` owns opaque bounded server-side sessions.
- Existing `apps/web` and `/api/v10/web/auth/{provider}/start` remain the only Web
  product path; no second frontend/API/identity stack is introduced.

## 4. Allowed changes

This focused increment may add only:

1. a provider-auth transaction primitive under `omni_cio/web`;
2. deterministic focused tests for that primitive;
3. this execution-plan record.

No existing runtime route is activated in this increment.

## 5. Security and failure contract

Required properties:

- cryptographically random OAuth `state`, PKCE verifier and OIDC nonce;
- S256 PKCE challenge;
- raw `state` is not retained server-side; only its SHA-256 lookup digest is kept;
- PKCE verifier stays server-side and is not exposed by the authorization-start
  value; verifier and nonce are removed after consume/expiry;
- exact provider binding prevents a Telegram transaction being consumed as VK ID;
- callback state is one-time under concurrent requests;
- replay, expiry, malformed state and provider mismatch fail closed;
- pending transactions have finite TTL, a hard maximum of 4096, and default cap
  1024;
- expired-entry scans are lazy: normal operations are O(1) before the next known
  expiry boundary, avoiding a full pending-registry scan on every request;
- only exact HTTPS callback URIs on default TLS port are accepted; credentials,
  query strings and fragments are rejected;
- runtime restart invalidates in-flight authorization attempts rather than trying
  to recover ambiguous ephemeral proof. The user may retry login; durable account
  or session truth is not changed by an uncompleted transaction.

No provider token, bot/client secret, raw user identity, tenant selector or broker
secret is persisted or logged by this component.

## 6. Explicit non-goals

This increment does **not**:

- configure or call Telegram/VK;
- add provider secrets to source, GitHub, CI or artifacts;
- validate a Telegram/VK token yet;
- enable registration or `PUBLIC_MULTI_USER_ENABLED`;
- mutate Render, Neon or Cloud.ru;
- authorize paid infrastructure;
- change T-Invest/public broker permission;
- enable broker write, `trading_methods` or Real execution;
- start WP23 Telegram Bot work;
- implement the Premium Spatial visual refresh, which remains separately locked.

## 7. Pre-CI readiness

Cheap focused preflight before the first repository CI cycle:

- Python compile of the new module;
- focused transaction tests for PKCE/state/replay/expiry/capacity/concurrency;
- line-length/import review against repository style;
- no dependency or lock-file change;
- full branch diff review before READY.

The local scratch preflight used no real secrets/provider calls and passed 13
focused cases before the repository PR was opened. After Gitar identified the
O(n)-per-operation expiry scan as a future auth-path DoS risk, the registry was
changed to lazy expiry scanning with a hard 4096 cap and focused expiry/capacity
coverage was rerun before refreshing exact-head CI.

## 8. Normal and negative acceptance

The focused test suite must prove:

- generated state and PKCE verifier satisfy bounded URL-safe form while the
  verifier never leaves the server-side pending transaction before consume;
- PKCE challenge equals base64url(SHA-256(verifier)) without padding;
- wrong provider cannot consume another provider's state;
- successful consume is one-time;
- expired state is destroyed and later-expiring state remains valid;
- full pending capacity fails closed but expired entries are purged;
- configured capacity above the hard maximum is rejected;
- HTTP, credential-bearing, non-443, query-bearing, fragment-bearing and malformed
  callback URIs are rejected;
- concurrent callback attempts yield exactly one successful consume;
- naive clocks and malformed/non-base64url state are rejected.

## 9. CI routing and Exit Gate

Applicable repository checks must execute on the real PR head and conclude
`success`. `failure`, `cancelled`, `queued`, `pending`, `in_progress`, `skipped`
or `neutral` are not GREEN evidence.

Before landing:

- direct exact-main Regression Shield evidence for base `00d6ac63...` is proven;
- focused tests, Ruff format/lint, mypy and applicable repository/security gates
  are SUCCESS on the unchanged PR head;
- full diff reviewed;
- unresolved blocking review threads = 0;
- no P0/P1 blocker;
- squash merge only;
- exact new main obtained and its post-merge Regression Shield proven directly,
  without temporary verification commits.

## 10. Rollback and next increment

Before merge: close the PR; accepted main is unchanged.  
After merge: the component is dormant until a provider adapter is explicitly
wired; rollback is source-only and contains no migration/private-state effect.

The next allowed Phase-5 increment after acceptance is a reviewed real provider
adapter, beginning with Telegram's current OIDC Authorization Code + PKCE flow
and cryptographic ID-token validation. VK ID follows through the same internal
boundary. Neither increment unlocks the visual refresh or WP23 by itself.
