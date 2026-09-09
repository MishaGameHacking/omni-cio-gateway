# V10 Engineering Failure Learning Ledger — FL108

Date: 2026-09-09  
Scope: CF-D production database bootstrap boundary diagnostics  
Authority: Amendment 8 + Amendment 12 + Amendment 14 + Amendment 15 + Amendment 16 + `V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`

## Accepted precursor and fresh MAIN_RED_STOP evidence

PR #475 was squash-merged as protected `main`
`c24ccd0624a6f4445f822c3f2ebcbadeb70a3530`. Its exact-main staging rehearsal proved all of
these before production database bootstrap:

- active staging Worker source SHA exactly matched accepted `main`;
- serving staging Container image source SHA exactly matched accepted `main`;
- staging database health was `READY`;
- canonical domain configuration and production Worker anchor validation passed.

Fresh exact-main `V10 Cloudflare Production Release` run `34385820740`, job
`102581684031`, nevertheless stopped fail-closed at the one-time production database bootstrap
with:

`CLOUDFLARE_CF_D_STAGING_BOOTSTRAP_FAILED`

Production deployment, production Custom Domain mutation and live production acceptance did
not run. Cleanup/quarantine completed successfully.

This evidence disproves the earlier hypothesis that a stale serving Container image alone was
the active cause of the repeated generic bootstrap failure. FL107 remains historical learning
about asynchronous Container rollouts and the exact-image provenance guard remains mandatory,
but it is not the current root-cause explanation.

## Current defect class

`CF_D_STAGING_BOOTSTRAP_BOUNDARY_FAILURE_NORMALIZATION_TOO_OPAQUE`

The source-controlled CF-D route, Worker egress proxy and Neon bootstrap Function already have
bounded allowlisted failure taxonomies. The external GitHub runner deliberately converts any
unrecognized staging HTTP response into one generic code. That was safe for secret hygiene,
but after exact Worker + exact Container provenance is proven it prevents systemic repair of a
repeated route-external/platform failure: HTTP status and source-controlled outer application
failure class are discarded together with the untrusted body.

Repeated identical generic RED is not eligible for blind same-SHA retry under Amendment 16.
The diagnostic boundary itself must preserve enough non-secret evidence to identify the next
repair surface while continuing to fail closed.

## Blast radius and coupled surfaces

The defect affects the external production-bootstrap authority chain only:

- GitHub Actions runner -> staging Cloudflare Worker;
- Worker -> exact serving Container;
- hosted security/route restoration -> exact CF-D route;
- Container outbound virtual host -> Worker egress handler -> Neon Function.

The correction does not change any success response, OIDC claim validation, database
credential value, provider destination, request body, retry policy, product session, tenant
scope, broker credential or public-user capability.

## Corrective change

The failure contract now distinguishes three safe layers:

1. exact source-controlled CF-D route/Worker/Neon failure codes remain preserved exactly as
   before;
2. a small allowlist of source-controlled outer application/edge `detail` values is preserved
   only when its HTTP status matches the expected source contract, with a dedicated
   `CLOUDFLARE_CF_D_STAGING_OUTER_` prefix;
3. when a bounded response remains unrecognized, the real request boundary retains only a
   finite allowlisted HTTP status as
   `CLOUDFLARE_CF_D_STAGING_HTTP_<status>_UNCLASSIFIED`.

Raw response bodies, response headers, request IDs, provider identifiers, URLs, secrets,
account IDs and private payloads are never reflected into the failure code or log. Unsupported
statuses remain the existing generic failure. Redirects and transport failures keep their
existing dedicated classes. No unknown failure becomes retryable.

## Permanent regression guard

Deterministic tests require:

- every allowlisted outer detail to match an exact expected HTTP status;
- wrong-status outer details to remain untrusted;
- every finite status-only code to be source controlled;
- real runner requests to preserve a known outer detail;
- opaque/plain/provider-specific bodies to yield only a status-only code and never raw text;
- unsupported unknown statuses to remain generic;
- existing route/Function/redirect/transport classifications to remain unchanged.

## Why prior preflight missed it

Earlier failure-classification work optimized for non-reflection and exact allowlists, which
was correct for known source-controlled failures. It did not distinguish “do not trust the
body” from “discard the HTTP status too”. Once exact Worker and Container provenance removed
the stale-image ambiguity, the lost status became material diagnostic evidence needed to
locate the remaining outer boundary defect.

## Future prevention rule

At a security boundary, sanitize untrusted failure content without destroying safe transport
metadata that is necessary for deterministic incident localization. Preserve only finite,
source-controlled classes and status codes; never reflect provider bodies or identifiers.

A repeated unknown production failure is a defect to classify and repair, not a transient to
rerun until GREEN.

## Acceptance rule

This correction is a focused `MAIN_RED_STOP` repair. It requires exact-head preflight/CI,
Sonar and independent review, zero blocking findings, squash merge, exact-new-main Regression
Shield and owning post-merge production-release evidence.

A fresh exact-main production release must either complete CF-D or expose a new bounded
source-controlled failure class. Any newly exposed source/config defect remains `MAIN_RED_STOP`
and is repaired in a separate focused branch before unrelated functional work resumes.
