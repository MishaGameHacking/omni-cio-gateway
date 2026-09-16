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

The verifier treated any valid SHA mismatch as immediate permanent corruption. This classification was too strict for an eventually convergent provider metadata field and bypassed the intent of the already-required outer 900-second release evidence wait.

A coupled diagnostic defect was also confirmed from the failed workflow traceback. The production gate is executed with `python -m`; the provenance helper imports the canonical module name. A provenance stop can therefore cross the helper boundary as an equivalent code-bearing `RuntimeError` whose class identity is not the gate's local `__main__` class. Without normalization at that boundary, an otherwise expected fail-closed stop may escape the sanitized gate result as a traceback. This does not authorize suppressing arbitrary runtime failures.

## Blast radius and adjacent failure modes

Directly affected:

- `scripts/check_v10_sonar_equivalent_tree_provenance.py`;
- `scripts/check_v10_cloudflare_postmerge_release_gate.py`;
- Green Checkpoint machine governance;
- deterministic provenance and release-gate regression tests;
- exact-main Cloudflare production release when the default-branch Sonar run is provider-cancelled and PR metadata has not converged yet.

Adjacent cases reviewed:

- missing or malformed merge SHA;
- valid merge SHA that stays different until the outer release deadline;
- current `main` superseded during convergence;
- zero or multiple associated PRs;
- canonical PR identity mismatch;
- non-main base;
- invalid PR head;
- Git-tree mismatch;
- PR-head Sonar non-success or findings;
- exact-main annotations/provider drift;
- code-bearing provenance stops crossing the `python -m` module-identity boundary;
- unrelated `RuntimeError` without an approved release-stop code.

## Permanent correction

Exact merge-SHA equality remains mandatory and no mismatch is accepted as GREEN.

For the single provider-metadata case where canonical `merge_commit_sha` is a syntactically valid full SHA but differs from exact main, the provenance verifier raises a dedicated `CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_SHA_CONVERGENCE_PENDING` signal. The release gate converts only that signal to `external_ready=False`. Its already-existing outer bounded wait then performs the next full snapshot, including the current-main recheck, fresh canonical PR read and all other release evidence.

There is no nested provenance sleep loop and no independent second deadline. If the value does not converge before the outer release deadline, the gate terminates with its existing external-evidence pending stop and production remains blocked.

Malformed or missing merge SHA remains immediate terminal RED. Every unrelated provenance defect remains terminal RED. Code-bearing provenance stops are normalized back into the gate's local `ReleaseGateStopped` at the helper boundary so the `python -m` execution path preserves sanitized stop semantics; an unclassified runtime exception is re-raised unchanged and can never be treated as pending.

The machine contract now freezes that a valid mismatch is `PENDING`, convergence uses the outer release wait, malformed merge SHA is terminal, and exact equality remains required before tree/Sonar certification.

## Prevention law

A security-critical provider metadata field may be eventually consistent without being optional. When the provider contract explicitly defines a state transition for the field, the owning outer state machine may classify a syntactically valid not-yet-converged value as bounded `PENDING`, but it must never substitute stale evidence, accept inequality, create competing deadlines, or suppress malformed/ambiguous states. The protected source SHA and all coupled evidence must be revalidated on every outer poll.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; no provider secret/value/private payload disclosure; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
