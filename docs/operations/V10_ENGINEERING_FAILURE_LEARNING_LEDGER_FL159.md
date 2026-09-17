# V10 Engineering Failure Learning — FL159

Failure class: `CF_D_SONAR_EXACT_MAIN_SUITE_STALLED`

Date: 2026-09-17

Scope: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D / exact-main release acceptance`

## Observed failure

PR #538 was squash-merged as exact protected `main` `c7fe6f9380208a41d5763bab180a434215e80fdb` after exact-head GitHub Actions and Sonar certification.

The complete repository-owned post-merge push batch on that exact main SHA reached `success`. Production Release #73 attempts 2 and 3 each waited the full bounded post-merge gate and stopped before provider mutation with:

`CLOUDFLARE_POSTMERGE_GATE=STOPPED code=CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_PENDING`

The first evidence read showed zero matching `SonarCloud Code Analysis` **check-runs** on exact main. A stronger GitHub Checks read then proved that the provider event was not absent: app `sonarqubecloud` had created an exact-main **check suite** at merge time, but the suite remained `status=queued`, `conclusion=null`, `latest_check_runs_count=0` and never produced a check-run during either bounded release attempt.

At the same time, GitHub proved all source-equivalence edges needed for independent source-quality evidence:

- merged PR: #538;
- PR exact head: `eb1fa57f8598e286de937ddbc97134643b31060c`;
- canonical PR merge commit: exact main `c7fe6f9380208a41d5763bab180a434215e80fdb`;
- PR head Git tree: `e199005b404c2330fd750dd2dfc3df74730202ad`;
- exact-main Git tree: the same `e199005b404c2330fd750dd2dfc3df74730202ad`;
- PR-head Sonar: `completed/success`, Quality Gate passed, `0 New issues`, `0 Security Hotspots`, `0 annotations`.

A same-SHA failed-jobs rerun under Amendment 16 reproduced the same release stop, so blind rerun was exhausted.

## Root cause

The release gate had two accepted external Sonar evidence paths:

1. preferred direct exact-main `completed/success` check-run evidence;
2. narrow equivalent-tree provenance recovery when an exact-main check-run existed and concluded `cancelled`.

When no exact-main check-run existed, `_external_evidence_state()` correctly remained pending, but the deadline path originally inspected check-runs only. It therefore could not distinguish:

- a genuinely absent Sonar suite;
- a Sonar suite acknowledged by GitHub but stalled in `queued`/`in_progress` with zero check-runs.

Treating `check-runs == 0` alone as provider absence would be too broad because a queued provider suite is still pending external work. The provider-side reason for the stall is intentionally not guessed.

## Blast radius and analogous surfaces

Directly coupled surfaces:

- `scripts/check_v10_cloudflare_postmerge_release_gate.py`;
- `scripts/check_v10_sonar_equivalent_tree_provenance.py`;
- `docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json`;
- deterministic release-gate, provenance and governance tests.

Adjacent failure modes reviewed:

- direct exact-main Sonar check-run is late and `in_progress`;
- exact-main check-run concludes `failure` or reports findings;
- cancelled exact-main check-run follows accepted FL146;
- provider suite exists but is queued/in-progress with zero check-runs;
- provider suite reaches a terminal conclusion without a usable check-run;
- provider suite or check-run appears/changes during provenance collection;
- multiple/ambiguous associated PRs;
- non-main PR base;
- canonical merge mismatch;
- PR-head/main Git-tree mismatch;
- PR-head Sonar is missing, cancelled, failed or non-zero;
- current main changes during evidence collection.

## Permanent correction

The preferred path is unchanged: an exact-main Sonar check-run, when present, must be `completed/success` with zero New issues, zero Security Hotspots and zero annotations.

No missing/stalled condition is immediately reclassified as GREEN. Throughout the normal bounded wait, lack of a completed exact-main check-run remains pending exactly as before.

Only after the full configured wait has expired, and only after all repository-owned exact-main push workflows are successful, the deadline path may enter equivalent-tree recovery.

The provenance verifier then reads exact-main check suites as well as check-runs:

- no matching suite -> `missing_exact_main_after_bounded_wait` candidate;
- latest matching suite `queued` or `in_progress`, `conclusion=null`, zero check-runs -> `stalled_exact_main_suite_after_bounded_wait` candidate;
- any terminal/non-null suite conclusion or non-zero check-run count is not eligible for stalled-suite fallback;
- any exact-main check-run that appears remains authoritative and aborts the fallback attempt;
- a suite that appears, disappears, changes identity, leaves the stalled state, or gains a check-run during provenance aborts the fallback attempt.

Neither a queued suite nor a missing suite is counted as a successful provider execution. Recovery is permitted only because the exact landed source tree can be independently bound to a previously normal Sonar analysis of the exact same source tree.

Both missing and stalled-suite recovery reuse the cryptographic/evidence chain accepted for FL146:

1. current main equals expected SHA;
2. exactly one associated merged PR;
3. canonical PR base is `main`;
4. canonical merge identity equals exact main, with the accepted unique merged-event fallback only when GitHub omits the merge SHA;
5. exact-main and PR-head Git trees are identical;
6. exact PR head has normal `sonarqubecloud` `completed/success` evidence with zero findings/annotations;
7. current main is rechecked during and after evidence collection.

## Regression guards

Deterministic tests freeze that:

- no-check-run evidence remains pending during normal polling;
- deadline-only recovery classifies missing versus stalled provider suite;
- stalled suite requires `queued|in_progress`, null conclusion and zero check-runs;
- terminal/non-zero suite states are rejected;
- a check-run appearing during provenance aborts fallback;
- a previously missing suite appearing during provenance aborts fallback;
- a stalled suite changing identity/state during provenance aborts fallback;
- suite pagination and exact-SHA filtering fail closed;
- unique merged-PR, exact merge identity, identical Git tree and normal green PR-head Sonar remain mandatory;
- Amendment-16 machine contract records both missing and stalled-suite conditions.

## Prevention law

`check-runs == 0` is not sufficient proof that an external provider did not receive the event. Release authority must inspect provider check-suite state before classifying no-check-run evidence. A persistently stalled external suite is never called GREEN; after a full bounded direct-evidence wait it may be replaced only by a unique, cryptographically anchored, exact-source-equivalent provider analysis that already proved the landed source tree clean.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; exact-current-main release authority; Cloudflare and Neon secret boundaries; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
