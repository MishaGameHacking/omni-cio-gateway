# Risk / Pre-Trade Explanation Envelope V1

## Purpose

`RiskPreTradeExplanationEnvelopeV1` combines already-validated read-only
portfolio-risk and directional pre-trade results into one auditable explanation.

It answers:

- whether the risk and broker-preview data refer to the same masked account;
- whether the conservative risk context is usable and fresh;
- whether capacity evidence matches the analytical intent;
- whether broker preview coverage and exact intent binding are complete;
- which layer first forces `wait_for_data`.

The envelope does not calculate a new recommendation and does not execute an
order.

## Source contracts

The composer retains, without reinterpretation:

- `RiskPolicyEvaluationV1`;
- `CapacityDirectionalPreTradeReviewV1`;
- the nested capacity-intent and purchase/sell preview gates.

Completed source contracts use a typed no-revalidation boundary. The envelope
validates its own mirrors, timestamps, account alignment, layer ordering,
blockers, warnings and final no-action behavior.

## Canonical layers

The result always contains five layers in this order:

1. account context;
2. portfolio risk;
3. capacity intent;
4. broker preview;
5. directional review.

Each layer is `ready`, `warning` or `blocked`. The first blocked layer is
reported as `primary_blocking_layer`.

## Account boundary

The masked account from the risk evaluation must match the masked account from
every broker preview in the directional source gate.

- no preview account: `account_context_unconfirmed`;
- different or multiple account contexts: `account_context_mismatch`;
- exactly one matching masked account: confirmed.

No full account identifier is stored or emitted.

## Freshness

The policy independently limits:

- risk evaluation age;
- directional review age;
- tolerated future-clock skew.

Stale or future-dated evidence forces `abstain` and `wait_for_data`.

## Risk semantics

A blocking or incomplete `RiskPolicyEvaluationV1` blocks the envelope. Warnings
and unknown counts remain visible.

The current risk evaluation is not claimed to be a pro-forma post-change risk
approval. Every result therefore keeps:

- `risk_change_approval_confirmed=false`;
- warning `risk_evaluation_not_pro_forma_bound`.

A later package must create an explicit pro-forma binding before this warning
can be removed.

## Fail-closed behavior

Any account, risk, freshness or directional blocker returns:

- `status=abstain`;
- `review_ready=false`;
- the existing no-action option;
- `final_action=wait_for_data`.

A ready envelope only preserves the analytical option and action from the
source review.

## Safety invariants

Every result keeps:

- `option_selected_by_envelope=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

The package adds no FastAPI route, OpenAPI operation, GPT Action, broker SDK
call, order method, transfer or withdrawal capability.

## Tests

Focused tests cover:

- ready matching sources;
- account mismatch and missing account context;
- blocking risk and non-blocking risk warnings;
- stale and future-dated sources;
- capacity, broker-preview and directional layer attribution;
- naïve timestamps;
- safety-field tampering.
