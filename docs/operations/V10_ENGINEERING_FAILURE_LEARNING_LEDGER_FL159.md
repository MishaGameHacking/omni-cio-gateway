# V10 Engineering Failure Learning — FL159

Failure class: `CF_D_SONAR_EXACT_MAIN_CHECK_MISSING`

Date: 2026-09-17

Scope: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D / exact-main release acceptance`

## Observed failure

PR #538 was squash-merged as exact protected `main` `c7fe6f9380208a41d5763bab180a434215e80fdb` after exact-head GitHub Actions and Sonar certification.

The complete repository-owned post-merge push batch on that exact main SHA reached `success`. Production Release #73 then waited the full bounded post-merge gate and stopped before provider mutation with:

`CLOUDFLARE_POSTMERGE_GATE=STOPPED code=CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_PENDING`

Direct GitHub check-run evidence showed that the exact main commit had **no** matching `SonarCloud Code Analysis` check from GitHub App `sonarqubecloud`. This differs from FL146, where the exact-main provider check existed but concluded `cancelled`.

At the same time, GitHub proved all source-equivalence edges needed for independent source-quality evidence:

- merged PR: #538;
- PR exact head: `eb1fa57f8598e286de937ddbc97134643b31060c`;
- canonical PR merge commit: exact main `c7fe6f9380208a41d5763bab180a434215e80fdb`;
- PR head Git tree: `e199005b404c2330fd750dd2dfc3df74730202ad`;
- exact-main Git tree: the same `e199005b404c2330fd750dd2dfc3df74730202ad`;
- PR-head Sonar: `completed/success`, Quality Gate passed, `0 New issues`, `0 Security Hotspots`, `0 annotations`.

A same-SHA failed-jobs rerun was attempted under Amendment 16, but an absent provider check cannot be created by blindly repeating the repository release gate.

## Root cause

The release gate had two accepted external Sonar evidence paths:

1. preferred direct exact-main `completed/success` evidence;
2. a narrow equivalent-tree provenance recovery only when the exact-main provider check existed and concluded `cancelled`.

When no exact-main Sonar check existed, `_external_evidence_state()` returned pending on every poll. After the bounded wait expired, the gate had no second-stage classification for the difference between:

- a still-running provider check; and
- a provider check that never materialized.

Both states therefore ended as the same permanent `EXTERNAL_CHECK_PENDING` blocker.

The provider-side reason the exact-main check did not materialize is intentionally not guessed. SonarQube Cloud documents main-branch analysis as normally triggered when main changes, but repository release authority must remain safe even when an external provider execution is absent.

## Blast radius and analogous surfaces

Directly coupled surfaces:

- `scripts/check_v10_cloudflare_postmerge_release_gate.py`;
- `scripts/check_v10_sonar_equivalent_tree_provenance.py`;
- `docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json`;
- deterministic release-gate, provenance and governance tests.

Adjacent failure modes reviewed:

- an exact-main Sonar check is merely late and still `in_progress`;
- exact-main Sonar concludes `failure` or reports findings;
- cancelled exact-main Sonar follows the already accepted FL146 path;
- multiple/ambiguous associated PRs;
- non-main PR base;
- canonical merge mismatch;
- PR-head/main Git-tree mismatch;
- PR-head Sonar is missing, cancelled, failed or non-zero;
- current main changes during evidence collection.

## Permanent correction

The preferred path remains unchanged: an exact-main Sonar check, when present, must be `completed/success` with zero New issues, zero Security Hotspots and zero annotations.

Missing exact-main evidence is **not** immediately reclassified as GREEN. During the normal bounded wait it remains pending exactly as before.

Only after the full configured wait has expired, and only if all repository-owned exact-main push workflows are already successful, the gate performs a fresh check-run read:

- if a matching exact-main check now exists, normal exact-main/cancelled semantics remain authoritative;
- if the check is still in progress, release remains pending/fail-closed;
- if it is a terminal failure/finding, release remains terminal RED;
- only if **no matching exact-main provider check exists** may the missing-evidence provenance recovery run.

The missing-evidence recovery reuses the same cryptographic chain accepted for FL146:

1. current main equals expected SHA;
2. exactly one associated merged PR;
3. canonical PR base is `main`;
4. canonical merge identity equals exact main, with the already accepted unique merged-event fallback only when GitHub omits the merge SHA;
5. exact-main and PR-head Git trees are identical;
6. exact PR head has normal `sonarqubecloud` `completed/success` Sonar evidence with zero findings/annotations;
7. current main is rechecked after evidence collection.

The resulting evidence is explicitly labeled `missing_exact_main_after_bounded_wait`; the absent provider run is never called successful.

## Regression guards

Deterministic tests freeze that:

- missing exact-main Sonar remains pending during normal polling;
- the missing fallback is reachable only from the deadline path;
- an in-progress exact-main check blocks the missing fallback;
- terminal provider failure/finding never uses the missing fallback;
- missing evidence still requires unique merged-PR, exact merge identity, identical Git tree and normal green PR-head Sonar;
- current main is checked before and after provenance certification;
- the Amendment-16 machine contract records the bounded-wait and no-matching-main-check preconditions.

## Prevention law

An absent external-provider execution is not a successful execution, but it is also not automatically a source-quality failure. A release may recover from persistent provider absence only after a bounded direct-evidence wait and only through a unique, cryptographically anchored, exact-source-equivalent evidence chain that already received the required normal provider analysis.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; exact-current-main release authority; Cloudflare and Neon secret boundaries; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
