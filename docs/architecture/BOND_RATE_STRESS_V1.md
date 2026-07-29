# Bond Rate Stress v1

## Scope

PR-23 adds an offline interest-rate stress layer for one bond value using the
bond duration already validated by `BondCreditRiskAssessmentV1`.

It is a scenario calculator, not a price forecast, recommendation or execution
method.

## Approximation

For each explicit yield shock:

`estimated price change ratio ≈ -duration × yield change`

`yield change = shock basis points / 10,000`

`estimated value = current full value × (1 + estimated price change ratio)`

`estimated change = estimated value - current full value`

The current value must be the full bond position value in one currency. For a
bond position this normally includes accrued interest when the upstream value is
defined on a full-value basis.

## Scenarios

The default scenarios are:

- rates down 200 basis points;
- rates down 100 basis points;
- rates up 100 basis points;
- rates up 200 basis points.

Callers may provide between 1 and 16 unique non-zero shocks. Shocks are bounded
to -1,000 through +1,000 basis points and sorted before calculation.

A scenario set fails closed when it is empty, oversized, duplicated, contains a
zero shock, exceeds the bounds or implies a negative estimated value under the
linear approximation.

## Credit assessment relationship

A rejected credit assessment blocks the rate stress. A partial credit assessment
is preserved as a warning when duration is still available, because the
mechanical interest-rate calculation can remain reproducible even though the
instrument is not recommendation-ready for another reason.

The source credit status is retained in the result.

## Limitations

The model explicitly assumes:

- linear duration approximation only;
- convexity is not included;
- credit spread is held constant;
- coupon reinvestment is not modeled;
- taxes, liquidity, bid-ask spread and slippage are not modeled;
- yield-curve changes are represented as a single parallel shock;
- issuer default or restructuring is not modeled.

Therefore large shocks and bonds with embedded options may differ materially
from the approximation. The output must not be presented as a guaranteed future
price.

## Output

Each scenario contains:

- shock in basis points;
- yield change;
- direction;
- duration;
- estimated price-change ratio;
- estimated value and change;
- estimated loss, floored at zero.

The assessment also reports the largest estimated loss and its ratio to current
value. Contracts reconcile every scenario and summary exactly.

## Safety

Every result keeps:

- `execution_ready=false`;
- `trading_methods=false`;
- `no_cross_currency_aggregation=true`;
- `convexity_included=false`;
- `credit_spread_held_constant=true`.

The implementation imports no broker SDK or network client and adds no route,
Action, Render setting, secret or execution identifier.

## Rollback

Revert the PR merge commit. No runtime, OpenAPI, database, Render, broker or GPT
Editor migration is required.
