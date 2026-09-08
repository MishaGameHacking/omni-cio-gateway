# V10 Engineering Failure Learning Ledger — FL101

Date: 2026-09-08  
Scope: CF-D Worker Neon branch-request construction classification before transport  
Authority: Amendment 8 + Amendment 12 + Amendment 14 + Amendment 15 + `V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`

## Accepted precursor

Focused PR #462 was accepted into protected `main` as
`0cd1bf27fdc4e66354b87fa60b709c1abd15e604` after unchanged-head READY verification.
Post-merge Regression Shield run `34206083001` completed protected quality/coverage and
security jobs successfully, and the downstream release gate proved all 11 current exact-main
push workflows successful.

Automatic `V10 Cloudflare Production Release` run `34206677174`, job `101997668735`, then
passed provider authority, Workers Builds authority, the pinned delivery toolchain,
Container registry read authority, exact-main staging Build, single-active-version proof and
pre-custody exact-SHA `/api/v10/release` attestation.

The release stopped before production mutation with:

`CLOUDFLARE_CF_D_ORIGIN_SYNC_DERIVATION_FAILED status=502`

Staging trigger quarantine and cleanup succeeded. Production database/runtime preparation,
production Worker promotion, Custom Domain mutation and live acceptance were skipped.

## Provider cross-check

Read-only provider evidence after the failure confirmed that the canonical Frankfurt Neon
project/default branch remained healthy on PostgreSQL 18, the intended staging runtime role
remained present without superuser/createdb/createrole/replication/bypass-RLS authority, and
the required bootstrap Function remained present.

No provider identifier, DSN, credential, hostname or private payload is recorded here.

## Root cause

PR #462 correctly preserves known source-controlled derivation classes across the Worker
custody boundary. A generic derivation failure after that correction therefore proves that an
exception escaped the known taxonomy.

Direct call-chain review found the concrete phase gap in
`cloudflare/src/cf-d-neon-bootstrap-egress.js`:

```text
runtimeBranchId()
  -> databaseSqlUrl()
  -> branchLookupRequest()
  -> classification try around fetchRuntimeBranchLookup()
```

`branchLookupRequest()` constructed the outbound `Request`, request headers and timeout
signal before the classification `try` began. A synchronous runtime exception during that
construction could therefore never become `CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_FAILED` or
another source-controlled class. It propagated to the outer custody sanitizer, which
correctly refused to expose arbitrary exception text and reduced it to the generic 502.

The existing transport regression injected an exception from `fetch()`. It therefore tested
the network phase but could not exercise the earlier request-construction phase.

The exact internal runtime exception text is intentionally unavailable by design and is not
required to correct the classification boundary. The security invariant is to preserve only
the minimum source-controlled phase classification, never raw runtime/provider detail.

## Blast radius

The defect class is the distinction between deterministic outbound-request construction and
actual network transport in the CF-D Worker egress path.

The review covered the directly coupled branch SQL-over-HTTP request, its exact Neon target,
header allowlist, bounded request body, timeout signal, retry policy, Python custody consumer
and machine-readable release contract. Existing same-branch/same-cell Function-origin,
response-body and provider-body no-leak protections remain unchanged.

Current Cloudflare Workers Request documentation defines `new Request(input, options)` and
supports POST, headers, body, `redirect` and `signal`; the correction uses the canonical URL
string at that boundary and does not depend on a new runtime API or dependency.

## Correction

1. Build the Neon branch request inside an explicit fail-closed construction boundary.
2. Use the canonical validated URL string (`href`) at the Worker `Request` constructor.
3. Map any synchronous construction/runtime failure to the new sanitized permanent class
   `CLOUDFLARE_CF_D_NEON_BRANCH_REQUEST_INVALID`.
4. Start the actual network phase only after construction succeeds.
5. Preserve `CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_FAILED` exclusively for `fetch()` transport
   failure; it remains retryable.
6. Remove the unnecessary branch-lookup double-Request reconstruction. The outbound request
   is generated once from the already validated runtime binding and fixed SQL operation.
7. Add the construction class to the Worker/Python/release-contract allowlist but not to the
   retry set.
8. Add an executable Node regression that forces `Request` construction to throw before
   `fetch()` and proves zero network calls plus bounded sanitized 502 detail.
9. Keep unknown exception text behind the generic fallback.

## Permanent learning

A sanitizer is only useful when every phase that can influence downstream retry/authority
starts inside a classification boundary. Tests must distinguish request preparation from
network transport; injecting only `fetch()` failures is insufficient when constructors,
headers, body encoders or timeout primitives can fail earlier.

Do not classify deterministic construction/configuration failures as transient merely to
obtain retries. Do not expose raw exception text to make diagnosis easier.

## Acceptance rule

This correction remains RED until the focused branch passes normal exact-head DRAFT and
unchanged READY SUCCESS-only verification, is squash-merged, the exact-new-main Regression
Shield/owning post-merge gates succeed, and a fresh exact-main Cloudflare Production Release
passes this boundary or produces a different bounded source-controlled failure class.
