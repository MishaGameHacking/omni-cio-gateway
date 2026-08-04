# Omni-CIO v9 — Fund X-Ray Engine

Status: **WP7 implementation contract**  
Parent program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`  
Protected production baseline: **Omni-CIO v8.6.1**

## 1. Purpose

WP7 expands ETF/fund wrappers into explicit underlying exposure instead of treating a fund ticker as automatically diversified.

Canonical sequence:

`WP3 fund identity + WP5 evidence → fund profile → composition → look-through exposures → hidden concentration → direct/fund overlap → immutable Fund X-Ray`

The X-Ray is analytics only. It does not recommend an order or authorize execution.

## 2. Exact fund identity

A fund is bound to the exact broker instrument UID from the WP5 research target and to the exact WP3 universe fingerprint.

The wrapper identity remains separate from every underlying holding. The wrapper is not added again to look-through exposure, preventing double counting of `fund + constituents`.

T-Invest provides a structured ETF surface through `Etfs`, `EtfBy` and asset metadata. That broker surface is useful for stable identifiers, fund characteristics, benchmark/management metadata and fee fields. It is not treated as proof of holdings unless the source actually contains composition data.

## 3. Composition modes

WP7 distinguishes four states:

- `full_holdings` — disclosed holdings reconcile to 100%;
- `partial_holdings` — disclosed holdings cover only a known fraction;
- `documented_buckets` — official exposure buckets exist but security-level holdings do not;
- `unavailable` — no decision-grade composition is available.

Partial composition is never rescaled to 100%. The residual remains `UNKNOWN`.

`unavailable` composition cannot carry a timestamp, fake holdings, fake coverage or fake provenance.

## 4. Holdings reconciliation

Every holding has:

- stable holding key;
- name;
- reported weight;
- optional underlying instrument UID;
- optional issuer, asset class, sector, currency and geography;
- WP5 evidence hashes.

Duplicate stable keys are rejected. Total disclosed holding weight may not exceed 100%.

For `full_holdings`, total weight must reconcile to 100% within a 1 bp tolerance. For `partial_holdings`, reported coverage must exactly reconcile to the disclosed weights and remain below full coverage.

## 5. Documented exposure buckets

When security-level holdings are unavailable, WP7 can preserve official buckets by:

- asset class;
- sector;
- currency;
- issuer;
- geography.

Each dimension is reconciled independently and may not exceed 100%. Missing residual within a dimension becomes `UNKNOWN`; it is never distributed proportionally across known buckets.

## 6. Look-through exposure

For holdings-based composition, WP7 derives all supported dimensions directly from holding weights.

If a known holding lacks a classification, that weight becomes `UNKNOWN` for that dimension. If composition itself is partial, the undisclosed residual is also `UNKNOWN`.

This means derived exposure retains uncertainty rather than making the reported slice look like the whole portfolio.

## 7. Hidden concentration

For holdings-based composition, WP7 calculates:

- top-1 holding weight;
- top-5 holding weight;
- Herfindahl-Hirschman concentration (`sum(weight²)`);
- measured composition coverage.

For documented-bucket-only composition, security-level concentration remains unavailable instead of being inferred from broad sectors/currencies.

## 8. Overlap

Two overlap views are deterministic:

### Direct holdings

For every disclosed constituent also held directly in the owner portfolio, `direct_holding_overlap` is the share of the fund represented by those duplicate constituents.

Example: if SBER is 12% of a fund and the owner also directly owns SBER, 12% of that fund is wrapper/direct duplicate exposure. The owner position size is not used to rescale the fund composition.

### Fund-to-fund

For two holdings-based funds:

`overlap = Σ min(weight_A_i, weight_B_i)` for shared stable holding keys.

The result is bounded by 100% and deterministic. Partial compositions only measure observed overlap; undisclosed residual is not guessed.

## 9. Fund profile and costs

The fund profile can preserve decision-grade evidence for:

- manager;
- benchmark/index;
- strategy;
- management style;
- constituent count;
- AUM and currency when available;
- turnover when available;
- tracking error;
- total/expense ratio;
- buy premium;
- sell discount.

T-Invest documents ETF/asset fields such as `management_type`, `primary_index`, `focus_type`, `total_expense`, `expense_commission`, `buy_premium`, `sell_discount` and `primary_index_tracking_error`. Missing broker fields remain missing rather than being assigned zero.

## 10. Freshness

Composition freshness is a first-class gate. Version 1 defaults to a seven-day maximum composition age and a five-minute maximum market-liquidity age, with a 60-second future-timestamp tolerance. These thresholds are explicit in `FundFreshnessPolicyV1` and can be versioned later.

Stale composition blocks `decision_ready` while preserving the stale evidence for inspection.

## 11. Provenance

Every profile/composition/holding/bucket evidence hash must exist in the exact bound WP5 dossier and must be `decision_grade`.

Media/context-only records cannot independently support Fund X-Ray state. Missing hashes fail closed.

## 12. Determinism

Canonical ordering is applied to:

- holdings by stable holding key;
- documented buckets by dimension/key;
- exposures by dimension/key;
- overlaps by kind/counterpart;
- source hashes and blocker codes.

`xray_sha256` binds the exact assessment time, WP5 dossier fingerprint, WP3 universe fingerprint, fund identity, profile, composition, liquidity, look-through exposures, concentration, overlap, uncertainty and blockers.

Equivalent source ordering therefore produces the same fingerprint.

## 13. Safety boundary

WP7 is internal/read-only and adds no:

- OrdersService / StopOrdersService call;
- Sandbox mutation;
- real-money proposal or submit call;
- withdrawal / transfer capability;
- public FastAPI route;
- OpenAPI Action;
- GPT Editor change.

`FundXRayV1.trading_methods` is `Literal[False]`.

## 14. Exit gate

WP7 is complete only when:

1. versioned fund profile/composition/holding/exposure/overlap/X-Ray contracts exist;
2. WP5 dossier and WP3 universe binding fail closed;
3. full/partial/bucket/unavailable composition states are explicit;
4. full holding weights reconcile and partial holdings are never normalized to 100%;
5. sector/currency/issuer/geography/asset-class look-through preserves unknown residual;
6. top holdings and HHI expose hidden concentration without inventing missing composition;
7. direct-holding and fund-to-fund overlap are deterministic;
8. fund costs/benchmark/management metadata remain provenance-bound and optional when unavailable;
9. stale/missing composition is explicit and cannot silently become fresh/full;
10. source-order invariance and X-Ray fingerprint are tested;
11. repository guard and mypy cover the package;
12. exact-head Regression Shield is fully green;
13. unresolved review threads are zero;
14. PR is squash-merged and epic #176 marks WP7 complete.
