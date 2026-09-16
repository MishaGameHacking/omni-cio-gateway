# V10 Engineering Failure Learning Ledger — FL150

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_POSTMERGE_PR_MERGE_SHA_MISSING_PROVENANCE`
- Scope: exact-main Sonar equivalent-tree fallback after PR #523

## Accepted evidence chain

PR #523 landed as protected `main` SHA `b9eef769b5bf9075f5578317e44db11e62d16783`. Its exact-main push verification completed before the production-release gate started. The exact-main external `SonarCloud Code Analysis` check completed provider-side `cancelled` with zero annotations, so only the narrowly governed equivalent-tree fallback was eligible.

Fresh production-release run `35074463339` stopped before any candidate, staging or production provider mutation with:

`CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_SHA_MISSING`

The release-runner token/API context omitted canonical PR field `merge_commit_sha` entirely. Outside that runner context, the canonical PR resource reports PR #523 merged into `main` with `merge_commit_sha=b9eef769b5bf9075f5578317e44db11e62d16783`.

Independently, the PR #523 issue-event timeline contains exactly one `merged` event whose `commit_id` is the same exact accepted main SHA. The production workflow already grants `pull-requests: read`, and the existing bounded issue-event path therefore requires no broader GitHub authority.

## Root cause

FL149 corrected one observed provider-field availability state: canonical `merge_commit_sha` could be explicit JSON `null` after the pull request was already merged. The verifier intentionally kept complete key omission terminal because omission was treated as schema corruption rather than field unavailability.

The fresh release-runner evidence disproves that distinction for this GitHub token/API context. The same security-critical primary merge-identity field can be unavailable either as explicit `null` or by omission while independent immutable GitHub merge-event evidence still identifies the exact squash commit.

Neither `null` nor omission is acceptable as GREEN evidence by itself. The defect is the assumption that the representation of primary-field unavailability is stable enough to determine whether independent exact merge-event proof may be consulted.

## Blast radius and adjacent failure modes

Directly affected:

- `scripts/check_v10_sonar_equivalent_tree_provenance.py`;
- Green Checkpoint machine governance for cancelled exact-main Sonar fallback;
- deterministic provenance regression tests;
- exact-main Cloudflare production release when canonical `merge_commit_sha` is unavailable by omission.

Adjacent cases reviewed:

- exact valid non-null merge SHA;
- valid non-null merge SHA that differs from exact main;
- malformed non-null merge SHA;
- explicit JSON `null` merge SHA;
- omitted `merge_commit_sha` key;
- zero or multiple `merged` issue events;
- malformed or missing merge-event `commit_id`;
- merge-event commit mismatch;
- issue-event pagination overflow/truncation;
- invalid issue-event response shape;
- non-main base, invalid PR head or ambiguous associated PR;
- Git-tree mismatch;
- PR-head Sonar non-success or findings;
- exact-main annotations/provider drift;
- current `main` supersession during release evidence collection.

## Permanent correction

Canonical `merge_commit_sha` remains the primary proof.

If it is present and contains a valid full SHA, exact equality with accepted main remains mandatory. A valid different SHA remains bounded `PENDING` through the existing outer release wait. A malformed non-null value remains terminal RED.

If the primary field is unavailable, either because its value is exactly JSON `null` or because the key is omitted, the verifier uses the same independent issue-event proof. It reads the PR event timeline with bounded pagination, requires exactly one `merged` event, requires a valid full `commit_id`, and requires that commit id to equal exact accepted main. Primary-field unavailability itself never authorizes success.

After merge identity is proven, every existing fail-closed requirement remains unchanged: merged PR identity, `base=main`, valid head, exact Git-tree equality, PR-head Sonar normal success with zero findings, and current-main recheck.

No new sleep loop, no second deadline, no broader GitHub permission and no provider mutation are introduced by this correction.

## Prevention law

When a security-critical provider field is proven to have multiple context-dependent unavailable representations, those representations must not be assigned different authority merely because one is explicit `null` and another is omitted. Unavailability never becomes proof. A narrowly scoped independent immutable record may resolve the missing primary fact only when it proves the same exact identity with bounded pagination, uniqueness, strict schema validation and exact equality. Malformed non-null data, ambiguity, truncation and identity mismatch remain terminal.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; no provider secret/value/private payload disclosure; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
