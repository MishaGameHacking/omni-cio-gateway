# V10 Engineering Failure Learning Ledger — FL103

Date: 2026-09-08  
Scope: CF-D one-time production database bootstrap trusted failure classification  
Authority: Amendment 8 + Amendment 12 + Amendment 14 + Amendment 15 + `V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`

## Accepted precursor

PR #466 resolved the pinned workerd redirect-mode incompatibility and was squash-merged as
protected `main` `e340926521a79e4b7f7dee92883c4c2d340474f9`. The exact-new-main post-merge
batch completed all 11 current push workflows with terminal `success`, including both
Regression Shield jobs.

Automatic `V10 Cloudflare Production Release` run `34218802511`, job `102036801081`, then
passed the exact-main post-merge gate, Cloudflare provider and Workers Builds authority,
pinned delivery toolchain, Container-registry authority, exact-SHA staging Build,
single-active-version proof, pre-custody exact-SHA release proof, bootstrap-origin custody,
staging live `/api/v10/release` and `/healthz` acceptance, canonical domain configuration
validation, and production Worker-anchor reuse.

The previous `CLOUDFLARE_CF_D_NEON_BRANCH_REQUEST_INVALID` failure therefore no longer
reproduced. Production still had no accepted runtime database secret, so the required
one-time bootstrap path executed and stopped fail-closed at:

`Reuse production database secret or bootstrap it once`

with only:

`CLOUDFLARE_CF_D_DATABASE_BOOTSTRAP=STOPPED code=CLOUDFLARE_CF_D_STAGING_BOOTSTRAP_FAILED`

Production Build/promotion, Custom Domain mutation and live production acceptance were
skipped. Staging trigger quarantine and private-file/workspace cleanup succeeded.

Owning defect: #467.

## Root cause class

`CF_D_PRODUCTION_DATABASE_BOOTSTRAP_TRUSTED_FAILURE_CLASSIFICATION_COLLAPSE`

The one-time bootstrap chain already contained source-controlled semantic failure classes,
but two trusted boundaries discarded them before the release control plane could act on
them:

1. `apps/api/cf_d_database_bootstrap.py::_fetch_bootstrap_response()` converted every
   non-200 response from the trusted Worker/Neon Function path into the single
   `CLOUDFLARE_CF_D_NEON_BOOTSTRAP_REJECTED` class.
2. `scripts/bootstrap_v10_cloudflare_production_database_via_staging.py::_request_json()`
   converted every staging HTTP error, redirect and transport failure into the single
   `CLOUDFLARE_CF_D_STAGING_BOOTSTRAP_FAILED` class.

The second helper is also the GitHub OIDC token endpoint helper. Widening it globally to
parse arbitrary remote error bodies would mix unrelated trust domains and would be an
incorrect recovery.

The source-controlled Neon bootstrap Function already distinguishes bounded request/OIDC,
PostgreSQL-version, database-query/transaction, runtime-role and final runtime-probe
failure classes. The trusted Worker also has its own bounded egress rejection/unavailable
classes. The defect was semantic loss across trusted hops, not absence of classification at
the final provider function.

Because run `34218802511` normalized the downstream result before logging, it does not prove
which Function/Worker/runtime subtype failed. This entry deliberately does not relabel the
failure as OIDC, TLS, provider outage, SQL, role convergence or any other specific subtype
without evidence.

## Blast radius and adjacent review

Directly coupled surfaces reviewed:

- GitHub Actions OIDC token acquisition and its generic endpoint contract;
- runner -> exact staging `/api/internal/v10/cf-d/production-database-bootstrap` request;
- staging FastAPI exact-SHA/OIDC/provider-context/TLS guards;
- Container -> trusted Worker `outboundByHost` bridge;
- trusted Worker fixed same-branch/same-cell Function destination authority;
- source-controlled Neon Function response taxonomy;
- bounded response-body handling at Worker/Container/runner boundaries;
- production DSN validation, private-file ACL/mode hardening and cleanup;
- production Worker secret write only after a validated production DSN exists.

The correction does not change the existing fixed provider destination, TLS trust anchor,
OIDC audience/claims policy, PostgreSQL 18 requirement, least-privilege production role,
production-secret absence semantics or promotion ordering.

## Correction

The trusted failure boundary is now explicit and source-controlled end-to-end:

1. Add a single Python contract module containing the allowlisted source Function codes,
   their exact source HTTP statuses, the trusted Worker failure codes and the staging-route
   sanitized codes.
2. Require exact JSON error shapes. Worker errors are accepted only as exactly
   `{detail}`; Function errors are accepted only as exactly `{status: "BLOCKED", code}`.
   Extra fields, wrong status/code combinations, unknown codes, invalid UTF-8 or malformed
   JSON collapse to the generic fail-closed class.
3. Read provider error bodies through the existing 32 KiB bounded stream before
   classification. Oversized bodies remain
   `CLOUDFLARE_CF_D_NEON_BOOTSTRAP_RESPONSE_TOO_LARGE` and are never parsed.
4. Prefix accepted source Function failures with
   `CLOUDFLARE_CF_D_NEON_FUNCTION_` before crossing the staging API boundary. Raw Function
   bodies, URLs, identifiers, OIDC assertions and exception text are never reflected.
5. Add an endpoint-specific runner classifier for the staging bootstrap request only. It
   reads at most 8 KiB of an HTTP-error body and accepts only exact allowlisted staging
   `{detail}` codes with their expected staging status.
6. Keep the generic `_request_json()` helper unchanged for GitHub OIDC token acquisition
   and unrelated callers. Provider-like bodies received there remain generic
   `GITHUB_OIDC_TOKEN_REQUEST_FAILED`.
7. Classify redirects separately as
   `CLOUDFLARE_CF_D_STAGING_BOOTSTRAP_REDIRECT_REJECTED`; raw transport failures become
   `CLOUDFLARE_CF_D_STAGING_BOOTSTRAP_UNAVAILABLE`. Neither carries raw exception text.
8. Do not add automatic retry authority in this correction. Unknown/generic failures are
   explicitly non-retry-authoritative; a future retry policy would require a separate
   explicit transient allowlist and bounded attempt/time budget.
9. Extend `V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json` with the exact source Function
   and Worker safe-code sets, 8 KiB runner error-body ceiling, endpoint-specific classifier
   requirement, raw-error reflection prohibition and unknown-failure non-retry rule.

## Permanent regression guards

Deterministic tests require:

- the Python Function taxonomy to match the source-controlled Function error surface;
- source Function codes to retain their exact source HTTP-status contract;
- the machine release contract to match the executable allowlists with no duplicates;
- exact Worker/Function sanitized error shapes and status/code matching;
- unknown, malformed, invalid-UTF8 and status-mismatched bodies to collapse fail-closed;
- provider error-body streaming to remain bounded before classification;
- Function OIDC failures to cross the staging API only as prefixed sanitized codes;
- staging HTTP error bodies to remain bounded at 8 KiB;
- redirects and transport failures to remain separate sanitized runner classes;
- the generic GitHub OIDC request helper to remain unclassified by this endpoint-specific
  provider taxonomy.

## Why previous verification missed it

Earlier CF-D recovery work focused on reaching the trusted staging custody/egress path and
then on exact workerd runtime compatibility. Those regressions correctly proved destination
authority, exact SHA, redirect rejection, bounded branch proof and staging acceptance, but
they exercised successful Function responses or generic failure handling. They did not
require the first-production-bootstrap path to preserve the minimum safe semantic class
needed by the next control plane.

Sanitization that erases all semantics is safe for secrecy but insufficient when the next
trusted layer must distinguish a real permanent configuration/authentication defect from a
transport/readiness defect. The reusable rule is to preserve only a fixed source-controlled
classification required for the downstream authority decision, never arbitrary provider or
exception text.

## Acceptance rule

Source/tests alone do not resolve #467. The focused branch requires cheap preflight,
complete diff review, DRAFT exact-head SUCCESS-only verification, independent Files-changed
review with zero blocking threads, unchanged READY fresh SUCCESS-only verification, squash
merge, exact-new-main Regression Shield/owning post-merge success and a fresh exact-main
`V10 Cloudflare Production Release`.

That release must either complete the one-time production database bootstrap or expose a
different bounded source-controlled failure class that identifies the next real defect. Any
new downstream failure remains RED and must be corrected separately rather than hidden by
classification or blind rerun.
