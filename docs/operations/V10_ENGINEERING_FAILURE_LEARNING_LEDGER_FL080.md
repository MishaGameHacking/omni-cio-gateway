# V10 Engineering Failure Learning Ledger — FL080

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-D exact-main production release authority for the protected Neon PostgreSQL runtime.

This entry records the provider-scope defect exposed after the OWNER corrected the protected `NEON_PROJECT_ID` binding and a fresh exact-main production release still stopped before mutation.

> Follow-up evidence: the initial correction recorded here still depended on account-/organization-level identity probes. Exact-main release `33659353292` later proved that a least-privilege project-scoped Neon key can reject those endpoints. FL081 supersedes that part of the corrective model and requires the project-scoped fallback to use project-level exact-resource reads only.

## Failure observed

Fresh CF-D release evidence on accepted main `d349ee4026a21aa733b171f843a180bd830990a6` showed:

- exact-main post-merge gate READY;
- Cloudflare Workers Builds authority READY;
- Neon exact project metadata read returned HTTP `403`;
- every staging, database-mutation, production Worker, Custom Domain, and live-acceptance step remained skipped;
- cleanup/quarantine completed successfully.

The existing diagnostic then attempted provider-wide project discovery after the exact-project failure. That assumption is incompatible with a least-privilege Neon project-scoped organization API key, whose authority is intentionally bounded to one project and must not depend on account-wide project enumeration.

## Root cause class

`PROVIDER_SCOPE_PROBE_CONTRACT_DRIFT`

The control plane conflated three different questions:

1. whether the credential is valid for the intended provider surface;
2. whether the configured organization metadata is compatible with the normal organization-scoped path;
3. whether the credential can operate on the exact configured project.

A provider-wide project search was used as diagnostic evidence for question 3. For project-scoped credentials, that search is not a valid authority probe and can hide the real distinction between an endpoint-specific metadata restriction and an actual key/project binding mismatch.

## Corrective invariant

The durable invariant, refined by later FL081 evidence, is that CF-D must remain fail-closed and prove project-scoped authority only with scope-compatible, read-only evidence before mutation:

- never use provider-wide project enumeration to diagnose a project-scoped key;
- after exact project metadata is unavailable, anchor authority to the protected exact `NEON_PROJECT_ID` and prove access through exact project subresource reads;
- do not require account-/organization-level identity endpoints in the project-scoped fallback; FL081 records the live evidence for this refinement;
- when project metadata itself is unavailable but exact project subresources are readable, resolve the target only from exact project subresources;
- validate the Frankfurt connection hostname and PostgreSQL major version `18` before migrations, role convergence, grants, or any other database mutation;
- keep provider identifiers, API keys, connection strings, and account identity payloads out of logs and exceptions.

## Permanent learning

- Credential presence is not credential authority.
- Credential authority is endpoint- and scope-specific; a valid least-privilege credential can legitimately reject account-wide discovery and identity surfaces.
- Exact resource authority must be proven with an operation that the credential class is expected to perform in production.
- Diagnostic fallbacks must not widen the discovery surface beyond the credential's intended scope.
- When metadata endpoints and operational subresource endpoints differ in scope behavior, runtime identity must remain anchored to protected exact identifiers and independently verified live properties before mutation.
- A fail-closed preflight is successful only when it distinguishes provider-scope incompatibility from true binding drift without fabricating provider state.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- No real credential, token, password, account identifier, database secret, connection URI, or provider-private payload is recorded in this ledger.
- No Cloudflare production mutation is authorized by this correction alone; CF-D still requires its exact-main provider, staging, production, domain, and live acceptance gates to succeed.
