# Capacity-Aware Decision Gate V1

## Purpose

This overlay connects an already completed analytical `DecisionSetV1` with the point-in-time market-capacity assessments introduced in PR-44.

It answers a narrow question:

> May the selected analytical change option proceed to further review at the requested sizes?

It does not choose an option, change portfolio targets, calculate affordability, call a broker preview or create an order.

## Inputs

The gate consumes:

- a base `DecisionSetV1`;
- one explicitly requested change-option ID;
- the exact instrument keys affected by that option;
- one capacity assessment per required instrument;
- freshness policy and assessment time.

The requested instrument list must be non-empty and unique.

## Base-decision boundary

The gate abstains when:

- the base decision already abstains;
- the base decision is not recommendation-ready;
- the base decision is stale or materially future-dated;
- the requested option does not exist;
- the requested option is the no-action option;
- the requested option is blocked.

Capacity never upgrades an available/review-only option to preferred. The original `base_preferred_option_id` is preserved in the output.

## Capacity coverage boundary

Capacity assessments are indexed by their request instrument key.

- duplicate instrument assessments are a structural error;
- an assessment for an unrequested instrument is a structural error;
- missing required instruments create a coverage blocker;
- stale or future-dated assessments create blockers;
- any assessment with `capacity_ready=false` creates a blocker.

Every coverage row includes:

- instrument key;
- capacity request ID;
- currency;
- requested notional;
- safe notional;
- safe whole lots;
- capacity readiness;
- assessment timestamp;
- underlying PR-44 capacity blockers.

## Result semantics

When every gate passes:

- `status=ready`;
- `gate_ready=true`;
- `abstain=false`;
- the requested option ID and action are preserved;
- the result only permits further analytical review.

When any gate fails:

- `status=abstain`;
- `gate_ready=false`;
- `abstain=true`;
- the existing no-action option is returned;
- `final_action=wait_for_data`;
- the change option is not retained.

## Deliberate separation

The capacity gate does not:

- decide whether a change is desirable;
- override the base preferred option;
- select an instrument;
- calculate free cash or affordability;
- change risk-policy limits;
- split or route orders;
- predict an execution price;
- call a broker;
- create, replace or cancel an order.

## Safety invariants

Every result retains:

- `capacity_gate_only=true`;
- `option_selected_by_gate=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

The gate is therefore compatible with strict Level 0 read-only operation.

## Compatibility

- no changes to the existing `build_decision_set` signature;
- no broker SDK changes;
- no FastAPI route;
- no OpenAPI operation;
- no GPT Action change;
- no transfer or withdrawal method;
- gateway version remains `3.9.1`;
- Render entrypoint remains `app:app`.

## Rollback

Revert the PR merge commit. Base Decision Engine and PR-44 market-capacity assessment remain independently usable.
