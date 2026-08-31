# V10 Engineering Failure Learning Ledger — FL065

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, gate CF-C LIVE.

This entry records two coupled exact-head defects discovered after Cloudflare Workers Builds authority became valid. It does not grant CF-C acceptance and does not authorize CF-D.

## Failure

On exact head `800c7ff02f8d67d2db5418eaaee0d97b62fb4151`:

1. `V10 Cloudflare Provider Readiness` passed, proving the protected user-scoped token had the required Workers Builds authority.
2. `V10 Cloudflare Candidate Deployment` reached a real Cloudflare build, but the build terminated with failure. The failure-path diagnostic reported only `CLOUDFLARE_BUILD_LOG_DIAGNOSTIC_UNAVAILABLE`, so the repository could not establish the provider build root cause from sanitized CI evidence.
3. The authoritative self-hosted Windows gate independently rejected the same head because `ruff format --check` found two Python formatting drifts introduced by the previous correction commit.

The correct response is a source correction batch, not a weakened provider or quality gate.

## Root cause

The build-log helper called the correct Cloudflare Workers Builds endpoint, but `_safe_build_failure_diagnostic()` caught every `BootstrapStopped` condition and collapsed the diagnostic failure to one generic code. Cloudflare's official Builds API documents `404` as a valid error response for the build-log endpoint and models `lines` as optional. The implementation had no bounded log-readiness retry and discarded the sanitized exception code/status needed to distinguish transient log availability from authority/schema/provider failures.

Separately, the previous correction head was published without re-running the formatter against all touched Python files, leaving two deterministic formatting violations for the exact-head CI gate to catch.

## Blast radius

- Every terminal CF-C Workers Build used the same diagnostic path, so any log retrieval failure could become opaque.
- Retrying all Cloudflare `404` responses globally would be unsafe because resource-not-found is normally authoritative. The retry therefore belongs only to failed-build log retrieval, where the provider exposes a dedicated logs resource after a known build UUID already exists.
- The formatting defect class applies to every Python source file in a correction batch and must be caught before publication rather than delegated to expensive exact-head CI.

## Durable prevention

1. Retry only build-log `CLOUDFLARE_API_HTTP_ERROR status=404` with a short bounded backoff; do not broaden the global Cloudflare API retry policy.
2. Preserve fail-closed behavior after the bounded retry budget is exhausted.
3. Emit only sanitized diagnostic enum/status metadata; never emit provider bodies, tokens, headers, account identifiers or private runtime data.
4. Accept omitted `lines` as the documented optional field while continuing to validate any supplied log-line structure.
5. Add deterministic regression tests for eventual `404 -> logs available`, persistent `404`, non-404 authority failure without retry, and omitted optional log lines.
6. Keep a repository contract guard for the build-log retry/diagnostic markers so future edits cannot silently restore opaque failure handling.
7. Run formatter/static preflight over every touched Python file before publishing a correction head.

## Security and authority invariants preserved

- Provider authority checks are not bypassed or downgraded.
- Retry is read-only, bounded and scoped to an already-known failed build UUID.
- No secret or provider response body is logged.
- No production promotion is performed by this correction.
- `PUBLIC_MULTI_USER_ENABLED=false` remains protected until its CF-D/capability gates.
- `REAL_TRADING_ENABLED=false` remains protected.
- `trading_methods=false` remains protected.
- broker write remains OFF.
- CF-D remains blocked until CF-C exact-head candidate acceptance succeeds.

## External reference

Cloudflare's current official Workers Builds API documents `GET /accounts/{account_id}/builds/builds/{build_uuid}/logs`, cursor-based pagination, optional `lines`, and a `404` error response for the logs resource. This evidence justifies a narrow failed-build log-readiness retry; it does not justify global not-found retries or fabricated candidate success.
