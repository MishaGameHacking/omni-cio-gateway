# Omni-CIO v9 — Portfolio Optimizer & Capital Scaling

Status: **WP10 implementation contract**  
Parent program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`  
Protected production baseline: **Omni-CIO v8.6.1**

## 1. Purpose

WP10 converts the exact WP9 Meta-Strategy Selection into deterministic portfolio targets that can actually be expressed in broker lots and cash after explicit commissions, tax estimates and bond accrued interest.

Canonical sequence:

`exact portfolio + WP2 IPS + exact current WP8 risk + exact WP9 selection + structured lot/market/friction evidence → lot-scaled target → hypothetical trade effects → WP8 target revalidation`

WP10 remains read-only. It creates no order, submits nothing to a broker and grants no execution authority.

## 2. Exact binding

Every optimizer result binds:

- exact portfolio snapshot SHA-256;
- exact WP2 policy reference and recomputed IPS fingerprint;
- exact current-state WP8 risk assessment SHA-256;
- exact WP9 strategy selection SHA-256 and selected regime.

WP10 rejects hypothetical WP8 assessments as the current baseline. The current risk assessment must have no proposed trade IDs and identical before/after states.

Every current portfolio position must have an exact optimizer asset row whose `RiskPositionV1` template equals the current WP8 input position. Missing or mutated position state fails closed.

## 3. No expected-return optimizer

WP10 does not accept expected return, alpha, macro-regime forecast or unconstrained utility score.

The optimizer uses a fixed, reviewable allocation policy per bounded WP9 regime, then applies the owner IPS and execution constraints. The fixed regime component budgets are implementation policy, not forecasts:

- `CAPITAL_PRESERVATION`: 25% liquidity / 60% quality debt / 15% diversified core;
- `DEFENSIVE_BALANCED`: 20% liquidity / 45% quality debt / 35% diversified core;
- `BALANCED_CORE`: 15% liquidity / 30% quality debt / 55% diversified core;
- `GROWTH_CORE`: 10% liquidity / 20% quality debt / 60% diversified core / 10% bounded active.

A WP9 `FORBIDDEN` component receives zero budget. An unavailable `ALLOWED` component remains cash. An unavailable `REQUIRED` component blocks readiness.

Owner liquidity reserve can only increase the cash budget. Non-cash component budgets are reduced proportionally when the IPS reserve is higher than the regime cash budget.

## 4. Valuation price versus execution price

WP10 deliberately separates portfolio valuation from execution cash arithmetic.

`OptimizerAssetV1.unit_full_value_*` is the **full economic value per unit** used for portfolio weights and WP8 target risk. For a bond this includes accrued coupon interest (НКД). For a non-bond it equals the current execution-price basis.

`OptimizerMarketEvidenceV1.clean_unit_price_base` is the **clean market execution price** in base currency. Its timestamp and source SHA-256 are part of the immutable optimizer evidence.

For a bond, the same market-evidence record also carries `accrued_interest_per_lot_base`. When this value is available the contract enforces:

`full unit value = clean unit price + accrued interest per lot / lot size`.

For a non-bond, accrued interest is forbidden and full unit value must equal the clean market price.

The runtime repeats the price-binding check before any non-zero trade so even an internally mutated/unvalidated object fails closed.

A bond trade with missing accrued-interest evidence is blocked; missing НКД is never converted to zero.

## 5. Small-capital scaling

Small portfolios must not be fragmented into meaningless positions.

For each component WP10:

1. divides the component budget deterministically across available assets;
2. caps each desired position by the owner `max_position_weight`;
3. compares desired value with both one broker lot at full economic value and the configured minimum meaningful portfolio weight;
4. skips sub-threshold micropositions rather than fabricating fractional lots;
5. rounds target quantity down to whole lots;
6. leaves unallocatable residue as cash.

A maximum target-position count is also enforced deterministically. Equal-weight overflow is resolved by stable asset key, not model preference.

## 6. Large-capital scaling

Every non-zero rebalance leg requires fresh structured market-capacity evidence:

- clean unit price in base currency;
- accrued interest per lot for bonds;
- average daily turnover in base currency;
- top-of-book depth in base currency;
- spread in basis points;
- timestamp;
- source SHA-256.

Participation and depth are measured against **clean traded notional**, not against accrued interest.

Safe daily notional is the minimum of:

- average daily turnover × maximum participation;
- top-of-book depth × maximum top-of-book participation.

Safe total notional is safe daily notional × maximum staging days.

If the desired trade is larger than safe total capacity, the target is scaled toward the strategy target by the maximum safe number of whole lots. This preserves a feasible partial step rather than pretending the full rebalance is executable.

Every output leg records:

- required execution days;
- daily-turnover participation;
- top-of-book participation;
- whether staged execution is required;
- `partial_fill_aware=true`.

A wide spread, stale/future market evidence, price-binding mismatch or zero safe capacity fails closed.

## 7. Bond settlement, fees, taxes and cash

For every rebalance leg WP10 keeps these values distinct:

- clean `gross_notional_base`;
- `accrued_interest_base`;
- `settlement_notional_base = gross_notional_base + accrued_interest_base`;
- commission estimate;
- SELL tax estimate;
- final signed cash delta.

For a BUY:

`cash_delta = -(settlement_notional + commission)`.

For a SELL:

`cash_delta = settlement_notional - commission - estimated_tax`.

This mirrors the existing project bond/pretrade convention in which НКД is a separate cash component rather than silently embedded in clean price.

Every non-zero trade also requires explicit friction evidence:

- commission basis points;
- evidence timestamp;
- one or more source SHA-256 values;
- estimated sell-tax basis points for SELL legs.

Missing values are never treated as zero. BUY tax is zero by contract because the field represents an estimated SELL tax only.

Commission and tax basis-point estimates are applied to clean gross notional. НКД remains a separate settlement component. Money arithmetic uses `Decimal`; commission/tax amounts use the explicit money quantum and `ROUND_HALF_UP`; lot calculations use explicit floor/ceiling rounding.

After initial lot and capacity scaling, WP10 recomputes cash after all SELL and BUY legs. If settlement cash including НКД and commissions would fall below the owner reserve, BUY legs are reduced deterministically, starting with bounded-active exposure, then diversified core, then quality debt. The optimizer never spends the IPS liquidity reserve to hit a nominal target weight.

## 8. Account eligibility

New BUY exposure requires `account_eligible=true`.

Unknown or false eligibility cannot be converted into a BUY. Existing holdings may still be reduced through SELL logic because selling an already-held position is not the same as granting purchase eligibility.

## 9. Risk revalidation

WP10 constructs `ProposedTradeRiskEffectV1` records for every changed position:

- exact current full market-value binding;
- cash delta after clean settlement, НКД, fees and tax estimate;
- exact post-trade `RiskPositionV1` at full economic value or removal;
- deterministic trade ID.

The effects are submitted to the real WP8 `assess_portfolio_risk` implementation.

For bonds, this avoids a false portfolio-value loss: cash pays clean price + НКД while the new WP8 position is valued at the corresponding full value. Only explicit fees/tax reduce portfolio value at the optimization instant.

A target cannot become plan-eligible unless:

- WP8 target assessment is decision-ready;
- target after-state is policy-compliant;
- the WP8 revalidation before-state exactly equals the supplied current WP8 after-state.

The final equality check prevents a target from being approved against different risk settings, stale evidence or a changed baseline. If current WP8 evidence aged between assessment and optimization, WP10 fails closed and requires a fresh risk assessment.

## 10. Scenario comparison

Every result contains exactly three non-forecast scenarios:

- `CURRENT`;
- `TARGET`;
- `NO_ACTION`.

Each scenario records portfolio value, cash, securities value, position count, clean turnover, commission, estimated tax, policy-compliance state and exact risk fingerprint/blockers where available.

There is no expected-return field. `NO_ACTION` is a real comparison baseline.

## 11. NO_ACTION strategy

If WP9 selects `NO_ACTION`, WP10 returns a ready, immutable no-trade optimization result:

- target lots equal current lots;
- no rebalance legs;
- `plan_eligible=false` because no execution plan is needed;
- CURRENT/TARGET/NO_ACTION scenarios are identical;
- exact current WP8 assessment is retained as target risk evidence.

## 12. Determinism and fingerprint

Canonical ordering is applied to:

- optimizer assets before computation;
- target positions by stable key;
- rebalance legs by deterministic trade ID;
- scenarios by scenario kind;
- blockers and warnings;
- friction source SHA-256 values.

Trade IDs are derived from a sanitized stable-key slug plus a stable SHA-256 suffix to avoid collisions from punctuation or truncation. A dedicated collision-shaped test verifies canonical ordering when different stable keys normalize to the same slug.

`optimizer_sha256` binds the exact policy/risk/strategy references, target lots and weights, clean prices, НКД, settlement amounts, fees/taxes, market/friction provenance, scenarios, WP8 target assessment, blockers and warnings.

Equivalent input ordering therefore yields the same fingerprint.

## 13. Threat and data-quality model

WP10 explicitly rejects or neutralizes:

- policy payload mutation under reused id/version;
- strategy from another portfolio/risk state;
- hypothetical WP8 assessment passed as current state;
- missing current optimizer asset rows;
- mutated risk-position templates;
- unbound or internally mutated execution price;
- missing bond accrued-interest evidence;
- fractional-lot target fabrication;
- zero commission/tax assumptions when evidence is missing;
- stale/future market or friction evidence;
- account-ineligible BUYs;
- oversized large-capital trades that exceed participation/depth windows;
- owner liquidity-reserve spending;
- target portfolios that fail WP8 risk/policy checks;
- broker mutation dependencies or execution authority.

## 14. Safety boundary

`omni_cio/optimizer` is internal and pure with respect to broker state. It may call the read-only WP8 risk engine but cannot import broker SDK mutation services, trading tokens, order APIs, Sandbox execution or real-execution modules.

`trading_methods=false` is contract-enforced.

WP10 adds no public route, OpenAPI Action, Render/Upstash mutation state or GPT Editor change. Applied GPT remains v8.6.1 until WP15.

## 15. Exit gate

WP10 is complete only when:

1. versioned optimizer asset/market/target/leg/scenario/result contracts exist;
2. exact WP2 + current WP8 + WP9 + portfolio binding fails closed;
3. full valuation values and clean execution prices are provenance-bound and reconciled;
4. bond НКД is explicit, missing НКД fails closed, and settlement cash reconciles;
5. target weights obey component directives and owner reserve/position limits before lot conversion;
6. small-capital micropositions and fractional lots are eliminated deterministically;
7. large-capital depth/spread/participation/staging constraints are explicit;
8. every non-zero leg has fresh commission/tax and market provenance;
9. cash after settlement, НКД and fees preserves the IPS liquidity reserve;
10. CURRENT/TARGET/NO_ACTION comparison contains no expected-return forecast;
11. target trade effects are revalidated by WP8 and any hard target breach blocks plan eligibility;
12. Decimal rounding and canonical fingerprints are deterministic/source-order invariant;
13. optimizer runtime is pure/read-only and repository-guarded;
14. tests, Ruff, mypy and exact-head Regression Shield are green;
15. unresolved review threads are zero;
16. PR is squash-merged and epic/status evidence is updated.
