# V10 Engineering Failure Learning Ledger — FL149

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_POSTMERGE_PR_MERGE_SHA_NULL_PROVENANCE`
- Scope: exact-main Sonar equivalent-tree fallback after PR #521

## Accepted evidence chain

PR #521 landed as protected `main` SHA `5362d8cbfd770973fd67e513232fc61a0d40996e`. Exact-new-main push workflows, including Regression Shield and Engineering Governance, completed successfully. The exact-main external `SonarCloud Code Analysis` check completed provider-side `cancelled` with zero annotations, so the narrowly eligible fail-closed equivalent-tree fallback applied.

The fresh production-release workflow stopped before any Cloudflare provider mutation with:

`CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_SHA_INVALID`

Two Amendment-16 same-SHA specific-job reruns reproduced the same terminal result. Further blind reruns were stopped.

Outside the release-runner token/cache context, the canonical PR resource reports PR #521 merged into `main` with `merge_commit_sha=5362d8cbfd770973fd67e513232fc61a0d40996e`. Independently, the PR issue-event timeline contains exactly one `merged` event whose `commit_id` is the same exact accepted main SHA.

The production workflow already grants `pull-requests: read`. GitHub's issue-event endpoint accepts Pull requests read permission, so the immutable merge-event evidence is available without adding broader workflow authority.

## Root cause

The equivalent-tree verifier treated canonical PR `merge_commit_sha` as the sole exact post-merge commit identity. `_sha_field(...)` intentionally rejects any non-string value, so an explicit provider JSON `null` was classified together with malformed or missing SHA data as immediate terminal corruption.

The release-runner evidence proves that GitHub can expose the canonical field as explicit `null` in one token/cache context after the pull request is already merged, while another context later exposes the exact squash commit. A provider-null field is not acceptable as GREEN, but it is also not equivalent to a malformed non-null SHA when an independent immutable GitHub merge event proves the exact merged commit.

## Blast radius and adjacent failure modes

Directly affected:

- `scripts/check_v10_sonar_equivalent_tree_provenance.py`;
- Green Checkpoint machine governance for cancelled exact-main Sonar fallback;
- deterministic provenance regression tests;
- exact-main Cloudflare production release when canonical `merge_commit_sha` is explicit JSON `null`.

Adjacent cases reviewed:

- missing `merge_commit_sha` key;
- malformed non-null merge SHA;
- valid non-null merge SHA that differs from exact main;
- zero or multiple `merged` issue events;
- malformed or missing merge-event `commit_id`;
- merge-event commit mismatch;
- issue-event pagination overflow/truncation;
- non-main base, invalid PR head or ambiguous associated PR;
- Git-tree mismatch;
- PR-head Sonar non-success or findings;
- exact-main annotations/provider drift;
- current `main` supersession during release evidence collection.

## Permanent correction

Canonical `merge_commit_sha` remains the primary proof.

If the key is present and contains a valid full SHA, exact equality with accepted main remains mandatory. A valid different SHA remains bounded `PENDING` through the existing outer release wait. A malformed non-null value remains terminal RED, and a missing key remains terminal RED.

Only when the key is present and its value is exactly JSON `null` does the verifier use the independent issue-event proof. It reads the PR event timeline with bounded pagination, requires exactly one `merged` event, requires a valid full `commit_id`, and requires that commit id to equal exact accepted main. Null itself never authorizes success.

After merge identity is proven, every existing fail-closed requirement remains unchanged: merged PR identity, `base=main`, valid head, exact Git-tree equality, PR-head Sonar normal success with zero findings, and current-main recheck.

No new sleep loop, no second deadline, no broader GitHub permission and no provider mutation are introduced by this correction.

## Prevention law

A security-critical provider field may have a documented or observed nullability/cache inconsistency without becoming optional evidence. If an independent immutable provider record exists for the same state transition, an explicit-null primary field may be resolved only through a narrowly scoped, exact-identity alternate proof. Missing schema, malformed non-null data, ambiguity, truncation and identity mismatch must remain terminal. Alternate proof must not broaden permissions, weaken equality, create competing deadlines or accept stale source identity.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; no provider secret/value/private payload disclosure; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
