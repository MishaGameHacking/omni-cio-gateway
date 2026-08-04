# Omni-CIO v9 — Meta-Strategy Selector

Status: **WP9 implementation contract**  
Parent program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`  
Protected production baseline: **Omni-CIO v8.6.1**

## 1. Purpose

WP9 selects an explainable portfolio regime from the exact owner IPS and the exact current WP8 risk state. It does not predict market direction, maximize an expected-return forecast, choose individual securities, size lots, compile orders or authorize broker writes.

Canonical sequence:

`WP2 IPS + exact current portfolio snapshot + WP8 current risk + explicit cost/tax friction evidence → bounded regime comparison → deterministic Meta-Strategy Selection`

The result is an internal read-only input for WP10 Portfolio Optimizer & Capital Scaling.

## 2. Safety boundary

The selector is pure/internal and has no broker SDK, token, order, stop-order, Sandbox or real-execution dependency.

`trading_methods=false` is contract-enforced. WP9 adds no public route, OpenAPI Action, Render/Upstash mutation state or GPT Editor change. Applied GPT remains v8.6.1 until WP15.

Engineering autonomy is not trading authority. A strategy selection cannot prepare or execute a real order.

## 3. Exact binding

Every selection binds:

- exact `portfolio_snapshot_sha256`;
- exact WP2 `PolicyReferenceV1`;
- recomputed WP2 policy fingerprint;
- exact WP8 `assessment_sha256`;
- the WP8 portfolio and policy references.

A policy payload changed under the same id/version fails closed. A WP8 assessment from another portfolio or IPS fails closed.

WP9 accepts only a **current-state** WP8 assessment. A risk assessment that contains hypothetical proposed trades, or whose before/after states differ, is rejected. Strategy selection must not accidentally bless a trade scenario as the current portfolio.

## 4. Bounded regime vocabulary

WP9 compares exactly five regimes:

1. `NO_ACTION` — current posture baseline;
2. `CAPITAL_PRESERVATION` — liquidity and loss avoidance dominate;
3. `DEFENSIVE_BALANCED` — defensive diversified core with quality debt where policy permits;
4. `BALANCED_CORE` — diversified core within moderate risk capacity;
5. `GROWTH_CORE` — diversified core with a bounded active sleeve only when both owner willingness and capacity are high and current risk is policy-compliant.

The model or caller cannot inject a new strategy label, free-form score or expected-return estimate into the selector.

## 5. Strategy components

Every result contains exactly four component directives:

- liquidity reserve;
- quality debt;
- diversified core;
- bounded active ideas.

Each component is `REQUIRED`, `ALLOWED` or `FORBIDDEN` with a machine-readable rationale code.

Owner liquidity reserve remains required for every actionable regime. Quality debt and diversified core are permitted only if compatible instrument classes are available under the IPS. The active sleeve is never required and is allowed only for `GROWTH_CORE` with both risk willingness and risk capacity explicitly `HIGH` and no current hard policy breach.

## 6. Hard policy and risk limits

The regime risk ladder is bounded by the minimum of:

- owner risk willingness;
- owner risk capacity;
- time-horizon capacity;
- the exact WP8 current risk state.

A more aggressive regime above that bound is marked infeasible before comparison. Hard permanent-loss, market/drawdown, liquidity or credit breaches sharply reduce the permitted regime set. Other hard breaches also reduce the set.

The selector never averages a hard breach away with objective fit, liquidity fit, lower costs or any favorable metric.

Current hard breaches do not automatically make remediation impossible: `NO_ACTION` becomes infeasible while a sufficiently defensive, policy-bounded regime may remain available for WP10 to construct a corrective portfolio. If required evidence is missing, selection still fails closed.

## 7. No regime chasing

WP9 has no macro bull/bear classifier and no expected-return input. It does not choose `GROWTH_CORE` because prices recently rose, nor `CAPITAL_PRESERVATION` because headlines are negative.

The objective-fit anchor comes from the owner IPS objective, then is capped by risk and horizon. Current WP8 severity can only restrict risk-taking; it cannot create an unsupported return forecast.

## 8. Deterministic comparison

Each regime records bounded ordinal grades for:

- risk fit;
- objective fit;
- liquidity fit;
- explicit transition/tax friction.

Ordering is deterministic and safety-first:

1. feasible before infeasible;
2. higher risk fit;
3. higher objective fit;
4. higher liquidity fit;
5. lower explicit friction;
6. deterministic `NO_ACTION` tie preference;
7. stable regime identifier.

The grades are not a return forecast and are not a weighted alpha score.

`NO_ACTION` is always present. It has zero transition friction and is a real baseline, not a dummy candidate. If current WP8 state contains a hard policy breach, `NO_ACTION` is marked infeasible so a breach cannot be preserved merely because doing nothing is cheap.

## 9. Costs and taxes

Every structurally feasible actionable regime requires explicit `StrategyFrictionEvidenceV1` containing:

- transition-cost weight;
- tax-cost weight;
- evidence timestamp;
- one or more provenance SHA-256 values.

Evidence is freshness-checked and future timestamps beyond tolerance fail closed. Missing friction evidence blocks decision readiness rather than assuming zero costs or zero tax.

An IPS with unknown tax context also blocks decision readiness.

## 10. Data quality and readiness

Global blockers include:

- IPS not ready;
- policy binding mismatch;
- WP8 binding mismatch;
- WP8 not decision-ready;
- hypothetical risk assessment supplied as current state;
- unknown tax context;
- missing/stale/future friction evidence;
- no feasible regime.

If any global blocker exists, the selection returns `decision_ready=false`, `optimizer_eligible=false` and fails closed to `NO_ACTION` as a non-actionable placeholder.

This is not a recommendation to keep the portfolio unchanged; it means the engine does not have sufficient verified state to pass a strategy to WP10.

## 11. Review and cancellation conditions

Every immutable result carries the full review set:

- policy changed → cancel;
- portfolio changed → review;
- risk state changed → review;
- new hard breach → cancel;
- friction evidence stale → review;
- tax context changed → review.

These conditions become downstream invalidation inputs. WP11/WP12 may add stricter plan/execution drift checks but cannot weaken them.

## 12. Remediation semantics

`remediation_required=true` means current WP8 after-state is not policy-compliant. It is not execution authority.

If the data is decision-ready and a defensive feasible regime exists, WP9 may select it so WP10 can attempt a compliant corrective allocation. WP10 must still prove the actual target weights, lots, cash, fees and post-optimization risk.

## 13. Determinism and fingerprint

Canonical ordering is applied to:

- components by kind;
- comparisons by the deterministic comparison key;
- blockers;
- review conditions;
- friction evidence source hashes.

`selection_sha256` binds the exact timestamp, portfolio, IPS, WP8 assessment, selected regime, component directives, complete comparison table, blockers, review conditions and readiness state.

Equivalent source ordering therefore yields the same fingerprint.

## 14. Threat model

WP9 explicitly rejects or neutralizes:

- LLM/free-text strategy injection;
- expected-return or macro-regime score injection;
- policy id/version reuse with mutated payload;
- risk state from another portfolio/IPS;
- hypothetical after-trade risk passed off as current state;
- zero-cost/zero-tax assumptions when evidence is absent;
- stale or future-dated friction evidence;
- aggressive strategy selection above willingness/capacity/horizon/WP8 risk capacity;
- active sleeve without high owner willingness + high owner capacity;
- broker mutation dependencies in the strategy runtime.

## 15. Exit gate

WP9 is complete only when:

1. versioned strategy/friction/component/comparison/review/selection contracts exist;
2. exact portfolio + WP2 + WP8 binding fails closed;
3. exactly five bounded regimes are compared, including `NO_ACTION`;
4. risk willingness/capacity, horizon and WP8 risk cap the regime set before ranking;
5. hard breaches cannot be averaged away;
6. diversified core, liquidity, quality debt and bounded active component rules are deterministic;
7. actionable regimes require explicit fresh cost/tax evidence;
8. unsupported macro prediction and expected-return optimization are absent;
9. selection ordering and SHA-256 are deterministic/source-order invariant;
10. review/cancellation conditions are complete;
11. strategy runtime is pure/read-only and repository-guarded;
12. tests, Ruff, mypy and exact-head Regression Shield are green;
13. unresolved review threads are zero;
14. PR is squash-merged and epic/status evidence is updated.
