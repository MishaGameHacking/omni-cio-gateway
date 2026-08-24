# Omni-CIO V10 — WP22A Phase 5 VK ID OAuth 2.1 Provider Adapter

Status: **IMPLEMENTATION DRAFT / PHASE 5 ONLY / DORMANT FAIL-CLOSED**  
Block: **E — Omni-CIO Web Platform**  
WP: **WP22A — External Web Access / Product Authentication Security Gate**  
Branch base: `4066a81054b4064ca847de88647989024783f7f5`

## 1. Authority and prerequisite

This is the next focused WP22A Phase-5 source increment after the accepted Telegram
OIDC adapter. PR #385 is accepted on exact protected main
`4066a81054b4064ca847de88647989024783f7f5` through permanent Regression Shield
run `32717629717` / #1531 (`push`, exact `main`, workflow `success`) with jobs
`Quality, contracts and coverage` and `Dependency, code and secret security` both
terminal `success`.

WP22A is still not complete. WP23+, broker-write/Real execution and the Premium
Spatial Web visual refresh remain locked by their separate sequencing gates.

## 2. Purpose

Add the smallest dormant VK ID OAuth 2.1 adapter required by the accepted Phase-5
product-auth boundary and correct the shared provider callback contract so it can
carry VK ID's required `device_id` without an untyped metadata dictionary.

The successful output remains only:

`VerifiedExternalIdentityV1(provider=vk_id, subject=<verified provider user_id>)`

No product account, tenant or session is selected by provider callback data.

## 3. Current external protocol basis — revalidated 2026-08-24

The current first-party `VKCOM/vkid-web-sdk` master at commit
`8ff76cfe59ea72e370c4c6c3b40712ecfd43aadd` was used as the mutable external
protocol reference, not historical chat memory.

Current first-party evidence establishes:

- the SDK README states OAuth 2.1 support;
- current production domain constants use `vk.ru`, with VK ID at `id.vk.ru`;
- authorization uses `https://id.vk.ru/authorize`;
- the authorization query carries `client_id`, `response_type`, server state,
  `code_challenge` and lowercase `code_challenge_method=s256`; the current SDK
  also carries `app_id` and the exact configured redirect URI;
- `AuthResponse` contains `code`, `state` and required `device_id`;
- `exchangeCode(code, deviceId, codeVerifier)` POSTs to
  `https://id.vk.ru/oauth2/auth` with `code` in the form body and
  `grant_type=authorization_code`, exact redirect URI, `client_id`, PKCE verifier,
  state and `device_id` in the query;
- the SDK rejects token-exchange state mismatch;
- current `TokenResult` contains `access_token`, `state` and numeric `user_id`.

The adapter intentionally uses the verified `user_id` from the successful token
exchange and does **not** call the optional `user_info` profile endpoint. This is
strict data minimization: Omni-CIO needs a stable external subject for account
binding, not avatar, name, email, phone or other profile fields.

No VK ID client secret is introduced because the current Web SDK authorization
code + PKCE exchange does not send one. A future provider contract change must be
revalidated and reviewed rather than guessed.

## 4. Changes in this increment

1. Extend `ProviderAuthenticationRuntimeLike.complete(...)` with one typed optional
   `device_id` callback field. Do not introduce arbitrary callback dictionaries.
2. Preserve Telegram behavior and make Telegram fail closed if a VK-only
   `device_id` is supplied.
3. Add `omni_cio/web/vk_id_oauth_v1.py` with fixed VK ID origins, bounded HTTPS
   transport, duplicate-JSON rejection, exact state verification and ephemeral
   token handling.
4. Add deterministic synthetic tests for protocol compatibility, PKCE, device-id
   validation, replay/provider confusion, token/state ambiguity, response bounds,
   network failure and data minimization.

Migration required: **NO**. Dependency/lock change required: **NO**.

## 5. Security properties

- server-generated one-time state and S256 PKCE come from the accepted
  `AuthorizationTransactionRegistryV1`;
- malformed authorization code or `device_id` is rejected before state consume;
- state is consumed before provider network I/O so ambiguous provider failures are
  do-not-replay;
- provider transaction binding prevents Telegram/VK state confusion;
- authorization/token origins are fixed to current `https://id.vk.ru` endpoints;
- redirects are not followed;
- HTTPS redirect URI remains exact, default-TLS-port only, with no credentials,
  query or fragment;
- provider JSON requires HTTP 200 + `application/json`, bounded bytes and unique
  object members;
- provider error payloads, mismatched state, missing/ambiguous token fields and
  invalid user IDs fail closed;
- access/refresh/profile data is never returned as product identity, persisted or
  logged by this adapter;
- successful product output carries only provider enum + stable subject;
- provider callback fields never carry account, tenant, role or engineering
  authority.

## 6. Explicit non-goals

This increment does not:

- bind `/api/v10/web/auth/...` routes;
- provision or request real VK ID credentials;
- enable provider descriptors, registration or `PUBLIC_MULTI_USER_ENABLED`;
- create product sessions;
- mutate Render, Neon, Cloud.ru, DNS or public ingress;
- bypass the zero-cost/provider gate;
- start WP23 Telegram Bot Foundation;
- change T-Invest permission or broker credential custody;
- enable broker write, `trading_methods` or `REAL_TRADING_ENABLED`;
- implement the Premium Spatial visual refresh.

The accepted Telegram JWKS single-flight/load tradeoff remains a separate required
review before any live route/concurrency activation.

## 7. Validation plan

Before READY/merge, require all applicable repository gates plus focused evidence:

- `python -m pytest -q tests/test_v10_wp22a_phase5_provider_auth.py tests/test_v10_wp22a_phase5_telegram_oidc.py tests/test_v10_wp22a_phase5_vk_id_oauth.py`;
- `python -m ruff check .`;
- `python -m ruff format --check .` where repository policy applies;
- `python -m mypy`;
- repository boundary/security/documentation guards;
- exact-head DRAFT GREEN;
- `gitar display:verbose` review on the exact current head;
- fresh unchanged-head READY GREEN;
- zero unresolved blocking threads;
- squash merge;
- exact-new-main Regression Shield with both required jobs terminal `success`.

No historical GREEN is final evidence after a new commit.
