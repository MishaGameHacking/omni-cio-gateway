# V10 Engineering Failure Learning Ledger — FL146

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_SONAR_DEFAULT_BRANCH_PROVIDER_CANCELLATION`
- Scope: exact-main release acceptance after PR #515

## Observed failure

After PR #515 landed as protected `main` SHA `c35c499747339e78d4863003492f153fd019b4da`, repository-owned post-merge workflows completed successfully, while the external `SonarCloud Code Analysis` check on that exact main SHA completed `cancelled`. The Cloudflare production release then stopped before provider mutation, as required by Amendment 16.

The same default-branch Sonar cancellation pattern was observed on several earlier accepted-main SHAs. By contrast, Sonar pull-request analysis on PR #515 exact head `0569fc40cbf7a2f69cd35bc6f7401759acfd1502` completed `success` with Quality Gate passed, zero New issues, zero Security Hotspots and zero annotations.

Git object inspection established that PR #515 exact head and the resulting squash-merge main commit both reference the identical tree `21cc55511c92c0aa44d17939d9f1eabb0d3b9af6`. Therefore the landed source content had already received normal successful Sonar analysis; the recurring failure was on Sonar's separate default-branch automatic-analysis path.

## Root cause class

The repository's post-merge policy correctly rejected the cancelled exact-main Sonar check, but it had no bounded recovery path for the specific case where:

1. Sonar's main/default-branch provider execution is cancelled;
2. GitHub proves the exact squash merge came from one merged PR;
3. the merged commit and certified PR head are byte-for-byte source equivalent at the Git-tree level; and
4. that exact PR head has a normal successful zero-finding Sonar result.

Blind reruns do not solve this class because the default-branch cancellation has recurred across multiple accepted-main SHAs. Treating `cancelled` as success would weaken the Green Checkpoint law and is forbidden.

## Blast radius and analogous surfaces

Directly coupled surfaces:

- `scripts/check_v10_cloudflare_postmerge_release_gate.py`;
- `scripts/check_v10_sonar_equivalent_tree_provenance.py`;
- `.github/workflows/v10-cloudflare-production-release.yml`;
- `docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json`;
- `scripts/check_v10_green_checkpoint_ci_repair.py`;
- deterministic regression tests for both release-gate and provenance behavior.

Adjacent failure modes considered:

- multiple or ambiguous associated PRs;
- non-main PR base;
- merge SHA mismatch;
- source-tree mismatch between merged main and PR head;
- wrong GitHub App identity;
- PR-head Sonar cancelled/failure/non-zero findings;
- annotations on the cancelled main check;
- main superseded during evidence collection;
- pagination/truncation of associated-PR evidence;
- attempting the fallback for any terminal conclusion other than `cancelled`.

## Permanent correction

The exact-main direct success path remains unchanged and preferred.

A second, narrowly bounded provenance path is permitted only when the latest exact-main Sonar check from `sonarqubecloud` is `completed/cancelled` with zero annotations. The release gate then requires GitHub read-only evidence proving exactly one merged PR introduced the exact main commit, `base=main`, the PR's `merge_commit_sha` equals current main, merged-main and PR-head Git tree SHAs are identical, and the exact PR head has normal `completed/success` Sonar evidence with zero New issues, zero Security Hotspots and zero annotations.

Current `main` is checked before and after provenance collection. Any ambiguity, mismatch, finding, provider drift, non-success PR-head check or exact-main terminal state other than `cancelled` fails closed.

The production-release workflow receives only `pull-requests: read` in addition to its existing read-only GitHub evidence permissions. No provider secret scope is broadened.

## Prevention law

A provider execution failure and a source-quality failure are not interchangeable evidence classes. A cancelled provider run must never be renamed GREEN. When an independently certified artifact is used as recovery evidence, equivalence must be cryptographically anchored to the exact deployed source object and all provenance edges must be unique, current and fail-closed.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; no provider secret/value/private payload disclosure; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
