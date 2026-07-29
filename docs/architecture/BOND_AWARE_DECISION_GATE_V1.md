# Bond-Aware Decision Gate V1

## Purpose

`build_bond_aware_decision_set` composes the existing analytical Decision Engine with verified bond credit and currency-local portfolio rate-stress evidence.

It does not replace `build_decision_set`, change public Actions or produce executable order parameters. The base engine still creates exactly three alternatives. The bond-aware layer either preserves those alternatives or forces an effective abstain state.

## Inputs

The gate accepts:

- `AdvancedPortfolioAnalyticsV1`;
- `RiskPolicyEvaluationV1`;
- the existing market-readiness and sanitized-news inputs used by the base engine;
- one `BondCreditRiskAssessmentV1` per bond position;
- one `BondPortfolioRateStressV1` per bond currency.

All inputs are immutable typed contracts. No network or broker adapter is imported.

## Coverage rules

For every portfolio position whose instrument type is `bond`:

1. a credit assessment must exist for the exact stable instrument key;
2. the credit assessment must be decision-ready and have no blockers;
3. its duration must not exceed `risk_evaluation.policy.max_duration_years`;
4. its currency must be represented by one portfolio stress assessment;
5. that stress assessment must cover exactly the bond keys held in the currency;
6. the stress current value must equal verified portfolio analytics;
7. the stress worst-loss ratio must not exceed `risk_evaluation.policy.max_stress_loss_ratio`.

Unexpected instruments, duplicate credit keys and duplicate stress currencies raise `BondAwareDecisionError`. Missing, stale or mismatched evidence produces a typed blocker and an effective abstain result.

## Risk-policy reuse

PR-25 introduces no new investment threshold.

It reuses the active conservative policy values already present in `RiskPolicyEvaluationV1`:

- maximum duration;
- maximum stress-loss ratio.

This keeps the decision reproducible and prevents a hidden policy from being embedded in the decision layer.

## Effective alternatives

When the base decision and every bond gate pass:

- the three base options retain their status and action;
- credit warnings may reduce high confidence to medium;
- no execution readiness is introduced.

When either the base decision or a bond gate is blocked:

- `no_action` becomes the only preferred option;
- its action becomes `wait_for_data`;
- limited and strategic changes become blocked;
- confidence becomes low;
- `recommendation_ready=false`.

## Credit warnings

The first version preserves the following non-blocking warnings as evidence:

- recent downgrade;
- exact rating-label divergence between agencies;
- single-agency coverage;
- inactive rating record present;
- explicit absence of cross-agency scale normalization.

A label difference between agencies is not converted into a fabricated common score. Actual stale, missing or contradictory rating evidence remains a blocker in `BondCreditRiskAssessmentV1`.

## Contract integrity

`BondAwareDecisionSetV1` independently verifies:

- base blockers match the nested base decision;
- bond coverage counters do not exceed required coverage;
- exactly three option kinds exist;
- exactly one option is preferred;
- effective abstain matches base and bond blockers;
- blocked decisions prefer `wait_for_data` and block changes;
- ready decisions mirror the source option status and action;
- warning-bearing decisions cannot retain high confidence;
- all evidence and option identifiers are unique.

## Safety boundary

Every output retains:

- `no_cross_currency_aggregation=true`;
- `execution_ready=false`;
- `trading_methods=false`.

PR-25 adds no FastAPI route, HTTP method, operation ID, OpenAPI schema, broker SDK import, confirmation token or execution adapter.

## Limitations

- Credit-rating labels are not normalized across agencies.
- The rate stress inherits linear-duration assumptions from PR-23 and PR-24.
- Convexity, credit-spread migration, taxes, slippage and liquidity are not added by this gate.
- The gate does not select a bond, calculate lots or produce a trade preview.
- UI rendering remains a later package.

## Rollback

Revert the PR-25 merge commit. Existing `build_decision_set`, public Actions, Render configuration and production response schemas remain unchanged.
