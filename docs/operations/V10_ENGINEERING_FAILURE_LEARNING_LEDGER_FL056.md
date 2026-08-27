# FL-056 — Organization-scoped provider credentials must not depend on user-discovery endpoints

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR FOCUSED DEFECT #396; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-28**  
WP / PR / reference: **post-#399 hosted-preview Neon recovery / issue #396**

## Symptom / failing gate

After PR #399 landed on protected `main` `58db4d8aae6af94ec29a63fe7f30cf125bf7d7bf`, the OWNER replaced the repository Neon credential with a newly created organization-wide API key and started a fresh Phase-4 `workflow_dispatch` run.

Fresh run #27 still stopped before provider mutation at `Enforce zero-charge provider boundary` with the sanitized diagnostic:

`NEON_API_KEY_INSUFFICIENT status=403`

The exact-main Regression Shield and Phase-4 source tests passed. The Render/Neon provider mutation step was skipped. Hosted release alignment therefore remained correctly RED because the public preview still served an older release SHA.

## Root-cause analysis

The credential itself was no longer the only plausible cause. The accepted Phase-4 preflight and provisioner both assumed an API key could discover its organization through:

`GET /users/me/organizations`

Current Neon CLI implementation guidance explicitly states that organization-scoped API keys cannot list user organizations. It also states that organization-scoped API keys cannot call the regions endpoint. The accepted provisioner contained both assumptions: user-organization discovery on every run and a regions discovery call on the clean-room project-create path.

Neon provides an organization-scoped API endpoint instead:

`GET /organizations/{org_id}`

and its own CI/e2e guidance uses a non-secret `NEON_ORG_ID` alongside an organization-scoped `NEON_API_KEY`.

The defect was therefore an authority-model mismatch between our CI credential type and the discovery endpoints selected by the code, not a reason to weaken authentication or accept HTTP 403.

## Blast radius searched

Directly coupled surfaces inspected:

- `scripts/check_v10_zero_cost_provider_boundary.py`;
- `scripts/provision_v10_render_neon_preview.py`;
- `.github/workflows/v10-phase4-free-preview-deploy.yml`;
- Phase-4 zero-cost/provider tests and authorization contract;
- existing preview-project reuse and clean-room project-create path;
- hosted release alignment as the downstream consumer of deployment success/failure.

Analogous provider-discovery assumptions were searched. The material Neon user-centric calls in the accepted Phase-4 deployment path were `/users/me/organizations` and `/regions`; both must be removed from the organization-scoped credential path.

## Why prior preflight missed it

Deterministic tests mocked the documented `/users/me/organizations` response and therefore proved our implementation against the assumed contract, not against the actual organization-scoped credential behavior exercised by Neon.

The Neon API reference currently describes `/users/me/organizations` as supporting organization-scoped keys, while Neon CLI implementation guidance documents the opposite operational limitation. The provider contradiction was only exposed by a real fresh organization-scoped key after #399 made 401/403 classification precise.

## Corrective change

The Phase-4 deployment path is changed to:

1. require a non-secret `NEON_ORG_ID` GitHub Actions variable;
2. validate that identifier before any network request;
3. validate organization identity and Free plan through `GET /organizations/{org_id}`;
4. require the returned organization identity to match the configured ID exactly;
5. retain 401/403 fail-closed handling, redirect rejection, bounded response size and bounded read-only retries;
6. treat Neon `423 Locked` as retryable only for idempotent GET checks;
7. remove the organization-scoped dependency on `/regions` from the project-create path and use the source-controlled accepted Frankfurt region directly;
8. retain exact-main, zero-charge, no-paid-fallback, V9, tenant, broker-write and Real-money boundaries.

No provider credential value or private provider payload is stored in source, GitHub comments, logs or artifacts.

## Permanent regression / guard

Phase-4 tests must fail if the canonical deployment source reintroduces `/users/me/organizations` or `/regions` into the organization-scoped Neon path.

Tests must also prove:

- missing/malformed `NEON_ORG_ID` stops before network access;
- organization ID mismatch stops fail-closed;
- a non-Free organization stops fail-closed;
- 401 and 403 stay distinct and sanitized;
- 423/503 GET failures use bounded retry;
- project creation uses the fixed accepted region without a forbidden regions-discovery call.

## Future prevention rule

When a provider supports multiple credential scopes, integration tests must model the actual scope selected for CI/runtime rather than only the broadest user credential. Provider discovery endpoints are authority-sensitive API surfaces and must be reviewed together with the credential type.

If first-party reference prose and first-party implementation guidance conflict, do not weaken security to make either side pass. Prefer the narrower credential scope, explicit non-secret resource identity and direct resource endpoint, then prove behavior through a fresh provider run.

## Dependency/tooling knowledge change

No dependency upgrade is required. This correction updates provider API routing/configuration only and preserves the accepted toolchain and lock files.
