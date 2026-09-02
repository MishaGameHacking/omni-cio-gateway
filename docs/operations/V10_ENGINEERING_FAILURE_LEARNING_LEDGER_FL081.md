# V10 Engineering Failure Learning Ledger — FL081

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-D exact-main production release authority for the protected Neon PostgreSQL runtime.

This entry records the follow-up provider-scope defect exposed by production release run `33659353292` after PR #432 had already removed provider-wide project enumeration from the scoped fallback.

## Failure observed

Fresh CF-D release evidence on exact accepted main `0e8b752e662824cd1ee5d1ff23cbaa9cc183a019` showed:

- exact-main post-merge gate READY;
- Cloudflare Workers Builds authority READY;
- protected Neon credentials/configuration were present;
- the exact project metadata path returned HTTP `403` and entered the project-scoped fallback;
- the fallback then called provider account-level `/auth`, which also returned HTTP `403` for the least-privilege project-scoped credential;
- every staging, database-mutation, production Worker, Custom Domain, and live-acceptance step remained skipped;
- cleanup/quarantine completed successfully.

Neon's current authentication contract defines a project-scoped organization API key as member-level authority to one organization-owned project only. Current Neon release notes also document that project-scoped keys can fail on account-level endpoints because they are restricted to project-level operations.

## Root cause class

`PROJECT_SCOPED_CREDENTIAL_ACCOUNT_ENDPOINT_DEPENDENCY`

The fallback correctly stopped using broad project enumeration, but still attempted to prove credential class and organization binding through account-/organization-level endpoints before proving the exact project subresource. That is an authority inversion: a least-privilege key was required to succeed on surfaces outside the permissions it is intentionally designed to have.

## Corrective invariant

For the project-scoped fallback:

- the protected `NEON_PROJECT_ID` remains the exact authority anchor;
- after exact project metadata returns `403`/`404`, use only read-only subresources under `/projects/{NEON_PROJECT_ID}/...` to prove access;
- do not require `/auth`, `/users/me/...`, `/organizations/...`, or provider-wide `/projects?...` discovery in that fallback;
- treat exact branch-read `403`/`404` as a fail-closed key/project binding mismatch;
- preserve non-binding provider failures without reclassification;
- continue resolving branch/database/connection URI only under the protected exact project;
- verify Frankfurt from the returned Neon connection hostname and PostgreSQL major version `18` before migrations, runtime-role convergence, grants, or any database mutation;
- never log API keys, provider identity payloads, project/account identifiers, connection URIs, or database secrets.

## Permanent learning

- Least privilege must be tested with operations that belong to the credential's intended permission boundary.
- A diagnostic endpoint is not automatically safe evidence merely because it is read-only; scope compatibility matters as much as mutability.
- Account identity, organization metadata, and exact project authority are separate provider surfaces and must not be conflated.
- When a provider intentionally restricts project-scoped credentials from account-level endpoints, the control plane must remain capability-based and exact-resource-bound rather than attempting to infer broader credential identity.
- Real release evidence overrides assumptions from earlier tests; a deterministic regression must encode the newly observed provider boundary before rerunning production.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- No real credential, token, password, full account identifier, database secret, connection URI, or provider-private payload is recorded in this ledger.
- No Cloudflare production mutation is authorized by this correction alone; CF-D still requires exact-head review/CI, squash merge, exact-new-main post-merge acceptance, staging rehearsal, production deployment, Custom Domain attachment, and live release acceptance.
