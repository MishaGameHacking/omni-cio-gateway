# V10 Engineering Failure Learning Ledger — FL082

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-D exact-main
production release authority for the protected Neon PostgreSQL runtime.

This entry records the observability defect exposed after PR #433 had already removed
account-/organization-level dependencies from the least-privilege project-scoped
authority fallback.

## Failure observed

Fresh production release run `33673595329` on exact accepted main
`4064c2d2776ee6be869579e001b6d005a9b25e0b` showed:

- the exact-main post-merge gate was READY;
- all protected Cloudflare/Neon secret bindings were present without their values being
  logged;
- Cloudflare Workers Builds authority was READY;
- the Neon exact-project probe still failed closed as
  `NEON_PROJECT_KEY_BINDING_MISMATCH status=403`;
- staging, database mutation, production deployment, Custom Domain attachment and live
  acceptance remained skipped;
- cleanup/quarantine completed successfully.

The same external symptom can represent materially different causes: an invalid or
wrong-scope credential, configured organization drift, configured project drift, a
canonical project that is absent from the configured organization, or provider-side
exact-project authorization drift. The existing failure marker intentionally hid
provider identifiers, but it also collapsed those distinct cases into one status.
Repeated credential/identifier rotation therefore could not establish root cause.

Current Neon documentation states that organization API keys can access projects within
their organization and that project-scoped keys have Editor access to one specified
project. The documented project branch-list surface is an ordinary project operation.
The release must therefore distinguish configuration/binding evidence without weakening
the exact-project authority gate.

## Root cause class

`NEON_AUTHORITY_FAILURE_OBSERVABILITY_GAP`

The authority check itself remained fail-closed. The defect was that its failure path
provided too little privacy-safe evidence to distinguish adjacent provider/configuration
failure modes after a real 403.

## Corrective invariant

When the existing Neon exact-project preflight fails:

- preserve the original preflight outcome as failure; diagnostics never convert RED to
  GREEN;
- run only read-only diagnostic calls;
- record HTTP status for the configured organization, exact configured project and
  exact configured project branch list;
- only when the configured organization is itself readable, perform a bounded
  organization-scoped exact-name search for the canonical project;
- compare the configured project ID to the exact canonical-name match in memory and emit
  only boolean/count/classification evidence;
- never emit API keys, provider IDs, request URLs containing IDs, provider payloads,
  connection URIs, database credentials or private tenant data;
- never perform provider mutation from the diagnostic path;
- never make the organization lookup or canonical-name lookup part of the
  project-scoped authority proof accepted by FL081/PR #433;
- project-scoped fallback authority remains based only on exact
  `/projects/{NEON_PROJECT_ID}/...` resources.

## Directly coupled consumers

The same exact-project preflight is used by:

- `V10 Cloudflare Provider Readiness`;
- `V10 Cloudflare Candidate Deployment`;
- `V10 Cloudflare Production Release`.

All three receive the same failure-only diagnostic step so analogous failures do not
regress to blind credential rotation.

## Permanent learning

- Least-privilege proof and failure diagnostics are different authority surfaces and
  must remain explicitly separated.
- Privacy-safe diagnostics should reduce ambiguity before asking the OWNER to rotate a
  credential or identifier again.
- A provider dashboard `last used` field is not accepted as proof that a rejected API
  request did or did not use a credential unless the provider contract explicitly
  guarantees that behavior.
- Repeated real-provider 403 evidence must produce a reusable deterministic diagnostic,
  not another speculative secret change.
- Diagnostic failure must never bypass, soften or reorder provider mutation gates.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- No real credential, token, password, full provider identifier, database secret,
  connection URI or provider-private payload is recorded in this ledger.
- No Cloudflare or Neon mutation is authorized by this diagnostic correction alone;
  CF-D still requires exact-head review/CI, squash merge, exact-new-main post-merge
  acceptance, staging rehearsal, production deployment, Custom Domain attachment and
  live release acceptance.
