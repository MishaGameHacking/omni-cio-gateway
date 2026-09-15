# V10 Engineering Failure Learning Ledger — FL145

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_POSTMERGE_RELEASE_GATE_EXTERNAL_CHECK_BLIND_SPOT`
- Scope: exact-main release acceptance after PR #514

## Observed failure

PR #514 was squash-merged after exact-head GitHub Actions and Sonar certification. The resulting protected `main` SHA entered its post-merge batch. Repository-controlled push workflows, including Regression Shield, proceeded successfully, while the external `SonarCloud Code Analysis` check for the exact new `main` SHA completed with conclusion `cancelled` and the provider-reported analysis failure marker.

Amendment 16 explicitly rejects `cancelled` as GREEN and defines any applicable post-merge RED on current `main` as `MAIN_RED_STOP`.

After Regression Shield completed `success`, `V10 Cloudflare Production Release` #60 started automatically. Its `Require all exact-main post-merge push workflows` step reported READY because `scripts/check_v10_cloudflare_postmerge_release_gate.py` queried only `/actions/runs` for push-triggered GitHub Actions workflows. The gate did not query commit check-runs, so it could not observe the external Sonar check at all.

At defect discovery the release had not reached production promotion. No broker, Real-money, public-user or product-identity authority changed.

## Root cause

The post-merge release gate modeled exact-main GREEN as GitHub Actions workflow success only. That was narrower than the accepted Green Checkpoint authority, which requires applicable external review evidence such as Sonar to conclude `success` and rejects `cancelled`, `failure`, `neutral`, `skipped` and other non-success conclusions.

The repository already had the correct external-check pattern on the PR path: `scripts/check_v10_pr_external_review_gate.py` reads exact-head GitHub check-runs and binds the Sonar check by its check name. The CF-D post-merge release gate did not consume an equivalent check-run surface.

The immediate Sonar analysis cancellation may be an external provider/analyzer incident and is not reclassified by this repair. Regardless of why Sonar was RED, production release authority must not be able to ignore that RED.

## Blast radius and analogous surfaces

Directly coupled surfaces reviewed:

- `scripts/check_v10_cloudflare_postmerge_release_gate.py`;
- `.github/workflows/v10-cloudflare-production-release.yml`, which invokes the gate before staging and immediately before production promotion;
- `docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json`;
- `scripts/check_v10_green_checkpoint_ci_repair.py`;
- `scripts/check_v10_pr_external_review_gate.py` as the existing external-check reference pattern;
- `tests/test_v10_cloudflare_postmerge_release_gate.py`;
- `tests/test_v10_green_checkpoint_ci_repair.py`.

Adjacent failure mode: any required external GitHub App check can be invisible to a release gate that observes only Actions workflow runs. Matching only a check name is also insufficient because an internal workflow could reuse that name. Provider identity must therefore be bound as well.

## Permanent correction

- Keep the existing exact-main GitHub Actions workflow gate unchanged.
- Add a second exact-commit evidence surface using GitHub commit check-runs.
- Grant the production-release workflow explicit read-only `checks: read` authority so the check-runs evidence surface is actually available under explicit GitHub token permissions.
- Bind the required post-merge Sonar evidence by both exact check name `SonarCloud Code Analysis` and GitHub App slug `sonarqubecloud`.
- Require the latest matching exact-main check to be `completed` with conclusion `success` and zero annotations.
- Treat missing or in-progress external evidence as bounded pending, never GREEN.
- Treat any terminal non-success external conclusion as immediate fail-closed RED.
- Re-run the same gate immediately before production promotion, preserving the existing superseded-main check.
- Record the requirement in the Amendment-16 machine contract and deterministic governance verifier.

## Regression guards

Deterministic coverage requires:

- a same-name check from the wrong GitHub App must not satisfy the gate;
- a matching provider check with `cancelled` must stop the gate;
- the latest matching provider check is authoritative over an older successful one;
- non-zero annotations must stop the gate;
- missing/in-progress external evidence remains pending;
- exact-SHA check-run filter drift fails closed;
- check-run pagination remains bounded and complete;
- current-main recheck still occurs after both workflow and external evidence become GREEN.

## Prevention law

A release gate may certify only the evidence classes required by its governing checkpoint contract. If external checks participate in GREEN certification, observing only GitHub Actions workflow runs is insufficient. Release authority must consume the exact commit's required external check-runs with provider identity binding and SUCCESS-only semantics.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; no provider secret or identifier disclosure; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
