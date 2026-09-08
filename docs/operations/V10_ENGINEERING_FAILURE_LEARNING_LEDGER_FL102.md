# V10 Engineering Failure Learning Ledger — FL102

Date: 2026-09-08  
Scope: CF-D pinned workerd Request redirect-mode incompatibility  
Authority: Amendment 8 + Amendment 12 + Amendment 14 + Amendment 15 + `V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`

## Accepted precursor

PR #464 resolved the earlier branch-request phase-classification gap and was accepted into
protected `main` as `ba032f0f23311bf6117d9415f7d98a46e62173f0` after unchanged-head READY
verification. Exact-new-main Regression Shield run `34212392929` completed both protected
quality/coverage and dependency/SAST/tracked-secret jobs successfully, and all 11 exact-main
push workflows completed `success`.

Fresh automatic `V10 Cloudflare Production Release` run `34213455114`, job `102019599134`,
then passed exact-main post-merge authority, Cloudflare provider authority, Workers Builds,
the pinned delivery toolchain, Containers registry read authority, exact staging Build,
single-active-version proof and pre-custody exact-SHA release attestation.

The staging rehearsal stopped before production mutation with the newly bounded class:

`CLOUDFLARE_CF_D_NEON_BRANCH_REQUEST_INVALID status=502`

Staging trigger quarantine and cleanup succeeded. Production database/runtime preparation,
production Worker promotion, Custom Domain mutation and live acceptance were skipped.

## Exact root cause

The repository lock pins Wrangler `4.127.1` and workerd `1.20260828.1`. Direct inspection of
the matching upstream Cloudflare workerd tag `v1.20260828.1` establishes the runtime contract:

- `Request::Redirect` contains only `FOLLOW` and `MANUAL`;
- `Request::tryParseRedirect()` recognizes only `follow` and `manual`;
- `Request::constructor()` rejects any other redirect value and explicitly says that `error`
  is not implemented at the edge and that callers should use `manual` and inspect the response
  status code.

The accepted Omni Worker branch lookup constructed:

```text
new Request(validatedNeonSqlUrl, { ..., redirect: "error", ... })
```

Therefore the exact pinned runtime deterministically threw during Request construction before
`fetch()` transport. PR #464 correctly classified that synchronous exception as
`CLOUDFLARE_CF_D_NEON_BRANCH_REQUEST_INVALID`; the production rehearsal made the underlying
runtime incompatibility observable without exposing raw exception text or secret-bearing
request material.

Current public Cloudflare Request documentation still lists `error` as a Request redirect mode.
That documentation/runtime discrepancy must not override the exact dependency lock plus the
actual production-runtime evidence.

## Why previous tests passed

The executable Web regressions run on the repository Node toolchain. Node's Fetch/Request
implementation accepts `redirect: "error"`, so local request construction succeeded and the
suite correctly exercised later transport/status/body behavior. The test environment therefore
did not model this workerd-specific constructor restriction.

The regression was not a missing generic Request test. It was a runtime-compatibility gap
between Node's standards-facing implementation and the exact pinned Worker engine.

## Blast radius

The review covered every explicit Worker `new Request(...)` site in the CF-D egress path.
The other inspected Worker requests already use `redirect: "manual"`. The separate Neon
bootstrap Function uses direct `fetch(url, init)` in its own Node runtime and is not the failing
Worker constructor path.

The relevant security invariant is not the spelling of `error`; it is that provider redirects
must never be followed. `manual` is the workerd-supported fail-closed primitive for that
invariant because a 3xx response is returned to source code instead of following its Location.
The existing branch status classifier treats non-allowlisted 3xx statuses as
`CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_HTTP_STATUS_INVALID`.

## Correction

1. Change the database branch-lookup Request redirect policy from unsupported `error` to pinned
   workerd-supported `manual`.
2. Keep exact validated Neon `/sql` destination construction unchanged.
3. Keep the branch Request constructor inside the permanent
   `CLOUDFLARE_CF_D_NEON_BRANCH_REQUEST_INVALID` boundary.
4. Keep actual `fetch()` failure exclusively mapped to retryable
   `CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_FAILED`.
5. Preserve explicit response-status classification so every 3xx is rejected rather than
   followed.
6. Update executable regression evidence to require `request.redirect === "manual"`, add a 302
   branch response case, assert exactly one Neon branch fetch, and preserve provider-body
   non-propagation.
7. Add a static guard that the Worker egress source contains no `redirect: "error"` constructor
   mode.
8. Do not add a new retryable class and do not expose raw workerd exception text.

## Permanent learning

For provider-sensitive Worker egress, standards-facing Node tests are necessary but not always
sufficient evidence of the exact Cloudflare runtime contract. When behavior depends on a
runtime-specific Request option, review the exact workerd version resolved by the committed
lock and preserve a deterministic source regression for the chosen supported primitive.

Security intent must be expressed in the runtime-supported mechanism. Here, `manual` plus
explicit 3xx rejection is stronger evidence of "never follow provider redirects" than an option
that the pinned engine rejects before transport.

## Acceptance rule

This correction remains RED until the focused branch passes deterministic preflight, complete
diff review, DRAFT exact-head SUCCESS-only verification, unchanged READY fresh SUCCESS-only
verification, squash merge, exact-new-main Regression Shield/owning post-merge gates, and one
fresh exact-main Cloudflare Production Release. No rerun of the already failed
`34213455114` is acceptance evidence.
