# Omni-CIO v9 — Portfolio Risk Engine 2.0

## Purpose

WP8 converts the exact portfolio/policy/evidence state into a deterministic risk assessment for both the current portfolio and a hypothetical post-trade portfolio. It is an internal analysis layer only. It does not prepare, submit, replace or cancel broker orders and it does not change the production Custom GPT/OpenAPI surface.

The core design rule is fail-closed: a hard owner-policy breach is never diluted by a composite score, expected return, diversification score or another favorable metric.

## Dependency and binding model

WP8 consumes versioned outputs from earlier v9 packages:

- WP2 Investment Policy Statement and its exact `PolicyReferenceV1` fingerprint;
- a normalized portfolio state identified by exact `portfolio_snapshot_sha256`;
- WP6 credit-passport readiness/default/floor state for direct bond exposures;
- WP7 Fund X-Ray v1.1 identity/readiness, duration coverage and credit-quality evidence for ETF look-through;
- explicit market/liquidity evidence normalized upstream.

The engine recomputes the supplied IPS fingerprint. Matching only `policy_id` and version is insufficient. A changed IPS payload with the same version fails the binding gate.

Cross-currency values are never converted implicitly. Every non-base-currency position requires a `RiskFxConversionV1` with native/base currency, exact conversion rate, timestamp and source SHA-256; base value must reconcile exactly to native value × explicit FX rate. FX evidence also has an explicit freshness threshold. Stale FX blocks decision readiness rather than silently contaminating every base-currency concentration/stress calculation.

## Risk vectors

The assessment always preserves exactly eight independent vectors:

1. permanent-loss risk;
2. market/stress risk;
3. concentration risk;
4. liquidity risk;
5. credit/default risk;
6. currency risk;
7. inflation/opportunity risk;
8. data-quality risk.

There is deliberately no weighted composite risk score. `BREACH`, `UNKNOWN` and normal severities remain visible per vector.

## Exposure model and Fund X-Ray boundary

Each position carries normalized issuer/group/sector/asset-class/currency slices. Every supplied dimension must reconcile to 100% of that position.

`POSITION` is not a caller-supplied exposure dimension. It is derived once by the engine from the wrapper position itself. This prevents wrapper/underlying double counting.

An ETF cannot enter WP8 as a direct single-asset exposure. It must use `FUND_LOOKTHROUGH` and carry the exact Fund X-Ray SHA-256/readiness state. Underlying issuer/sector/class/currency slices then replace wrapper classifications for look-through dimensions. Missing or non-decision-ready Fund X-Ray evidence is explicit and blocks decision readiness; it is never replaced by a guessed diversification profile.

WP7 dependency hardening issue #202 upgraded Fund X-Ray to schema v1.1 so duration and credit-quality uncertainty are available when evidence supports them. WP8 does **not** infer a policy-floor result by parsing arbitrary credit-quality labels or performing an implicit rating-scale crosswalk.

## Fund credit summary

Every ETF can carry a `FundCreditRiskInputV1` bound to the exact Fund X-Ray SHA-256. It preserves:

- debt/credit-applicable fund weight;
- assessed credit weight;
- unknown credit weight;
- weight below the owner IPS credit floor;
- active-default weight;
- source SHA-256 provenance.

`assessed_weight + unknown_weight` must reconcile to `applicable_weight`. Floor-breach/default weights cannot exceed assessed weight.

If an ETF lacks this summary, credit evidence is explicitly incomplete. Any unknown credit weight blocks decision readiness. Any positive credit-floor-breach or active-default weight becomes a hard credit breach. An equity-only fund can explicitly report `applicable_weight=0` rather than being assumed safe because its wrapper type is ETF.

## Concentration and policy limits

The engine calculates:

- Top-1, Top-3 and Top-5 portfolio position weights;
- position concentration;
- issuer concentration;
- group concentration;
- sector concentration;
- asset-class concentration;
- currency concentration.

WP2 IPS limits are hard and owner-bound. Optional later owner overlays may also be hard only when explicitly owner-confirmed. System guardrails may be useful diagnostics but are prohibited from impersonating owner policy: they cannot be `hard` and cannot set `owner_confirmed=true`.

When more than one applicable limit exists for a dimension, the stricter limit is selected deterministically, with a hard limit winning an equal-threshold tie.

## Liquidity and capital scale

Liquidity is position-size aware rather than expressed as a fixed portfolio-size tier. For each position the engine can consume an explicit daily exit-capacity estimate and spread evidence. Exit days are calculated as:

`position base market value / daily exit capacity in base currency`.

This naturally scales from small accounts to materially larger positions: the same security can be liquid for a small position and capacity-constrained for a larger one.

Missing/stale liquidity evidence is explicit. The owner IPS liquidity reserve is a hard check against post-trade cash; a plan cannot hide a reserve breach behind stronger expected returns.

## Credit and permanent-loss gates

Direct bond positions require WP6 credit evidence. Active default/distress state and failure of the exact IPS credit floor are hard credit breaches. Non-decision-ready credit evidence is a readiness blocker.

ETF credit risk uses the Fund Credit Summary described above rather than treating the ETF wrapper as non-credit exposure.

Permanent-loss analysis is represented as `PASS`, `WATCH`, `BLOCK` or `UNKNOWN`. `BLOCK` is a hard breach; `UNKNOWN` blocks decision readiness rather than being silently interpreted as safe.

## Stress and drawdown

Stress scenarios are versioned deterministic definitions. A scenario can apply a broad shock or dimension/bucket-specific shocks. Portfolio loss is computed from base-value exposures only after explicit, fresh FX normalization.

The owner IPS `max_drawdown` is evaluated against every scenario. A stress result beyond that limit produces `MAX_DRAWDOWN_BREACH` and the market vector becomes a hard `BREACH`.

Default acceptance scenarios include broad invested-asset shocks of -10%, -20% and -30%. Additional scenarios can be supplied without changing the engine algorithm.

## Before/after proposed-trade risk

WP8 never sends a trade. A `ProposedTradeRiskEffectV1` is a hypothetical risk delta only. It binds to:

- a stable position key;
- the exact expected before-value;
- a base-currency cash delta;
- the full hypothetical after-position (or removal).

A value/identity mismatch fails closed. The engine builds a full after-state, recomputes all vectors/concentrations/liquidity/stress checks and records both newly introduced and resolved blockers.

Proposal effects are processed and fingerprinted in canonical trade-ID order. Reordering equivalent hypothetical effects does not change the after-state or assessment SHA-256.

`plan_eligible` requires both decision-ready evidence and a policy-compliant after-state. Therefore every downstream plan can carry explicit risk before and after, and a hard policy breach cannot be averaged away.

## Data quality

Missing or stale facts do not become zeros or inferred good states. Examples include Fund X-Ray readiness, Fund Credit Summary coverage, FX freshness, liquidity evidence, direct-bond credit evidence, permanent-loss evidence and exact policy binding. These appear as machine-readable blockers and in the data-quality vector.

Inflation/opportunity assumptions are optional. If they are absent, that vector is `UNKNOWN`; the engine does not fabricate macro assumptions.

## Determinism

Inputs are canonically ordered. The final `PortfolioRiskAssessmentV1` carries a SHA-256 over the canonical payload excluding only the SHA field itself. Reordering equivalent positions, exposure slices or proposal inputs does not change the fingerprint.

## Safety boundary

`omni_cio/risk` remains pure/read-only for WP8:

- no T-Invest SDK dependency or token access;
- no Orders/StopOrders/Sandbox service access;
- no `prepareRealTrade`, `executeRealTrade`, Sandbox preparation/execution or margin confirmation;
- no public route/OpenAPI Action added;
- no GPT Editor change;
- `trading_methods=false` in the WP8 assessment contract.

Production remains Omni-CIO v8.6.1 until WP15.

## Exit gate

WP8 is complete only when:

- contracts, architecture and repository guard are present;
- exact portfolio/policy/evidence bindings fail closed;
- explicit FX provenance and freshness protect all cross-currency aggregation;
- Top-1/3/5 and dimension limits are deterministic;
- ETF risk uses WP7 v1.1 look-through without wrapper double counting;
- ETF debt/default/floor state is represented by an exact-X-Ray-bound Fund Credit Summary;
- liquidity reserve/exit-capacity, direct/ETF credit/default and stress/drawdown gates are covered;
- proposed trades produce deterministic before/after risk and blocker deltas independent of input order;
- hard breaches never disappear into a composite score;
- acceptance/integrity tests, Ruff, format, mypy and full Regression Shield are green on the exact final head;
- review threads are zero and the PR is squash-merged.
