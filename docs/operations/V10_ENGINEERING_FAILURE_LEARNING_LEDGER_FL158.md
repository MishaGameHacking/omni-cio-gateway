# V10 Engineering Failure Learning — FL158

Failure class: `CF_D_REQUIRED_RECOVERY_SKIP_PROPAGATION`

Date: 2026-09-17

Scope: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D / V10 Cloudflare Production Release`

## Observed failure

Production Release #72 on exact protected `main` `cb75074ad8f15a90565dbf79a75c8ad0bfa680df` completed with workflow conclusion `success`, but the real release chain was incomplete.

The exact-main staging rehearsal succeeded and the production runtime-secret probe emitted:

`CLOUDFLARE_PRODUCTION_DATABASE_SECRET=BOOTSTRAP_REQUIRED`

`CLOUDFLARE_PRODUCTION_DATABASE_RECOVERY=HOSTED_EGRESS_REQUIRED`

Despite that required state, job `CF-D hosted production database recovery` concluded `skipped`, and the downstream `CF-D exact-main gated production promotion` also concluded `skipped`.

The same workflow already had a legitimately skipped staging-recovery job because the reusable staging database secret existed. That skipped ancestor was therefore part of the dependency graph before the production-recovery decision.

## Root cause

GitHub Actions job-level `if` evaluation has status-check semantics. Without an explicit status-check function, an implicit success-status condition participates in dependency evaluation. In a dependency graph containing a skipped ancestor, a later job can be skipped before the intended output comparison is allowed to drive the required recovery path.

The production recovery job used only:

`needs.rehearse.outputs.production_bootstrap_required == 'true'`

It did not explicitly neutralize inherited skip propagation with a status-check function and did not require the direct producer job result to be `success` in the same expression.

The staging recovery job used the same vulnerable condition shape, so the defect class existed symmetrically even though staging secret reuse meant it did not trigger in Release #72.

A second failure mode amplified the defect: the workflow had no terminal fail-closed DAG sentinel. If an applicable recovery or promotion job was skipped, all executed jobs could still be `success`, allowing the workflow itself to appear green despite incomplete release authority.

## Adjacent cancellation hazard

The first repair checkpoint used `always()` to override inherited skip propagation. That solves the skip-propagation defect, but `always()` has a materially different cancellation semantic: GitHub re-evaluates running job conditions during workflow cancellation, and `always()` remains true even when the workflow is cancelled.

That behavior is acceptable for bounded read-only cleanup/terminal observation, but not as the job-level status function for release jobs that can mutate Neon or Cloudflare state.

Permanent release orchestration therefore uses the following invariant:

`CANCELLATION_FAIL_CLOSED`

Provider-mutating release jobs use `!cancelled()` plus explicit producer/result requirements. The terminal read-only release outcome sentinel retains `always()` so incomplete/cancelled release graphs cannot be mistaken for an accepted production release.

## Permanent correction

The four conditional jobs that can reach provider mutation use cancellation-safe status semantics:

- staging recovery: `!cancelled() && inspect_database_state.result == 'success' && staging_bootstrap_required == 'true'`;
- staging rehearsal/production-state probe: `!cancelled() && inspect_database_state.result == 'success' && (staging_bootstrap_required == 'false' || hosted staging recovery == 'success')`;
- production recovery: `!cancelled() && rehearse.result == 'success' && production_bootstrap_required == 'true'`;
- production promotion: `!cancelled() && rehearse.result == 'success' && (production_bootstrap_required == 'false' || hosted production recovery == 'success')`.

This preserves conditional execution when a secret is already reusable, prevents an earlier skipped dependency from silently suppressing a recovery that the immediate producer explicitly requires, and prevents provider-mutating downstream jobs from remaining eligible after workflow cancellation.

A final `CF-D release DAG terminal fail-closed gate` runs with `always()` for applicable release invocations and validates the complete state machine:

1. database-state inspection succeeded;
2. staging bootstrap output is exactly `true` or `false`;
3. when staging recovery is required, hosted staging recovery concluded `success`;
4. rehearsal succeeded;
5. production bootstrap output is exactly `true` or `false`;
6. when production recovery is required, hosted production recovery concluded `success`;
7. production promotion concluded `success`.

Missing/invalid outputs, required-but-skipped recovery, failed recovery, skipped promotion, or a cancellation that prevents provider-mutating jobs from completing therefore cannot produce terminal release acceptance.

## Security and authority invariants

This repair changes only GitHub Actions orchestration semantics.

It does not widen Neon authority, Cloudflare authority, PostgreSQL role authority, DNS/domain authority, tenant scope or product activation.

Unchanged:

- project-scoped Neon management credential boundary;
- PostgreSQL 18 + RLS/FORCE RLS;
- exact-main release provenance;
- hosted recovery only when a runtime secret is genuinely absent;
- no DSN/provider identifiers in job outputs, artifacts or summaries;
- V9 `app:app`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`.

## Regression guard

`tests/test_v10_cloudflare_cf_d_hosted_egress_recovery.py` freezes:

- explicit `!cancelled()` + direct-producer-success semantics on both hosted recovery jobs;
- cancellation-safe job-level conditions for staging rehearsal and production promotion;
- absence of job-level `always()` on the four provider-mutating conditional jobs;
- staging/production symmetry;
- the terminal read-only `always()` fail-closed DAG gate;
- rejection of a required recovery that does not end in `success`;
- required successful production promotion before terminal success.

## Acceptance requirement

Because the defect occurred on protected `main`, Amendment 16 `MAIN_RED_STOP` remains active until the focused repair is exact-head certified, squash-merged, exact-new-main post-merge checks succeed, and a fresh Production Release demonstrates that a genuinely required production recovery executes rather than being skipped and proceeds to canonical promotion/live acceptance.
