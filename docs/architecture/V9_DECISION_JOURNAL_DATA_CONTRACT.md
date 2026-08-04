# WP14 — Decision Journal Data Contract

## Canonical record classes

### DecisionJournalRecordV1

A frozen decision-time record. It binds:

- policy reference and owner objective;
- exact portfolio snapshot hash;
- exact decision-set and evidence hashes;
- exact risk assessment hash;
- optional strategy/optimizer/plan/execution identities;
- selected action;
- starting portfolio value;
- optional baseline/target concentration and cash weights;
- optional expected execution cost;
- decision-time research coverage counts and data-completeness flag.

It deliberately stores hashes/quality metrics rather than raw broker/account payloads.

### DecisionOutcomeRecordV1

A later frozen outcome record. It binds:

- original decision ID;
- observation horizon;
- ending portfolio value and net external flow;
- optional `NO_ACTION` ending value + source SHA;
- optional policy-benchmark ending value + source SHA;
- optional ending concentration/cash/execution metrics;
- observed research coverage and data-completeness ratio;
- source SHA set.

Benchmark value/evidence pairs are all-or-nothing.

### DecisionEvaluationRecordV1

A deterministic derived record binding exact decision/outcome record hashes. It contains:

- realized period result;
- explicit benchmark availability;
- optional benchmark period results and excess values;
- data completeness and research coverage;
- concentration/cash/execution-quality deltas;
- safety literals proving no hindsight rewrite, counterfactual fabrication or production-rule modification.

## Canonical arithmetic

Realized period result:

`end_value - start_value - net_external_flow`

When evidence-bound `NO_ACTION` exists:

`no_action_result = no_action_end_value - start_value - net_external_flow`

`excess_vs_no_action = realized_result - no_action_result`

Policy benchmark uses the same external-flow basis.

Concentration reduction in basis points:

`(baseline_top1_weight - ending_top1_weight) * 10000`

Cash-weight delta in basis points:

`(ending_cash_weight - baseline_cash_weight) * 10000`

Execution-cost variance:

`actual_execution_cost - expected_execution_cost`

Research coverage:

- if decision expected zero research items, coverage is `1`;
- otherwise `min(covered_at_outcome, expected_at_decision) / expected_at_decision`.

Evaluation completeness is `COMPLETE` only when the decision-time data was marked complete and outcome data-completeness ratio equals `1`. Benchmark unavailability by itself does not fabricate incompleteness; it remains a separate availability state.

## Canonical hashing

Every record uses sorted-key compact UTF-8 JSON and SHA-256. Self-hash fields are excluded from their own digest calculation. Immutable IDs exclude both the ID and digest fields, then the final digest includes the computed ID.

Evidence/source hash collections are sorted and deduplicated before validation.

## Journal semantics

The journal is append-only:

- exact duplicate append: idempotent success;
- same identity + different payload: conflict;
- outcome before decision: conflict;
- evaluation without exact decision/outcome bindings: conflict;
- no update/delete operation exists.

Durable authenticated metadata tracks revision plus decision/outcome/evaluation counts. A successful new append advances revision by exactly one and increments exactly one counter.

## Offline replay contract

A replay case contains only:

- hashes of the immutable decision/outcome/evaluation records;
- expected decision action;
- expected completeness state;
- optional boolean label for evidence-bound `NO_ACTION` outperformance.

Replay datasets are sorted deterministically by case ID. `SANITIZED_PRODUCTION` source requires explicit sanitization confirmation. Contracts assert that account identifiers, raw private payloads, secrets and production-write capability are absent.

## Regression gate

Baseline and candidate predictions must cover the exact same case IDs once each. A match requires exact expected action and expected abstention behavior. A candidate has a regression when the baseline matched a case and the candidate no longer does.

A candidate becomes `ready_for_review` only when:

- there are zero regression cases; and
- candidate match count is at least the baseline match count.

This result never deploys or rewrites production configuration automatically.
