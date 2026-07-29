# Equity Fundamental Assessment V1

## Purpose

PR-37 adds a strict offline equity-fundamental assessment that composes with
the existing `MarketResearchBundleV1` readiness gate. It calculates only
reproducible facts and ratios from typed evidence and does not create a price
forecast, recommendation or execution capability.

Every output preserves:

- `facts_only=true`;
- `no_price_forecast=true`;
- `no_investment_recommendation=true`;
- `execution_ready=false`;
- `trading_methods=false`.

## Evidence boundary

`EquityFundamentalEvidenceV1` binds one share instrument and one explicit
currency to:

- accounting standard and reporting-period kind;
- period start and end;
- publication timestamp and report source;
- revenue;
- optional operating profit and EBITDA;
- net income;
- operating cash flow;
- non-negative capital expenditure;
- free cash flow;
- total debt and cash;
- total equity;
- optional dividends paid;
- current market capitalization with a separate source and timestamp;
- optional shares outstanding.

Report provenance and market-cap provenance are intentionally separate. A
financial statement cannot silently serve as the source for a current market
capitalization.

The evidence contract requires:

`free cash flow = operating cash flow - capital expenditure`

It also rejects a source retrieval timestamp earlier than the fact timestamp.
Forecast values are prohibited in V1.

## Market composition

The assessment first runs the existing `assess_market_research_bundle` gate.
The bundle must identify the same stable instrument key, use the same currency,
represent a share, and provide ready reference, quote, liquidity and event-check
evidence.

A blocked market bundle does not hide valid arithmetic. Ratios may still be
returned as facts, but `analysis_ready=false` and
`market_research_not_ready` remain explicit.

## Provenance and freshness

The policy separately controls:

- maximum report age in days;
- maximum market-cap age in seconds;
- future-timestamp tolerance;
- accepted source-authority classes.

The conservative default accepts primary, official and regulated sources. A
secondary or untrusted report or capitalization source blocks readiness.

The report publication timestamp, report period end and market-cap timestamp
are checked independently. Future or stale evidence is not silently accepted.

## Exact calculations

All money and ratios use `Decimal`. The assessment calculates:

- net debt;
- net margin;
- optional operating margin;
- optional EBITDA margin;
- free-cash-flow margin;
- optional net debt / EBITDA;
- earnings yield;
- free-cash-flow yield;
- optional price / earnings;
- optional price / book;
- optional dividend payout ratio.

Core formulas include:

- `net debt = total debt - cash and equivalents`;
- `margin = metric / revenue` when revenue is non-zero;
- `earnings yield = net income / market capitalization`;
- `FCF yield = free cash flow / market capitalization`;
- `P/E = market capitalization / positive net income`;
- `P/B = market capitalization / positive equity`;
- `payout = dividends paid / positive net income`.

The output contract independently recomputes net debt and both mandatory yield
ratios.

## Unavailable metrics

A ratio is not fabricated when its denominator is zero, negative or absent.
Examples:

- no positive net income: no positive P/E or payout ratio;
- no positive equity: no P/B;
- no positive EBITDA: no net-debt/EBITDA;
- zero revenue: revenue-based margins are unavailable;
- omitted optional operating profit, EBITDA or dividends: dependent metrics are
  listed in `unavailable_metrics`.

Negative income, cash flow or equity remains analyzable evidence and appears as
a warning. It is not converted into a positive multiple and is not represented
as a forecast.

## Warnings versus blockers

Blockers concern evidence trust and usability:

- market research not ready;
- missing or non-share reference;
- instrument or currency mismatch;
- untrusted report or market-cap source;
- future or stale report;
- future report period;
- future or stale market capitalization.

Warnings describe facts or limitations that do not by themselves invalidate
the evidence:

- negative income or cash flow;
- negative equity;
- non-positive EBITDA or operating profit;
- dividends above positive income;
- net cash position;
- missing optional values;
- non-standard accounting basis;
- multiples are not forecasts;
- no cross-currency aggregation.

V1 deliberately contains no personalized leverage, valuation or profitability
threshold. Those belong to a separately reviewed policy/decision layer.

## Scope not included

PR-37 does not add:

- a network financial-statement fetcher;
- issuer-data normalization across accounting standards;
- forecast consensus;
- target prices;
- valuation recommendations;
- fund analysis;
- public FastAPI routes or GPT Actions;
- broker SDK calls;
- execution or confirmation logic.

Fund-specific composition, fees, tracking error and duplication analysis remain
a separate PR.

## Validation

Focused tests cover:

- exact positive-case metrics;
- negative income, cash flow, EBITDA and equity;
- unavailable optional metrics without guessing;
- share identity, currency and instrument-type gates;
- untrusted and stale report/capitalization sources;
- future report, period and market-cap timestamps;
- propagation of market-readiness failure;
- custom freshness policy;
- free-cash-flow reconciliation;
- source-time provenance;
- tampered metric reconciliation;
- all read-only and non-recommendation safety flags.

Regression Shield must pass repository policy, compile, Ruff, formatting,
mypy, stable `app:app`, read-only GPT Actions release contract, full pytest and
coverage, dependency audit, Bandit and secret scan before merge.

## Rollback

Revert the merge commit. Existing market readiness, bond analysis, public API,
Render deployment and broker permissions remain unchanged.
