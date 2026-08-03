# Omni-CIO v9 — Deterministic Candidate Funnel

Status: **WP4 implementation contract**  
Parent program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`  
Protected production baseline: **Omni-CIO v8.6.1**

## 1. Purpose

WP4 converts a verified portfolio gap into a bounded, reproducible list of candidates for WP5 deep research.

The funnel is not an investment recommendation and is not an execution plan. It is a deterministic comparison layer that deliberately prevents “first found ticker” behavior.

Canonical sequence:

`portfolio gap → role → policy/universe hard blockers → complete comparable evidence → ordinal score → CASH comparison → bounded research shortlist`

## 2. Required upstream inputs

A security ranking is permitted only when all of the following are available:

- a portfolio-gap contract containing a stable portfolio snapshot fingerprint;
- an active, effective, current and personal-sizing-ready WP2 IPS;
- a decision-ready WP3 universe with canonical content SHA-256;
- one and only one comparable evidence bundle for every security that survives static policy/role filtering;
- a timezone-aware assessment timestamp.

If the IPS or universe is not ready, the result is fail closed and contains only the `NO_ACTION/CASH` alternative.

If market/exposure evidence covers only part of the eligible universe, partial ranking is forbidden. The funnel returns `EVIDENCE_COVERAGE_INCOMPLETE`, no security shortlist and the cash alternative. This is the principal anti-selection-bias guard.

## 3. Candidate roles

Version 1 supports explicit portfolio roles:

- liquidity reserve;
- defensive bond;
- income;
- equity growth;
- diversification.

Instrument-type role compatibility is deterministic. A role mismatch is a hard blocker before scoring.

WP4 does not infer a portfolio objective from a ticker and does not let an LLM assign a role-fit number.

## 4. Hard blockers before score

Static blockers run before market evidence is requested:

- role mismatch;
- instrument type outside IPS allowlist;
- instrument type in IPS denylist;
- market outside IPS allowlist;
- market in IPS denylist;
- target-currency mismatch;
- explicit WP3 insufficient-liquidity flag.

Comparable-evidence blockers then include:

- missing/duplicate evidence;
- untrusted market source;
- stale or materially future-dated quote/liquidity evidence;
- invalid security/market identity;
- invalid price basis;
- minimum lot above supplied budget;
- portfolio-value currency mismatch;
- one-minimum-lot breach of position/group/sector/currency IPS limits;
- preliminary permanent-loss screen = block.

A blocked security never receives a published candidate score.

## 5. Market evidence

WP4 reuses existing `MarketQuoteV1` and `MarketLiquidityV1` rather than creating a parallel market schema.

Accepted source authorities are `PRIMARY`, `OFFICIAL` and `REGULATED`. Current v1 freshness policy:

- future timestamp tolerance: 60 seconds;
- hard maximum evidence age: 300 seconds;
- freshness grade buckets: ≤30s, ≤60s, ≤180s, ≤300s.

The funnel does not equate a fresh quote with final pre-trade readiness. Execution still requires the later pre-trade and owner-confirmation gates.

T-Invest market-data methods used by future evidence collection include official LastPrices/OrderBook/Candles/MarketValues surfaces. WP4 itself remains a pure engine and adds no broker call or public route.

## 6. Bond minimum-lot cost

Shares/ETFs use currency ask × lot.

Bonds must explicitly declare `PERCENT_OF_NOMINAL` cost basis and carry nominal value. The screen converts broker points/percent-of-nominal to currency before comparing affordability or concentration:

`minimum lot cost = ((best ask / 100) × nominal + accrued interest per unit) × lot`

A bond without nominal basis is rejected. A non-bond carrying percent-of-nominal basis is rejected.

This avoids the known category error of treating a bond quote such as `95` as 95 RUB.

## 7. Ordinal score — no false precision

Only candidates that pass every hard blocker are scored.

Each factor is an integer grade from 0 to 4. The contract fixes weights and mathematically reconciles `rank_points`; callers cannot inject a subjective score.

| Factor | Weight |
|---|---:|
| Role fit | 25 |
| Diversification / concentration headroom | 20 |
| Liquidity / spread | 20 |
| Minimum-lot cost efficiency | 15 |
| Preliminary permanent-loss screen | 10 |
| Freshness | 10 |

Maximum = 400 ordinal points.

The score is a sorting device, not expected return, probability of profit or price target. Deep research may later reject a high-ranked candidate.

## 8. Diversification / concentration grade

WP4 performs only a one-minimum-lot feasibility screen; final sizing belongs to WP10.

For the candidate lot, the engine calculates:

`weight delta = minimum lot cost / current portfolio value`

It projects position, group, sector and currency weights and hard-blocks any IPS limit breach. For candidates inside limits, the worst normalized remaining headroom determines the diversification grade.

No FX conversion is invented. Portfolio value and candidate lot cost must be in the same currency for this screen.

## 9. `NO_ACTION/CASH` is first-class

Every valid or blocked funnel contains exactly one `cash:no_action` row.

CASH is scored by the same fixed ordinal contract and wins exact score ties. Its role grade falls as the declared gap urgency rises, while its liquidity/cost/permanent-loss/freshness grades remain conservative strengths.

Therefore CASH can rank first. The engine never forces a security merely because a candidate list exists.

A cash-first result may still send a bounded set of security alternatives to WP5 research when the funnel itself is complete; research may confirm that no action remains best.

## 10. Determinism and fingerprint

Security ordering is:

1. descending reconciled ordinal points;
2. CASH first on exact tie;
3. stable `candidate_id` lexical tie-breaker.

Rejected rows are also sorted deterministically.

`funnel_sha256` binds:

- assessment timestamp;
- full gap contract including portfolio fingerprint;
- exact IPS reference/fingerprint;
- exact WP3 universe fingerprint;
- ranked alternatives;
- research shortlist;
- rejection reasons;
- global blockers.

The same semantic inputs and timestamp produce the same result regardless of source list ordering.

## 11. Privacy and execution boundary

WP4 result contains instrument identifiers, tickers, machine-readable blockers and bounded score evidence. It does not persist raw user free text, full account IDs, user IDs or tokens.

WP4 cannot call:

- OrdersService;
- StopOrdersService;
- Sandbox mutation services;
- withdrawal/transfer methods;
- real execution services.

`CandidateFunnelResultV1.trading_methods` is `Literal[False]`.

No `app.py`, OpenAPI, Render/Upstash or GPT Editor change is part of WP4.

## 12. Exit gate

WP4 is complete only when:

1. versioned gap/evidence/score/result contracts exist;
2. score arithmetic is contract-bound to documented weights;
3. policy/universe readiness and full eligible-universe evidence coverage fail closed;
4. policy/role blockers precede scoring;
5. stale/untrusted market evidence cannot score;
6. bond nominal conversion is covered;
7. budget and concentration headroom blockers are covered;
8. CASH is always present and can rank first;
9. source-order invariance, tie-breaks, bounded shortlist and fingerprint are tested;
10. repository guard + mypy cover the package;
11. exact-head Regression Shield is fully green;
12. PR is squash-merged and epic #176 marks WP4 complete.
