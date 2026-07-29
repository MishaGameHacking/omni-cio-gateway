# Bond Credit Risk Assessment v1

## Scope

PR-21 adds an offline, fail-closed credit and horizon assessment for a normalized
bond `MarketResearchBundleV1`. It does not fetch ratings, map agency scales,
recommend a trade or expose a new Action.

## Rating identity

Issuer and issue ratings remain separate. A current issuer rating never
substitutes for a missing issue rating and an issue rating never substitutes for
issuer coverage.

Ratings are grouped by:

- exact agency name, case-insensitive;
- `issuer` or `issue` scope.

Only the latest effective timestamp for each agency and scope is selected. When
two records from the same agency and scope have the same latest timestamp but
different rating, action or outlook values, the assessment is rejected as
contradictory.

## Rating freshness

The default policy considers a selected rating stale when its effective action
is older than 400 days. The threshold is configurable and is not presented as a
universal regulatory standard.

A required scope is blocked as:

- `*_rating_missing` when no selected current record exists;
- `*_rating_stale` when current records exist but all exceed the policy age.

Withdrawn latest records are not current and therefore do not provide coverage.
Future timestamps beyond the allowed tolerance are rejected.

## Cross-agency boundary

PR-21 does not convert national or agency-specific rating labels into a common
numeric score. `cross_agency_scale_normalized=false` is permanent in this
version.

When current labels differ exactly, the result records the divergent scope and a
warning. Label divergence alone does not prove a credit disagreement because
agency notation and scales may differ. It remains visible for human review.

## Source authority

Reference, bond-metric and selected-rating sources must be primary, official or
regulated. Secondary or untrusted sources block the assessment.

## Bond horizon

The assessment derives:

- days to maturity;
- days to offer when present;
- effective exit date;
- duration;
- selected yield basis.

A future offer on or before maturity makes yield-to-offer the relevant basis.
Otherwise yield-to-maturity is used. The corresponding yield must be present.
An already passed offer is reported as a warning and maturity becomes the basis.
A passed maturity date is a rejection.

## Duration and metric freshness

The default maximum duration is five years and the default bond-metric age is
24 hours. Both are configurable conservative policy inputs rather than a
personal recommendation.

Stale metrics, excessive duration or a missing required yield block decision
readiness.

## Status

- `ready`: no blockers;
- `partial`: required data or a conservative policy input is incomplete/stale;
- `rejected`: wrong instrument type, missing reference, contradictory rating
  records, untrusted source, future timestamp or passed maturity.

Warnings never silently remove blockers.

## Safety

Every result has:

- `execution_ready=false`;
- `trading_methods=false`;
- `no_cross_currency_aggregation=true`;
- `cross_agency_scale_normalized=false`.

The implementation imports no network client, broker SDK or execution method.
It does not alter FastAPI routes, OpenAPI, Render or GPT Actions.

## Limitations

PR-21 does not yet provide:

- a minimum-rating rule across heterogeneous agency scales;
- default probability or loss-given-default estimates;
- issuer financial-statement analysis;
- covenant or subordination analysis;
- issue size and live turnover assessment;
- recovery analysis;
- automated live rating retrieval.

Those require source-specific adapters and independently reviewed methodologies.

## Rollback

Revert the PR merge commit. No runtime, database, OpenAPI, Render, broker or GPT
Editor migration is required.
