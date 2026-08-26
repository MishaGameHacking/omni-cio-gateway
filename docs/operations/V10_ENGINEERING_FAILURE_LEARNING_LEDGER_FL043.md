# FL-043 — Unhandled server errors must retain the hosted security response envelope

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 5; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-25**  
WP / PR / reference: **WP22A Phase 5 integrated technical closeout / PR #391 / source review after exact head `75fe2dd8`**

## Symptom / review finding

Phase-5 source review found that ordinary responses and explicit `_safe_error(...)` paths were hardened by `HostedPreviewSecurityMiddlewareV1`, but an unexpected endpoint exception could escape that installed middleware and be converted into the framework's outer 500 response path.

The resulting response was not structurally guaranteed to retain the Phase-5 security envelope: API `Cache-Control: no-store`, HSTS, CSP, `X-Content-Type-Options`, referrer policy, opener isolation and `Vary: Origin, Sec-Fetch-Site`.

This is a material browser/API failure-mode gap even when the exception body itself is generic. A degraded path must not silently become a weaker cache/security-header path.

## Root-cause analysis

The application relied on response hardening in installed middleware:

`endpoint -> HostedPreviewSecurityMiddlewareV1 -> _harden_response(response)`

Starlette places `ServerErrorMiddleware` as the outermost application layer. Unexpected application errors therefore bubble through installed middleware as exceptions and are handled by the outer server-error layer. Response mutation that occurs only after `call_next(...)` returns is not a reliable authority for those errors.

The reusable design error was assuming that a normal-response middleware post-processing step also protects every unhandled-error response.

## Blast radius searched

The review covered:

- the complete `HostedPreviewSecurityMiddlewareV1` response path;
- all `_safe_error(...)` and `_rate_error(...)` callers;
- hosted FastAPI endpoints that already catch known database/provider failures;
- provider routes and product endpoints where an unexpected runtime exception can still occur;
- API/private cache policy versus Web document cache policy;
- HSTS, CSP, COOP, nosniff, referrer and `Vary` headers;
- Starlette/FastAPI exception-handler composition;
- protected V9, broker authority, tenant identity and public-production locks.

No second exception stack, proxy authority, broker path or provider bypass is introduced.

## Corrective change

`create_hosted_preview_app(...)` now registers an application-wide `Exception` handler that returns only the sanitized error code `INTERNAL_ERROR` through the existing `_safe_error(...)` path.

The handler classifies the request with the same API-path rule used by hosted security middleware, so:

- `/api/*` and `/healthz` unexpected failures remain `Cache-Control: no-store`;
- Web/document unexpected failures remain `Cache-Control: no-cache`;
- both retain the complete hosted hardening header set;
- raw exception text is never returned to the browser.

The normal middleware path is unchanged. Known domain/provider/database failures retain their existing bounded fail-closed responses.

## Permanent regression / guard

A deterministic hosted-app regression injects test-only crashing API and Web routes ahead of the production catch-all routes and uses `TestClient(..., raise_server_exceptions=False)` to observe the real 500 response.

It proves for both API and Web error classes that:

- status is exactly `500`;
- payload is exactly `{\"detail\": \"INTERNAL_ERROR\"}`;
- the synthetic sensitive exception marker is absent;
- cache policy is `no-store` for API and `no-cache` for Web;
- HSTS, CSP, COOP, nosniff and referrer headers remain present;
- `Vary` retains both `Origin` and `Sec-Fetch-Site`.

The full exact-head GitHub CI/security cycle remains required after this guard is committed.

## Future prevention rule

For hosted security headers and private cache policy:

1. identify framework-generated error responses separately from normal endpoint responses;
2. do not assume post-`call_next` middleware mutation protects exceptions that never return a response through that middleware;
3. sanitize and harden unexpected 500 responses at the framework error-handler boundary itself;
4. regression-test both API/private and Web/document error classes;
5. never expose exception text, secrets, provider material, session material or tenant-private payloads merely to improve diagnostics;
6. treat missing cache/security headers on degraded paths as a security defect, not cosmetic inconsistency.

## Dependency/tooling knowledge change

No dependency update is required. The correction uses the existing FastAPI/Starlette exception-handler mechanism and existing `_safe_error(...)` hardening path. Official Starlette middleware/exception documentation confirms that `ServerErrorMiddleware` is the outermost layer and that `Exception`/500 handlers are the intended server-error boundary.
