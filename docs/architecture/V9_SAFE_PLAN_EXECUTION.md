# WP12 Safe Plan Execution Engine

## Status

WP12 extends the owner-approved v8.6.1 real BUY/SELL lifecycle so an exact, valid WP11 immutable `PORTFOLIO_PLAN` can be executed as a sequence of tightly controlled LIMIT stages. It does not replace the v8.6.1 broker stack and does not broaden the allowed real-money surface.

Applied Custom GPT remains v8.6.1 until WP15.

## Design objective

One owner approval may authorize the disclosed immutable portfolio plan, but that approval does not waive server controls. Every stage still passes fresh plan, portfolio, risk, instrument, market, liquidity, price-step, own-funds/own-position and existing real-trading hard-cap checks immediately before preparation and submit.

The execution engine is a deterministic orchestrator over the existing `RealTradingServiceV1` proposal/confirmation/idempotency/reconciliation primitive.

## Core components

- `omni_cio/contracts/v1/plan_execution.py` — versioned plan-execution/session/stage/attempt/reconciliation contracts.
- `omni_cio/plan_execution/service_core_v1.py` — fail-closed deterministic state machine.
- `omni_cio/plan_execution/service_v1.py` — audited public facade with horizon, tranche-order and terminal broker reconciliation hardening.
- `omni_cio/plan_execution/adapter_v1.py` — thin adapter to the accepted v8.6.1 single-order service.
- `omni_cio/plan_execution/journal_v1.py` — revisioned compare-and-swap journal protocol and in-memory test implementation.
- `omni_cio/plan_execution/upstash_journal_v1.py` — durable Upstash implementation for production plan state.
- `omni_cio/plan_execution/broker_reconciliation_v1.py` — normalized broker execution-state evidence.

## State machine

A plan session is deterministically keyed by the exact WP11 plan SHA. The primary progression is:

`PREPARED → ACTIVE → stage PREPARED → AWAITING_BROKER_RECONCILIATION → BROKER_TERMINAL → portfolio reconciliation → next stage → COMPLETED`.

Any material unsafe condition transitions the whole session to `HALTED`. An ambiguous possible-submit is special: the session remains halted and may only transition into broker reconciliation for the same request id. It must never create a replacement submit.

## Exact WP11 binding

Preparation requires:

1. canonical Pydantic re-validation of the complete plan;
2. recomputation of `plan_sha256`;
3. actionable BUY/SELL legs only (`NO_ACTION` creates no real execution session);
4. exact starting lots and cash reconciliation;
5. current risk decision-ready and policy-compliant state;
6. trusted instrument identity/lot-size binding;
7. a fresh valid WP11 review built from current market observations;
8. proof that the currently configured real-money hard cap can fit every required slice inside the immutable plan validity horizon.

Owner approval is accepted only for the exact `owner_approval_phrase` embedded in the same immutable plan. The approval evidence is hashed into the session. Repeated approval returns an idempotent replay result and never submits an order.

The WP11 validity horizon is derived from WP10 `required_execution_days`. The short `validity_seconds` window remains the final-day approval/execution tail. WP12 may make a leg smaller because an existing hard cap is tighter, but it must fail preparation if that would require more calendar stages than the still-valid immutable plan authorizes. WP12 never auto-extends the plan and never auto-increases the cap.

## Per-stage revalidation

Immediately before stage preparation and again before submit, WP12 rechecks:

- current portfolio progress and cash;
- policy/risk/strategy/optimizer/target-risk binding through current-state evidence;
- instrument stable identity, UID, ticker, ISIN and lot size;
- trusted quote freshness and future-timestamp tolerance;
- LIMIT price and exact minimum price increment;
- spread, turnover and top-of-book depth against the immutable baseline;
- plan drift rules through WP11 review semantics;
- existing v8.6.1 broker `GetMaxLots` own-funds/own-position preflight;
- existing per-order and atomic daily RUB hard caps;
- repeated v8.6.1 preflight immediately before `PostOrder`.

A price change between stage preparation and submit resets the stage for a fresh proposal rather than silently changing the approved order.

## Staged LIMIT execution

The immutable optimizer leg is split deterministically when WP10 requires several execution days. A tighter existing v8.6.1 per-order hard cap may make individual slices smaller only when the resulting stage count still fits inside the same immutable plan horizon.

Stages are scheduled by tranche first and exact leg sequence second. For a two-leg/two-day plan the deterministic order is `leg1/stage1 → leg2/stage1 → leg1/stage2 → leg2/stage2`. This preserves the disclosed leg order inside each tranche while keeping the portfolio rebalance synchronized across the approved execution horizon.

A given immutable instrument/leg may submit at most one staged slice per Moscow calendar day. Different legs may proceed sequentially on the same day only after the prior leg is broker-terminal and independently reconciled, and the existing atomic daily RUB cap remains authoritative. Stage quantity is never increased beyond the exact immutable leg.

Only `LIMIT / CURRENCY / DAY` orders are used. The accepted v8.6.1 surface remains share/ETF, RUB, own-funds BUY and own-position SELL. A future extension to another instrument type requires a separately reviewed real-money safety change; the existence of a WP11 plan is not sufficient.

## Partial fills and broker reconciliation

After any submit, no later stage can proceed until the exact request id is reconciled with the broker. `NEW` and `PARTIALLY_FILLED` remain active and are not resubmitted. Terminal broker evidence records executed lots, amount, commission and response fingerprint.

Read-only portfolio/cash reconciliation is then required before the engine advances. The engine derives expected lots from broker-confirmed progress, not from the requested quantity. SELL estimated-tax allowance is tracked separately so cash reconciliation does not falsely demand exact tax timing.

A partial terminal fill returns the same stage to `PENDING` with only the broker-confirmed remainder, and its earliest next attempt is the following Moscow day. It cannot be converted into a same-day replacement order.

## Replay and ambiguity

The deterministic execution id, revisioned journal, v8.6.1 proposal UUID/idempotency and broker request-id reconciliation form one replay boundary.

- repeated plan preparation returns the same exact session when payload identity matches;
- repeated owner approval does not submit;
- an already-submitted underlying proposal is recorded as replay without a second submit;
- `submitting` / `unknown` or an ambiguous transport result halts remaining legs;
- recovery from ambiguity is reconciliation-only for the original request id;
- plan expiry never suppresses reconciliation of a request that may already have reached the broker.

## Durable state and rollback

Production execution requires a durable plan-execution journal. Upstash is the selected zero-cost durable backend, consistent with the existing real-trading journal. Compare-and-swap revisions prevent concurrent session advancement.

`REAL_TRADING_ENABLED=false` remains the master real-money rollback. WP12 must not make plan execution available when the underlying real-trading contour is disabled or not production-ready.

## Explicit prohibitions

WP12 does not add:

- transfer or withdrawal;
- margin or uncovered short;
- MARKET/BESTPRICE;
- futures/options/currency execution;
- stop orders;
- ReplaceOrder or asynchronous submit;
- autonomous recurring real-money execution;
- automatic cap increases;
- automatic extension/reissue of an approved plan;
- a second broker client or trading token path;
- GPT Editor changes before WP15.

## Exit gate

WP12 is complete only after architecture/threat/data contracts, boundary guards, mypy scope, fake-client acceptance coverage for replay/ambiguity/partial fills/halt/reconciliation/staging/horizon, security checks, exact-head Regression Shield, zero unresolved review threads and squash merge. Any minimal-real acceptance remains a separate explicit owner-controlled release step before increasing real caps.
