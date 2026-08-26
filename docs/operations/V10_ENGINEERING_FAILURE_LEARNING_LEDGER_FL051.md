# FL-051 — Accepted temporal gates must stop re-binding historical evidence to later PR bases

Status: **ADDITIVE FAILURE-LEARNING ENTRY; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-27**  
Scope: **Amendment 12 governance PR #393 / verification head `b147d208d7f8539655f8660da2a0d49b552a6692`**

## Symptom / failing gates

After the Amendment 12 synchronization head was treated as preflight-ready, the safe exact-head verification batch produced three independent quality findings while the normal repository/product guards remained green:

- `V10 WP22A Phase 5 Technical Closeout` failed before substantive re-verification because accepted Phase-5 evidence was intentionally bound to the historical accepted main SHA, not the later governance PR base;
- `V10 WP22A Phase 4 Public Acceptance` retried the already accepted hosted preview against the later PR base and failed with `HEALTH_CONTRACT_MISMATCH detail=release_sha`;
- SonarQube Cloud reported new-code duplication at the quality-gate boundary in the newly added governance validator, and Gitar found that the new supplementary governance test module was not executed by the governance workflow.

The other observed PR workflows, including the authoritative Windows lane, Fast PR checks, Toolchain Compatibility, Engineering Governance and current product audits, completed successfully on the same verification head.

## Root cause

Two process defects were present.

First, Phase-4 and Phase-5 acceptance workflows were originally designed as temporal/exact-release proof gates. Their `pull_request.paths` lists later expanded to include live status, generic governance and transition-test surfaces. After WP22A acceptance, ordinary governance/status edits therefore re-triggered those historical gates, which correctly rejected a new PR base because the immutable accepted release/evidence remained bound to an earlier main SHA. The failure was an applicability defect, not a reason to rewrite accepted evidence to the latest base.

Second, the new Amendment-12 guard/test integration was preflight-reviewed for behavior but not sufficiently for verifier quality: repeated validation boilerplate pushed Sonar duplication to the gate boundary, while the governance workflow executed the enforcement script but omitted the supplementary regression test module.

## Blast radius searched

Reviewed:

- `.github/workflows/v10-wp22a-phase4-public-acceptance.yml`;
- `.github/workflows/v10-wp22a-phase5-technical-closeout.yml`;
- accepted Phase-4/Phase-5 evidence and exact-base binding semantics;
- current live status/governance surfaces that had become over-broad trigger inputs;
- `scripts/check_v10_integrated_system_update_governance.py`;
- `tests/test_v10_integrated_system_update_governance.py`;
- `.github/workflows/v10-engineering-governance.yml`;
- analogous risk that a regression test can exist in source while no authoritative workflow executes it.

GitHub's documented `pull_request.paths` behavior confirms that a workflow runs when the PR changed-file set matches the configured path filters; therefore routing is the correct place to make an accepted one-shot gate non-applicable to unrelated later governance work.

## Corrective change

- Narrow the historical Phase-4/Phase-5 PR path routing to their immutable acceptance evidence/contract surfaces rather than generic live status/governance/test files.
- Preserve the historical exact-base and exact-release checks themselves; do not mutate accepted evidence merely to follow future PR bases.
- Add deterministic routing regression tests so live status/governance edits cannot silently reactivate the historical one-shot gates.
- Refactor the Amendment-12 validator to shared data-driven helpers without weakening any required marker or protected invariant.
- Convert the supplementary governance tests to `unittest` and execute both new regression modules explicitly from `v10-engineering-governance.yml`.

## Permanent prevention rule

Once an exact-release/temporal acceptance gate has completed and its evidence is immutable historical authority, future changes must distinguish between:

1. editing that historical evidence/contract itself, where the owning historical gate remains applicable; and
2. later live status/governance/product work, which must use permanent current-state guards and must not re-bind old release evidence to a new PR base.

Every new permanent guard must have both an enforcement path and an authoritative CI regression path. A test file merely existing in the repository is not coverage evidence.

## Dependency/tooling knowledge change

No dependency or runtime version changed. The reusable tooling lesson is GitHub Actions routing semantics: path filters are part of the acceptance contract, not incidental workflow plumbing. Sonar duplication thresholds and independent review remain verifier signals that must be addressed structurally rather than suppressed.
