# V10 Engineering Failure Learning — FL164

Failure class: `CF_D_POSTMERGE_GITHUB_READ_HTTP_500_NOT_RETRYABLE`

Date: 2026-09-18

Scope: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D / exact-main release evidence transport`

## Observed failure

V10 Cloudflare Production Release #81 on exact accepted main
`e9514619dcfba2d9afe64c47c78d08b1f5267f0d` started only after exact-main
Regression Shield, Engineering Governance and all owning push audits were successful.

The release stopped before any Cloudflare, Neon or production mutation in:

`CF-D exact-main database state and staging anchor -> Require all exact-main post-merge push workflows`

with:

`CLOUDFLARE_POSTMERGE_GATE=STOPPED code=CLOUDFLARE_POSTMERGE_GITHUB_HTTP_ERROR status=500`

The same log independently certified the accepted equivalent-tree Sonar provenance, so
the failure was not Sonar evidence drift.

## Root cause

`scripts/check_v10_cloudflare_postmerge_release_gate.py::_api_get()` is a bounded
transport used only for authenticated GitHub REST `GET` reads of exact-main workflow,
check, pull-request, event, commit-tree and check-suite evidence.

Its explicit transient HTTP allowlist covered `408/429/502/503/504`, but not `500`.
A single GitHub `500 Internal Server Error` therefore became terminal even though
replaying the same idempotent read inside the already bounded three-attempt budget
cannot duplicate provider mutation.

This is not authority failure: `401/403` remain separately classified and terminal.

## Blast radius

The shared `_api_get` transport is also reused by
`check_v10_sonar_equivalent_tree_provenance.py`, so the missing `500` classification
affected all read-only GitHub evidence paths behind the CF-D post-merge gate.

The repair does not change:

- Cloudflare API retry policy;
- Neon/provider retry policy;
- any POST/PUT mutation replay rule;
- Telegram/provider secret custody;
- public multi-user or provider activation flags;
- broker-write or Real execution authority.

## Permanent correction

Add only HTTP `500` to the existing read-only GitHub GET transient allowlist:

`408/429/500/502/503/504`

Keep the existing attempt/time bound unchanged:

- maximum three attempts;
- backoff `1s -> 2s`;
- no fourth request;
- exhaustion remains
  `CLOUDFLARE_POSTMERGE_GITHUB_HTTP_ERROR status=500`.

`401/403` remain non-retryable authority failures. Diagnostics remain code/status only;
GitHub response reason/body and token values are not propagated.

GitHub's REST troubleshooting guidance documents server-error/time-out conditions as
conditions that can be tried again later, while its best-practice guidance requires
repeated 4xx/5xx failures to remain errors rather than being ignored. The correction
therefore adds bounded resilience without converting repeated server failure into GREEN.

## Permanent regression guards

Deterministic tests prove:

- one `500` followed by `200` recovers successfully;
- three consecutive `500` responses perform exactly three GET attempts with
  `1s/2s` backoff and then fail closed;
- `401` and `403` perform exactly one attempt and never sleep/retry;
- terminal diagnostics do not echo the HTTP reason or token;
- the pre-existing `503 -> 200` transient regression remains intact.

## Acceptance requirement

Source change alone does not close FL164.

The exact branch head must pass focused preflight, applicable DRAFT and READY checks,
Sonar/security/review and zero blocking threads, then squash-merge. Exact-new-main
Regression Shield, Engineering Governance and owning audits must be successful. A fresh
V10 Cloudflare Production Release must then pass the exact-main post-merge evidence gate,
production promotion and terminal DAG without relying on blind reruns.

Issue: #552.
