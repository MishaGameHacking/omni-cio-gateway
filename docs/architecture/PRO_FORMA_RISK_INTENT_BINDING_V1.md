# Pro-Forma Risk / Intent Binding V1

## Purpose

`ProFormaRiskIntentBindingV1` links an already-calculated post-change risk
evaluation to the exact analytical option and capacity intent reviewed by the
PR-51 explanation envelope.

The package does not generate a new portfolio, recalculate broker values or
execute an order. It only verifies that the supplied pro-forma result belongs
to the same masked account, option, direction and complete intent set.

## Two-stage boundary

### Pro-forma scenario

`ProFormaRiskScenarioV1` retains:

- the masked account;
- requested option ID;
- homogeneous buy or sell direction;
- every exact `CapacityOrderRequestV1`;
- the post-change `RiskPolicyEvaluationV1`;
- the scenario timestamp;
- a deterministic SHA-256 intent fingerprint.

The scenario validates its own fingerprint and rejects duplicate instruments,
duplicate request IDs, mixed directions, account mismatch and timestamp
mismatch.

### Binding result

The binder compares the scenario with the existing
`RiskPreTradeExplanationEnvelopeV1` and its nested exact capacity intent.

It requires:

- a ready base explanation;
- matching masked account context;
- the same requested option;
- the same direction;
- the same instrument set;
- the same complete capacity-request fingerprint;
- the same conservative risk policy;
- a ready and fresh pro-forma risk evaluation.

## Fingerprint contents

The SHA-256 fingerprint is calculated from canonical JSON containing only:

- masked account ID;
- requested option ID;
- direction;
- request ID and stable instrument key;
- currency;
- quantity in lots;
- lot size;
- reference price;
- intended execution window;
- units;
- order notional.

Requests are sorted deterministically. Decimal values use canonical text, so
formatting differences such as `100`, `100.0` and `100.00` do not create false
mismatches.

The fingerprint is not a secret and contains no full account identifier.

## Current versus pro-forma risk

Both risk evaluations remain embedded and separate:

- current-portfolio risk from PR-51;
- post-change pro-forma risk from the scenario.

The result reports status and breach/warning/unknown count deltas. These deltas
are risk-control diagnostics, not a return forecast, profit estimate or promise.

The binding layer does not recompute the pro-forma risk evaluation and reports
`pro_forma_risk_recomputed_by_binding=false`.

## Fail-closed behavior

Any mismatch, stale evidence, future timestamp or unready source produces:

- `status=abstain`;
- `review_ready=false`;
- `risk_change_approval_confirmed=false`;
- the existing no-action option;
- `final_action=wait_for_data`.

A ready result may set `risk_change_approval_confirmed=true` only for the exact
analytical review described by the fingerprint. It is not trade authorization.

## Safety invariants

Every result keeps:

- `option_selected_by_binding=false`;
- `trade_authorized=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

The package adds no FastAPI route, OpenAPI operation, GPT Action, broker SDK
call, order method, transfer or withdrawal capability.

## Tests

Focused tests cover:

- successful exact binding;
- account, option and direction mismatches;
- quantity and instrument substitution;
- blocked, stale and future pro-forma risk;
- risk-policy mismatch;
- blocked base explanation preservation;
- scenario fingerprint tampering;
- result safety-field tampering;
- naïve timestamp rejection.
