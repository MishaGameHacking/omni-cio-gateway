# Final Decision-Review Response V1

## Purpose

`FinalDecisionReviewResponseV1` is the compact, user-safe boundary after the
PR-52 pro-forma risk/intention binding.

It exposes enough information to explain whether an analytical change is ready
for human review or must wait for data, without exposing the deep internal gate
objects, a full account identifier, broker secrets or any execution surface.

## Response contents

The response contains:

- generated timestamp;
- `ready` or `abstain` status;
- disposition: `review_ready` or `wait_for_data`;
- masked account only;
- requested and final option IDs;
- final analytical action;
- homogeneous buy/sell direction;
- exact non-secret intent fingerprint;
- compact intent lines with lots, lot size, reference price, units and notional;
- separate current and pro-forma risk summaries;
- risk breach/warning/unknown deltas;
- source blockers and warnings;
- sanitized provenance containing provider, operation and retrieval timestamp.

`source_id` is deliberately omitted from the user-safe provenance structure.
The response never embeds the source binding, risk contracts, capacity gates or
broker previews.

## No recalculation

The adapter copies already-validated values from
`ProFormaRiskIntentBindingV1`. It does not recalculate:

- broker prices;
- commissions;
- affordability;
- sell proceeds;
- accrued interest;
- capacity;
- current risk;
- pro-forma risk.

The response therefore keeps `source_values_recomputed=false` and warns that
risk deltas are controls, not forecasts of return or profit.

## Fail-closed semantics

A binding with blockers produces:

- `status=abstain`;
- `disposition=wait_for_data`;
- `review_ready=false`;
- the first source blocker as `primary_blocker`;
- the source no-action option;
- `final_action=wait_for_data`;
- `risk_change_approval_confirmed=false`.

The adapter does not remove, reorder or reinterpret source blockers.

## Shadow validation

`FinalDecisionReviewShadowValidationV1` retains the completed source binding
only inside the internal shadow result and verifies response parity for:

- status;
- readiness and abstain state;
- requested/final option;
- final action;
- direction;
- masked account;
- intent fingerprint;
- risk-change approval;
- safety flags.

Any post-adapter substitution produces `status=mismatch` and an explicit list
of mismatched fields. It never upgrades the response.

## Safety invariants

The response always reports:

- `full_account_identifier_present=false`;
- `source_contracts_exposed=false`;
- `public_action_exposed=false`;
- `source_values_recomputed=false`;
- `option_selected_by_adapter=false`;
- `trade_authorized=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

The shadow result additionally reports:

- `shadow_only=true`;
- `route_added=false`;
- all execution flags false.

This package adds no FastAPI route, OpenAPI operation, GPT Action, broker SDK
call, order, stop-order, transfer or withdrawal capability.

## Tests

Focused tests cover:

- ready user-safe response generation;
- blocked `wait_for_data` preservation;
- complete shadow parity;
- option substitution detection;
- provenance deduplication and `source_id` removal;
- safety and risk-arithmetic tamper rejection;
- naïve timestamp rejection.
