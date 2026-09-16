# V10 Engineering Failure Learning Ledger — FL147

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_ASSOCIATED_PR_PROJECTION_PROVENANCE_MISMATCH`
- Scope: exact-main Sonar fallback after PR #517

## Observed failure

PR #517 landed as protected `main` SHA `d202ee7d579a1330affafbf2855915230be5824f`. Exact-new-main Regression Shield and repository-owned post-merge checks completed successfully. The external `SonarCloud Code Analysis` check again completed `cancelled` with zero annotations, which is the narrowly eligible case for the fail-closed equivalent-tree provenance fallback accepted in #517.

The subsequent `V10 Cloudflare Production Release` stopped twice, including one same-SHA retry, before any provider mutation. Both attempts failed inside the post-merge release gate with:

`CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_SHA_MISMATCH`

Provider mutation, production promotion and public-route steps were skipped. Cleanup/quarantine completed successfully.

## Root cause

The #517 verifier correctly required exactly one pull request associated with the exact main commit, but it then treated the pull-request object embedded in `GET /commits/{sha}/pulls` as the canonical source for merged-PR metadata such as `merge_commit_sha`.

The release runner rejected that association-list projection twice. Independent canonical GitHub PR evidence for the same uniquely associated PR #517 reports the exact accepted merge commit, exact PR head and `base=main`. Git object evidence also proves that the PR head and resulting squash-merge commit reference the identical source tree.

The defect was therefore the evidence-source boundary: association discovery and canonical pull-request metadata were conflated. The association-list row is sufficient to establish unique PR identity, but canonical merged-PR fields must be re-hydrated from `GET /pulls/{number}` before they are trusted by a release authority gate.

## Blast radius and adjacent failure modes

Directly affected:

- `scripts/check_v10_sonar_equivalent_tree_provenance.py`;
- deterministic provenance regression tests;
- exact-main Cloudflare production-release gating whenever the default-branch Sonar run is provider-cancelled.

Adjacent failure modes reviewed:

- zero or multiple associated PRs;
- invalid or missing associated PR number;
- malformed canonical PR response;
- canonical PR number not matching the associated identity;
- canonical PR not merged;
- canonical `merge_commit_sha` different from exact main;
- canonical base not `main`;
- invalid PR-head SHA;
- main/head Git-tree mismatch;
- PR-head Sonar non-success or findings;
- exact main superseded before or after evidence collection.

## Permanent correction

Keep the #517 security model and fail-closed semantics intact.

1. `GET /commits/{exact_main}/pulls` is used only to prove exactly one associated PR and obtain its numeric identity.
2. The verifier fetches `GET /pulls/{number}` through the same read-only GitHub authority.
3. The canonical response must be an object and must return the exact same numeric PR identity.
4. Only then are `merged_at`, `base=main`, `merge_commit_sha=exact_main` and exact PR-head SHA enforced.
5. Exact Git-tree identity, exact PR-head Sonar `completed/success`, zero issues/hotspots/annotations and current-main checks remain unchanged.

A stale or incomplete association-list metadata projection can no longer decide the release result, while any mismatch in the canonical PR resource still fails closed.

## Prevention law

Discovery endpoints identify an object; they do not automatically become the authority for all fields of that object. A release/security provenance gate should use stable identity from a listing/association projection, then hydrate the canonical resource before enforcing security-critical mutable or derived metadata.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; no provider secret/value/private payload disclosure; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
