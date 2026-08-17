# V10 CI Action Download Resilience

Status: MAINTENANCE IN PROGRESS

## Root cause

Mandatory self-hosted V10 jobs can fail before repository code executes when the runner cannot download pinned external Actions from `codeload.github.com`. The reproduced failures on PR #327 include HTTP 429 and 503 while preparing `actions/checkout` and `actions/upload-artifact`.

## Required correction

The mandatory PR and post-merge authority plane must not depend on downloading non-authoritative helper Actions before project checks can execute. Repository bootstrap must remain exact-SHA, fail closed, use only job-scoped repository read authority, and remove temporary Git credentials immediately after fetch. Diagnostic transport must not become merge authority.

## Invariants

- no weakening of tests, Regression Shield, dependency audit, SAST, secret scanning, or exact-head verification;
- no repository, provider, broker, Telegram, portfolio, or runtime secrets;
- `app:app` remains protected;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no broker-write expansion;
- WP22A remains current; WP23+ remains locked.

This maintenance package carries zero product-progress credit.
