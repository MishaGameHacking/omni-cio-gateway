# Technical Indicator Assessment V1

## Purpose

`PriceSeriesEvidenceV1` and `assess_technical_indicators` provide a reproducible offline analysis of OHLCV data. The module treats technical indicators as calculations and observations, never as proof of a future price or as an automatic trading instruction.

## Evidence contract

Each bar contains:

- timezone-aware opening timestamp;
- open, high, low and close;
- optional volume.

The contract requires:

- positive prices;
- `high >= open/close`;
- `low <= open/close`;
- chronological ordering;
- unique timestamps;
- trusted provenance whose retrieval time does not precede the latest bar.

The series also declares interval, corporate-action adjustment status, pagination/truncation status and session completeness.

## Policy

`TechnicalIndicatorPolicyV1` explicitly versions all parameters:

- minimum history;
- last-bar freshness;
- future tolerance;
- corporate-action adjustment requirement;
- maximum missing-volume fraction;
- short and long SMA periods;
- RSI period and conventional zones;
- MACD fast, slow and signal periods;
- ATR period;
- volatility annualization factor;
- trusted source authorities.

The policy rejects internally inconsistent lookbacks.

## Calculations

V1 uses Decimal arithmetic for:

- period return;
- peak and trough closes;
- maximum close-to-close drawdown;
- close-to-close realized volatility;
- annualized volatility;
- short and long simple moving averages;
- Wilder-style RSI;
- EMA-based MACD, signal and histogram;
- trailing true-range ATR;
- average and latest volume when available.

The result also classifies the current values as:

- above, below or mixed relative to both moving averages;
- oversold-zone, neutral or overbought-zone RSI;
- positive, negative or neutral MACD histogram.

These labels describe the calculation only.

## Readiness blockers

The assessment is rejected when any of the following applies:

- current market research is not ready;
- instrument identity or currency does not match;
- price source is untrusted;
- history is insufficient;
- latest bar is stale or materially future-dated;
- adjusted prices are required but unconfirmed;
- the series is truncated;
- session data is incomplete;
- missing volume exceeds policy.

Metrics may still be returned for a blocked series when enough bars exist, but `analysis_ready=false`.

## Warnings

Warnings include:

- unadjusted prices when explicitly allowed;
- missing or zero volume;
- conventional RSI extreme zones;
- close below the long moving average;
- negative MACD histogram;
- price-only evidence;
- requirement for alternative explanations;
- technical signals are not forecasts.

## Method limitations

V1 does not:

- identify chart patterns with computer vision;
- infer causality;
- incorporate news or financial statements;
- guarantee indicator efficacy;
- optimize parameters on historical outcomes;
- perform backtesting;
- produce target prices;
- produce buy/sell recommendations.

Every result retains:

- `facts_only=true`;
- `no_price_forecast=true`;
- `no_investment_recommendation=true`;
- `technical_analysis_not_sufficient_alone=true`;
- `execution_ready=false`;
- `trading_methods=false`.

## Compatibility and security

The module adds no network fetcher, broker call, order method, transfer/withdrawal method, FastAPI route, OpenAPI operation or GPT Action. Gateway version remains `3.9.1`; Render entrypoint remains `app:app`.

## Tests

Focused tests cover rising and falling series, exact SMA/RSI/ATR/volume calculations, drawdown, insufficient history, stale/future/untrusted evidence, adjustment policy, volume coverage, market-readiness propagation, malformed OHLC, ordering, provenance, policy validation, metric tampering and immutable safety flags.

## Rollback

Revert the PR merge commit. Existing market, equity, fund, bond, paper, public API and broker layers remain independent.
