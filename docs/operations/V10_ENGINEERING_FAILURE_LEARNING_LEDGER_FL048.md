# FL-048 — Request-derived CSRF material must not be reflected into response headers

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 5; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-26**  
WP / PR / reference: **WP22A Phase 5 integrated technical closeout / PR #391 / exact-head Sonar Security Rating follow-up**

## Symptom / failing gate

Exact head `1e3ed22ba6d7fccc31ec701d5c54b0766b35042c` was re-analyzed by SonarQube Cloud after the fresh session token CSPRNG call was moved into the cookie-writing module. The Quality Gate still failed with **Security Rating on New Code = B** while the required rating is **A**. The Sonar check reported the same 17 GitHub annotations as the prior head.

This result disproved the working hypothesis that the remaining finding was caused by the CSPRNG origin being hidden behind the imported `new_session_token_v1()` helper. The experimental direct `secrets.token_urlsafe(...)` mint is therefore reverted instead of being retained as analyzer-driven architectural noise.

The available GitHub integration exposes the exact-head Sonar Quality Gate result but does not permit retrieval of the private check-run annotation payload, and the private Sonar project does not expose issue-level details anonymously. This entry therefore does **not** claim the exact private Sonar rule or finding text.

## Root-cause analysis

A fresh production-only source/sink review found a direct framework boundary that existed from the opening Phase-5 integrated diff:

`Request.cookies[__Host-omni_v10_csrf] -> csrf -> Response.headers[X-Omni-CSRF]`

`GET /api/v10/web/session` read the browser CSRF cookie and, after validating it with the server-side session-bound HMAC policy, echoed the same raw string into the `X-Omni-CSRF` response header.

Runtime validation was already strict: `BrowserCookiePolicyV1.csrf_matches()` requires the exact URL-safe 43-character token shape and verifies the HMAC binding to the live server-side session. That prevents CR/LF material from being accepted in practice. However, the response-header echo was still structurally unnecessary and forced reviewers/static analyzers to understand a custom sanitizer before proving that request-derived data could not reach a response-header sink.

The browser never required this response transport. The CSRF cookie is intentionally `HttpOnly=False`, `Secure`, `__Host-` scoped, and same-origin. The browser API client already contains a cookie reader and can copy that same-origin CSRF cookie into the `X-Omni-CSRF` request header for unsafe methods. The server then validates exact cookie/header equality plus the session-bound HMAC.

## Blast radius searched

The review covered:

- every Phase-5 `Response.headers[...]` and explicit response-header construction path;
- the hosted session endpoint and request-security middleware;
- CSRF cookie generation, shape validation, HMAC binding and comparison;
- browser `requestHeaders()` and `requestJson()` CSRF transport;
- logout and revoke-all flows;
- provider callback session/CSRF cookie issuance;
- API cache/security headers and `Vary` handling;
- existing backend and frontend CSRF contract tests;
- the prior session CSPRNG experiment, which exact-head Sonar evidence disproved;
- protected tenant, provider, broker and Real-execution authority boundaries.

No other Phase-5 response header requires request-derived CSRF material.

## Corrective change

The CSRF contract is reduced to one browser-visible source of truth:

1. successful authentication sets the session-bound `__Host-omni_v10_csrf` cookie;
2. `GET /api/v10/web/session` validates the cookie against the live session but does not reflect it into any response header;
3. the browser reads only the same-origin CSRF cookie when preparing an unsafe request and copies it to `X-Omni-CSRF`;
4. middleware requires the session cookie, CSRF cookie and CSRF request header, compares cookie/header in constant time, and verifies the HMAC binding;
5. logout/revoke-all no longer maintain an independent in-memory CSRF cache because no such cache is needed.

The exact request security policy is therefore unchanged while the unnecessary request-to-response dataflow is removed.

The disproved direct session-token mint experiment is reverted to the accepted named `new_session_token_v1()` primitive. Session issuance remains `resolve -> revoke -> input-free CSPRNG mint -> bind -> Set-Cookie`.

## Permanent regression / guard

Deterministic contracts now prove that:

- authenticated `/api/v10/web/session` does **not** emit `X-Omni-CSRF`;
- the valid same-origin CSRF cookie remains present after provider authentication;
- browser product code reads the CSRF token from `__Host-omni_v10_csrf` only;
- browser product code does not cache a response-derived CSRF token and does not read `X-Omni-CSRF` from responses;
- unsafe requests still send `X-Omni-CSRF` from the cookie;
- Web Storage remains forbidden for credentials;
- server middleware still enforces exact Origin, Fetch Metadata, cookie/header equality and session-bound HMAC validation.

A fresh exact-head Sonar Security Rating **A** remains mandatory. No `NOSONAR`, rule exclusion, hotspot dismissal, quality-profile change or reduced security gate is introduced.

## Future prevention rule

For browser security tokens and response metadata:

1. do not reflect request-derived credential or anti-CSRF material into response headers when the browser already has an authenticated same-origin source;
2. prefer one credential transport source of truth over mirrored cookie/header caches;
3. keep custom validation as defense in depth, but remove unnecessary source-to-sink paths rather than relying on analyzers/reviewers to infer custom sanitizers;
4. preserve server-side binding and constant-time comparisons when simplifying browser transport;
5. when an exact-head independent analyzer disproves a diagnostic refactor, revert the refactor instead of accumulating analyzer-only architecture;
6. treat the next exact-head analyzer result as proof or disproof of the new hypothesis, never as a reason to suppress the gate.

## Dependency/tooling knowledge change

No dependency update is required. The change uses the existing `__Host-` cookie policy, HMAC CSRF binding, Fetch API credentials policy and server request-security middleware. SonarQube Cloud Security Rating A remains the unchanged independent acceptance gate.
