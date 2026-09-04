# V10 Engineering Failure Learning Ledger — FL089

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, focused CF-D defect #446 on exact accepted main `4bab04398d228c1ae7aa17cbee1cffca1b7940f1`.

This entry records the custody/provider-scope regression exposed after PR #441 aligned the Neon GitHub integration project selector to a repository variable and PR #443 then removed that variable from active workflow environments to stop raw provider-identifier rendering in GitHub Actions logs.

## Failure observed

The accepted sequence established two individually valid requirements that were combined incorrectly:

- PR #441 / FL086 matched the official Neon GitHub integration custody shape: `NEON_API_KEY` is a repository secret and `NEON_PROJECT_ID` is a repository variable.
- Fresh exact-main provider evidence then showed that direct `${{ vars.NEON_PROJECT_ID }}` expansion into a step environment renders the raw project identifier in GitHub Actions logs before in-process masking can execute. PR #443 / FL087 correctly removed that direct variable expansion.

PR #443 replaced the exact protected project selector with canonical-name discovery through `GET /projects`. It first attempts an organization-filtered list and, after HTTP `403`, retries the project list without `org_id` as a presumed project-scoped-key fallback.

Fresh production release run `33884821699` on exact main `4bab04398d228c1ae7aa17cbee1cffca1b7940f1` completed the exact-main post-merge and Cloudflare Workers Builds authority gates, then stopped before any provider mutation with privacy-safe Neon evidence including `canonical_query_status=403` and `classification=UNRESOLVED`. Every staging/database/production/Custom Domain/live-acceptance mutation remained skipped and cleanup succeeded.

Current Neon documentation states that project-scoped API keys are restricted to project-level operations and can be rejected on account-level surfaces. The project list is therefore not a valid capability proof for a least-privilege one-project credential merely because the request is read-only.

This also conflicts with already-accepted FL081 and FL082, which require the project-scoped authority fallback to remain anchored to the exact project identifier and exact `/projects/{NEON_PROJECT_ID}/...` resources, while keeping account/organization/project-list calls outside that authority proof.

Historical exact-project and exact-branch `403` evidence tracked in #430 remains separate evidence. Correcting this source contract does not claim that the currently protected key/project pair is already authorized.

## Root cause class

`NEON_PROJECT_SELECTOR_CUSTODY_SCOPE_REGRESSION`

The source conflated two distinct concerns:

1. **privacy custody** — a provider identifier must not be rendered into engineering logs even when the provider itself labels the value non-secret;
2. **provider authority** — a project-scoped credential must be tested only through operations inside that exact project's permission boundary.

Removing the project selector from the runner solved the first concern but forced account-level project enumeration to recover it, regressing the second concern.

## Corrective invariant

For active CF-C/CF-D workflows:

- `NEON_API_KEY` remains a GitHub Actions secret;
- the exact Neon project selector is supplied through protected GitHub Actions secret custody as `NEON_PROJECT_ID`, so GitHub masks the value before any step process runs;
- the provider-managed repository variable may continue to exist as upstream Neon integration metadata, but active Omni-CIO release workflows must not expand `${{ vars.NEON_PROJECT_ID }}` into runner-visible workflow state while GitHub renders that value unmasked;
- the protected project-ID secret is a privacy custody mirror and exact selector, not broader Neon credential authority;
- every use of the selector remains fail-closed against the existing exact project ID/name/organization/Frankfurt/PostgreSQL 18 contract before mutation;
- a project-scoped fallback uses only exact project-level subresources under `/projects/{NEON_PROJECT_ID}/...` and never depends on provider-wide `GET /projects` enumeration;
- an exact project/branch read `403` or `404` remains a real fail-closed binding/authority failure and is never converted to success by diagnostics;
- failure-only diagnostics remain read-only and may not convert RED to GREEN;
- organization-wide or admin Neon authority must not be introduced merely to make project enumeration succeed;
- if the protected project-ID secret is absent or stale, the release stops before mutation and requires an OWNER custody correction outside source control;
- no API key, provider identifier value, request URL containing a provider identifier, database DSN, or tenant-private payload is written to source, issue/PR discussion, CI summaries, logs, screenshots, or artifacts.

## Directly coupled consumers

The correction applies consistently to:

- `V10 Cloudflare Provider Readiness`;
- `V10 Cloudflare Candidate Deployment`;
- `V10 Cloudflare Production Release`;
- `scripts/check_v10_cloudflare_provider_readiness.py`;
- `scripts/check_v10_cloudflare_candidate_delivery.py`;
- `scripts/provision_v10_cloudflare_neon_runtime.py` and its exact-project authority path;
- failure-only Neon authority diagnostics and deterministic regression tests.

The invalid canonical-name resolver introduced by PR #443 is removed from the active release path rather than retained as a second competing project-selection authority.

## Permanent learning

- Provider-defined “non-secret” metadata can still be confidential under a stricter project security policy; workflow expression rendering must be reviewed independently from provider classification.
- Secret custody can be appropriate for masking a non-credential identifier when the operational policy forbids that identifier from logs.
- Least-privilege credentials must be tested with capabilities they are actually intended to possess; read-only account enumeration is not a substitute for exact-resource authority.
- A source correction that fixes a privacy leak must not silently invalidate an earlier accepted least-privilege authority invariant.
- Historical provider failures remain evidence after a source correction; do not reinterpret old RED as GREEN.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- no transfer/withdrawal/margin/leverage/uncovered-short authority is introduced.
- no Cloudflare or Neon mutation is authorized by this source correction alone; CF-D still requires exact-head review/CI, squash merge, exact-new-main post-merge acceptance, exact Neon authority, staging rehearsal, production deployment, Custom Domain attachment, and canonical live release acceptance.
