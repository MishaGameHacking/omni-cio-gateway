# V10 Engineering Failure Learning Ledger — FL148

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_POSTMERGE_PR_MERGE_SHA_CONVERGENCE`
- Scope: exact-main Sonar equivalent-tree fallback after PR #519

## Accepted evidence chain

PR #519 landed as protected `main` SHA `1af49b53a932775c3650d728da43c8aeae2df8f4`. Exact-new-main Regression Shield and V10 Engineering Governance completed successfully. The exact-main external `SonarCloud Code Analysis` check completed provider-side `cancelled` with zero annotations, which is the narrowly eligible fail-closed fallback class introduced by #517.

The first production-release attempt stopped correctly because one exact-main `V10 WP17 Application Shell Audit` browser test had timed out. Under Amendment 16, the unchanged exact SHA/job was rerun. The rerun passed all 22 browser tests and all remaining WP17 quality, security and recovery checks. GitHub then reported all 11 exact-main push workflows as `completed/success`.

A specific same-SHA retry of the failed production-release job then passed the push-workflow gate but stopped before any provider mutation inside the Sonar provenance fallback with:

`CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_SHA_MISMATCH`

Current canonical GitHub PR evidence for #519 reports the exact accepted main SHA as `merge_commit_sha`, `base=main`, the exact PR head, and the PR head/main Git objects share the same source tree. Therefore the failure was not a source-equivalence defect and not a Sonar finding.

## Root cause

GitHub defines `merge_commit_sha` as state-dependent metadata: before merge it can represent the test merge commit, while after a squash merge it represents the squashed commit on the base branch. The release runner observed a syntactically valid but not-yet-converged canonical merge SHA after the PR had already been merged. Later reads of the canonical PR resource returned the expected exact-main SHA.

The verifier treated any valid SHA mismatch as immediate permanent corruption. This classification was too strict for an eventually convergent provider metadata field and bypassed the intent of the already-required bounded release evidence wait.

## Blast radius and adjacent failure modes

Directly affected:

- `scripts/check_v10_sonar_equivalent_tree_provenance.py`;
- deterministic provenance regression tests;
- exact-main Cloudflare production release when the default-branch Sonar run is provider-cancelled and PR metadata has not converged yet.

Adjacent cases reviewed:

- missing or malformed merge SHA;
- persistent valid merge-SHA mismatch;
- current `main` superseded during convergence;
- zero or multiple associated PRs;
- canonical PR identity mismatch;
- non-main base;
- invalid PR head;
- Git-tree mismatch;
- PR-head Sonar non-success or findings;
- exact-main annotations/provider drift.

## Permanent correction

Exact merge-SHA equality remains mandatory and no mismatch is accepted as GREEN.

For the single provider-metadata case where the canonical `merge_commit_sha` is a syntactically valid full SHA but differs from exact main, the provenance verifier now performs a fixed bounded convergence wait. Between retries it re-checks that current `main` is still the expected SHA. Certification can continue only after canonical `merge_commit_sha` exactly equals expected main.

Malformed or missing merge SHA remains terminal RED. Every unrelated provenance defect remains terminal RED. A valid mismatch that persists through the bounded attempts is re-raised as the original mismatch and production remains blocked.

This implements the existing Amendment-16 `bounded_wait_required=true` and `post_merge_cancelled_fallback_merge_sha_must_equal_exact_main=true` laws without weakening either one.

## Prevention law

A security-critical provider metadata field may be eventually consistent without being optional. When the provider contract explicitly defines a state transition for the field, a verifier may use a bounded current-object re-read, but must never substitute stale evidence, accept inequality, or suppress malformed/ambiguous states. The protected source SHA must be revalidated during the wait.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; no provider secret/value/private payload disclosure; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
