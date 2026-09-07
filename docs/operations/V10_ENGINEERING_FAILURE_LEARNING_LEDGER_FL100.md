# V10 Engineering Failure Learning Ledger — FL100

Date: 2026-09-07  
Scope: CF-D Worker-to-control-plane Neon derivation failure classification and retry authority  
Authority: Amendment 8 + Amendment 12 + Amendment 14 + Amendment 15 + `V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`

## Observed failure

Accepted protected `main` `56c9c8d04c36af8a8569732219a32fd3810e5c31` completed
Regression Shield run `34105669575` successfully. Automatic `V10 Cloudflare Production
Release` run `34106645644` then exercised the version-bound staging custody correction from
PR #455.

Both the original release attempt and a fresh failed-job retry passed the exact-main
post-merge gate, Cloudflare Workers Builds authority, Container registry read authority,
pinned delivery toolchain, staging database-secret reuse, staging Worker-anchor reuse,
gated exact-SHA staging Build, single-active-version proof and exact-SHA pre-custody
`/api/v10/release` attestation.

Both attempts then stopped before any production mutation with:

`CLOUDFLARE_CF_C_CANDIDATE=STOPPED code=CLOUDFLARE_CF_D_ORIGIN_SYNC_DERIVATION_FAILED status=502`

Staging trigger quarantine and workspace cleanup succeeded. Production database/runtime
preparation, production promotion, Custom Domain changes and canonical live acceptance were
not attempted.

A read-only OWNER-authorized provider cross-check between the two attempts confirmed that
the canonical Neon project/default branch and the `cfdprodbootstrap` Function remained
present, the default branch was readable/ready, PostgreSQL was reachable through OWNER
provider authority, and the intended staging runtime role existed. No provider identifier,
credential, DSN or private payload is recorded in this ledger.

## Root cause

The Worker egress implementation already produced distinct internal fail-closed error codes
for several materially different states:

- invalid or stale runtime database binding shape;
- rejected egress destination;
- Neon branch SQL-over-HTTP transport failure;
- Neon branch response failure or malformed proof;
- trusted bootstrap Function-origin validation/mismatch.

However, `cloudflare/src/cf-d-bootstrap-origin-custody.js` caught every exception from the
derivation path and replaced it with the single HTTP 502 detail
`CLOUDFLARE_CF_D_ORIGIN_SYNC_DERIVATION_FAILED`.

The Python release control plane then mapped every custody HTTP 502 to that same generic
code and treated the generic class as retryable. This caused two coupled failures:

1. **diagnostic authority loss** — a permanent runtime binding/auth/config/proof failure and
a transient provider/readiness failure became indistinguishable after crossing the trusted
Worker boundary;
2. **retry authority widening** — permanent failure classes inherited the same retry policy
as transient network/readiness classes, delaying fail-closed termination without improving
evidence.

The issue was not that the Worker returned too much detail. The issue was that it returned
too little trusted, bounded detail after the internal implementation had already classified
the failure safely.

## Blast radius

The defect class applies to every sanitized failure occurring while deriving the trusted
same-branch/same-cell Neon Function origin from the staging runtime database binding.
Directly coupled cases include:

- malformed/non-staging/non-Frankfurt runtime DSN;
- rejected internal Neon SQL-over-HTTP destination;
- branch SQL-over-HTTP authorization failure;
- missing branch/database HTTP endpoint;
- transient branch SQL-over-HTTP readiness/transport failure;
- unexpected branch HTTP status;
- oversized or malformed branch proof;
- bootstrap Function-origin validation or branch/cell mismatch.

The defect does not authorize exposing a provider response body, database hostname, branch
identifier, DSN, password, API token or Function URL in GitHub Actions diagnostics.

## Corrective change

The failure boundary is made both informative and fail-closed:

1. Classify Neon branch SQL-over-HTTP non-success status into a fixed source-controlled
   taxonomy: unauthorized, not found, transient/not ready or unexpected status.
2. Preserve only a fixed allowlist of sanitized source-controlled derivation codes across
   the Worker custody endpoint. Unknown exceptions remain the generic derivation-failed
   code.
3. Keep the custody response HTTP status bounded at 502 for derivation failures; no raw
   provider body, provider identifier or target URL is reflected.
4. Allow the Python control plane to read the bounded JSON `detail` only for the trusted
   custody endpoint and only when HTTP status is 502.
5. Accept only the same source-controlled allowlist in Python. Unknown or non-JSON 502
   responses collapse to the generic permanent class; malformed JSON fails closed as an
   invalid custody response. None of these unknown-response classes is retry-authoritative.
6. Retry only explicit transient classes: branch transport failure, branch not-ready,
   staging not-ready and control-plane transport unavailable.
7. Fail permanent auth/config/proof/status/body/origin classes immediately without retry.

## Permanent regression guards

Deterministic JS/Python tests and the release-acceptance contract require:

- explicit branch HTTP-status classification without propagating provider response bodies;
- a strict Worker-side safe-code allowlist with unknown-error collapse;
- preserved sanitized custody detail for known branch failures;
- strict Python-side safe-code allowlist for HTTP 502 custody errors;
- malformed JSON 502 responses to fail closed and non-JSON 502 responses to stay generic;
- exact transient-only retry membership;
- permanent authorization/configuration/proof failures to execute once and stop;
- unknown derivation failures never to become accepted or retry-authoritative by default.

## Why earlier verification missed it

FL099 corrected a real Cloudflare Worker version/deployment race and added distinct HTTP
status preservation at the outer custody boundary. That correction successfully moved the
release forward: the exact Worker version and exact SHA were proven live before custody in
run `34106645644`.

The next failure exposed a deeper nested boundary. The previous tests verified that Worker
internal derivation errors were deliberately sanitized to one generic 502, but did not model
the operational need to distinguish permanent versus transient sanitized classes for retry
authority. A generic message is safe for secrecy, but it is not sufficient when the next
control plane makes materially different decisions from the classification.

Future failure sanitization must preserve the minimum source-controlled semantic class
required by the downstream authority decision while continuing to reject arbitrary provider
or exception text.

## First-party provider references

- Neon serverless driver — HTTP/WebSocket transport and one-shot SQL over HTTPS:
  `https://neon.com/docs/serverless/serverless-driver`
- Neon serverless driver reference — default HTTPS SQL endpoint derives from the database
  host as `https://host/sql`:
  `https://neon.com/docs/serverless/serverless-driver-reference`
- Neon archive storage — archived branches automatically reactivate on first access and can
  incur readiness latency:
  `https://neon.com/docs/introduction/archive-storage`

## Acceptance rule

Source/tests alone do not make this defect accepted. Issue #456 and its focused branch
require normal exact-head SUCCESS-only verification, independent review disposition, zero
blocking review threads, squash merge, exact-new-main Regression Shield success and a fresh
exact-main Cloudflare production release.

That fresh release must either pass the formerly generic custody boundary or produce one of
the newly preserved sanitized failure classes. Any newly exposed permanent provider/runtime
binding defect remains RED and must be corrected separately; classification itself is not a
bypass and is not release acceptance.
