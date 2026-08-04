# WP12 Safe Plan Execution — Data Contract

## Purpose

This document defines the versioned data boundary used by WP12. The contract preserves exact WP11 plan identity while adding only the execution state required to safely stage, submit, reconcile and audit the already-approved plan.

## Source objects

WP12 consumes, but does not reinterpret, the following upstream identities:

- WP11 `PortfolioPlanV1.plan_sha256`;
- WP11 exact policy reference;
- current WP8 risk assessment SHA;
- WP9 strategy selection SHA;
- WP10 optimizer SHA;
- target WP8 risk assessment SHA;
- exact WP11 BUY/SELL legs and market baselines.

A plan with `NO_ACTION`, `approval_required=false`, a stale canonical SHA, or no actionable legs cannot create a real execution session.

## `PlanExecutionSessionV1`

A session is a revisioned durable state object with deterministic identity derived from the exact plan SHA.

Required identity/state fields include:

- `schema_version=1.0`;
- `execution_id`;
- `plan_sha256`;
- initial/current WP11 review fingerprints and timestamps;
- exact instrument/stage state set;
- owner-approved boolean, timestamp and approval-evidence SHA;
- confirmed broker cash delta and separate estimated SELL tax allowance;
- halt reason when halted;
- monotonically increasing `revision`;
- hard safety literals: `real_money=true`, autonomous/margin/short/withdrawal/transfer all false.

A session cannot be `COMPLETED` unless every stage is portfolio-reconciled as filled.

## Instrument binding

`PlanExecutionInstrumentBindingV1` binds a plan stable key to the broker execution identity:

- instrument UID;
- ticker;
- optional ISIN;
- instrument type;
- lot size;
- source fingerprint and timestamp.

The binding is refreshed and compared before execution. Current WP12 production authority remains restricted by the accepted v8.6.1 real policy; a contract value being representable does not make that instrument type executable.

## Execution evidence

Each actionable stage requires `PlanExecutionLegEvidenceV1`, composed of:

1. a WP11-compatible `PlanMarketObservationV1`; and
2. a `PlanExecutionQuoteV1`.

The observation and quote must agree on stable key, timestamp, spread, turnover and top-of-book depth. Quote currency is RUB, bid cannot exceed ask, and the declared spread must reconcile to bid/ask.

The quote exposes the deterministic executable LIMIT reference: best ask for BUY and best bid for SELL. The service separately validates exact minimum price increment and bounded drift from the immutable plan baseline.

## Current-state contract

`PlanExecutionCurrentStateV1` is trusted read-only evidence of the current state used for progress and risk reconciliation. It contains:

- observation timestamp;
- portfolio snapshot SHA;
- policy reference;
- RUB cash;
- canonical stable-key/lots positions;
- current risk assessment SHA and decision/policy readiness;
- strategy, optimizer and target-risk SHA bindings;
- evidence source fingerprints.

No broker token, full account id or arbitrary raw payload is part of this contract.

## Stage model

Each immutable leg is split into one or more `PlanExecutionStageV1` rows. Stage identity is deterministic from plan SHA, leg sequence, stage index and stable key.

A stage records:

- plan leg sequence and stable key;
- BUY/SELL side;
- stage index/count;
- exact planned lots;
- broker-terminal and portfolio-reconciled lot counts;
- ordered attempts;
- earliest Moscow execution date and last submission date;
- state.

Stage/attempt indices must be contiguous. Broker-terminal lots cannot exceed planned lots. Portfolio-reconciled lots cannot exceed broker-terminal lots.

## Attempt model

`PlanExecutionAttemptV1` stores one v8.6.1 proposal lifecycle for a stage remainder:

- attempt index and quantity;
- v8.6.1 proposal id and broker request UUID;
- exact LIMIT price;
- prepared/submitted/reconciled timestamps;
- broker status and executed lots;
- executed amount and commission;
- broker-response fingerprint;
- replay marker or failure code.

An attempt in an unknown state is never converted into a fresh submit. It remains bound to the same proposal/request id for reconciliation.

## Broker snapshot

`PlanExecutionBrokerSnapshotV1` normalizes only evidence required for deterministic reconciliation:

- proposal id and request id;
- broker execution status;
- requested/executed lots;
- total order amount;
- executed commission;
- optional executed price;
- response SHA.

Executed lots may not exceed requested lots. A broker `FILL` status requires all requested lots executed.

## Cash semantics

Confirmed cash movement is based on broker-terminal order evidence:

- BUY decreases `confirmed_cash_delta_rub` by broker order amount;
- SELL increases it by broker order amount;
- estimated SELL tax remains a separate allowance rather than being double-counted into broker proceeds.

Read-only current cash must remain within the deterministic expected range after confirmed broker progress plus the bounded tax allowance and configured RUB tolerance.

## Revision and atomicity

Every state mutation increments `revision` by exactly one. Journal persistence uses compare-and-swap on `(execution_id, expected_revision)`. Concurrent or stale writers fail closed rather than overwriting newer execution state.

Production requires a durable implementation. The in-memory journal is test-only and deliberately reports `durable=false`.

## Data minimization and redaction

WP12 durable session state must not contain:

- `TINVEST_TOKEN`, `TINVEST_TRADING_TOKEN` or gateway secrets;
- Authorization headers;
- full broker account ids;
- arbitrary broker raw responses;
- unrelated portfolio holdings or personal identity data.

Broker response content is normalized/fingerprinted through the existing real-trading reconciliation boundary. Existing v8.6.1 masking and sanitization requirements remain in force.

## Compatibility and migration

Schema v1 is additive to the existing real-trading journal and does not reinterpret or destructively migrate v8.6.1 proposal records. Plan session state and single-order proposal state remain separate durable objects connected only by explicit proposal/request ids.

Any future schema migration must preserve unresolved/ambiguous request ids and broker reconciliation capability across rollback. Destructive cleanup is forbidden until broker state is reconciled.
