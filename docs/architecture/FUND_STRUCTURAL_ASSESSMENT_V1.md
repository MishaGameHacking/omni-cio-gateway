# Fund Structural Assessment V1

## Purpose

`FundStructuralEvidenceV1` and `assess_fund_structure` provide a strict offline assessment of an exchange-traded fund's disclosed structure. The module composes with `MarketResearchBundleV1` and does not fetch data, forecast price, recommend a trade or expose a public Action.

## Scope

V1 assesses:

- point-in-time holdings;
- top-1, top-5 and top-10 concentration;
- Herfindahl concentration and effective holding count;
- direct overlap with instrument keys already present in a portfolio;
- derivative, fund-of-funds and cash/currency exposure;
- underlying currency concentration;
- total expense ratio;
- tracking difference and tracking error when supplied;
- existing quote/liquidity readiness, spread and turnover;
- replication method and management-company identity.

## Evidence contract

The evidence separates three fact families:

1. holdings structure and its source/time;
2. fee disclosure and its source/time;
3. optional tracking statistics and their source/time.

Tracking evidence is accepted only as a complete set: timestamp, source, tracking difference and tracking error. A partial set is rejected by the contract.

All holdings weights must sum exactly to `1`. All underlying currency exposure weights must also sum exactly to `1`. Decimal arithmetic is used throughout.

A source retrieval timestamp cannot precede the fact's `as_of` timestamp. Timestamps must be timezone-aware.

## Market composition

The assessor calls the existing `assess_market_research_bundle` function. A stale quote, missing liquidity, untrusted market source or inconsistent fund reference therefore blocks structural readiness.

The reference must:

- have `instrument_type=etf`;
- use the same stable instrument key as the evidence;
- use the same trading currency as the evidence.

The trading currency is not treated as a substitute for underlying asset currency exposure.

## Exact metrics

V1 computes:

- `top_1_weight`;
- `top_5_weight`;
- `top_10_weight`;
- `herfindahl_index = sum(weight²)`;
- `effective_holding_count = 1 / herfindahl_index`;
- direct overlap weight and overlapping stable keys;
- derivative exposure weight;
- fund-of-funds exposure weight;
- cash/currency weight;
- dominant underlying currency and its weight;
- spread and turnover from the market bundle when present.

Missing tracking, spread or turnover values are explicit in `unavailable_metrics`.

## Blocker boundary

Readiness blockers are limited to evidence usability and trust:

- market research is not ready;
- fund reference is absent;
- reference is not an ETF/fund;
- instrument identity mismatch;
- trading currency mismatch;
- untrusted evidence source;
- future or stale structure disclosure;
- future or stale fee disclosure;
- future or stale tracking statistics.

A blocked result still contains deterministic structural calculations, but `analysis_ready=false`.

## Warning boundary

The following are warnings, not forecasts or automatic trade blockers:

- high single-holding concentration;
- high top-ten concentration;
- high expense ratio;
- high tracking error;
- large absolute tracking difference;
- missing tracking statistics for an index fund;
- direct overlap with existing positions;
- derivative exposure;
- fund-of-funds exposure;
- dominant single-currency exposure;
- synthetic replication;
- management-company risk not independently scored.

Thresholds are explicit in `FundStructuralPolicyV1`. They are generic analytical defaults, not a personalized investment policy.

## Point-in-time limitation

A holdings disclosure is a snapshot. It does not prove future composition, future tracking quality, future liquidity or future management behavior. Every assessment therefore retains:

- `facts_only=true`;
- `no_price_forecast=true`;
- `no_investment_recommendation=true`;
- `point_in_time_structure=true`;
- `execution_ready=false`;
- `trading_methods=false`.

## Security and compatibility

V1 adds no:

- network fetcher;
- broker call;
- order method;
- transfer or withdrawal method;
- FastAPI route;
- OpenAPI operation;
- GPT Action;
- Render configuration change.

Gateway version remains `3.9.1` and the stable entrypoint remains `app:app`.

## Tests

Focused tests cover:

- exact concentration and HHI arithmetic;
- direct portfolio overlap;
- tracking-statistics completeness;
- active-fund behavior;
- high-cost and synthetic warnings;
- stale and untrusted evidence;
- identity, currency and type mismatch;
- propagation of market-readiness failures;
- exact weight reconciliation;
- future timestamps;
- metric tampering;
- immutable read-only flags.

## Rollback

Revert the PR merge commit. Existing market, equity, bond, paper-trading, public API and broker layers remain independent.
