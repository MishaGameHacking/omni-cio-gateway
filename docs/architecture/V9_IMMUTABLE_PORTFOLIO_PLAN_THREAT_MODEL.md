# WP11 Immutable Portfolio Plan — Threat and Data Model

## Trust boundary

WP11 is downstream of validated WP2/WP8/WP9/WP10 objects and upstream of WP12 execution. It is not a broker adapter and does not grant execution authority.

## Protected assets

- owner IPS identity and fingerprint;
- exact portfolio snapshot identity;
- exact current and target WP8 risk assessments;
- exact WP9 strategy selection;
- exact WP10 optimizer output and ordered leg set;
- market, friction, FX and bond accrued-interest evidence;
- owner approval challenge bound to one exact immutable plan.

## Threats and controls

| Threat | Control |
| --- | --- |
| Caller mutates a Pydantic object with `model_copy` while retaining an old embedded hash | WP11 recomputes WP8/WP9/WP10 hashes and re-validates the complete plan before review |
| Portfolio changed after optimization | Exact portfolio snapshot SHA is embedded and compared during review |
| Policy changed after optimization | Exact WP2 policy reference/fingerprint is embedded and compared |
| Risk or strategy changed | Exact WP8/WP9 SHA bindings cancel the plan |
| Optimizer result changed | Exact WP10 optimizer SHA binding cancels the plan |
| Actionable asset evidence becomes stale before plan creation | Build-time market/friction/FX freshness gates fail closed |
| Market changes after plan creation | Review checks clean price, spread, turnover, depth, FX and bond НКД drift |
| Cost assumptions change | Friction source hashes, commission and estimated tax are compared |
| BUY eligibility disappears | BUY plan cancels; SELL does not incorrectly require buy eligibility |
| Approval phrase is replayed for a mutated plan | Phrase is deterministically derived from exact plan SHA |
| Extreme market discontinuity exceeds 100% | Drift result uses unbounded non-negative bps while tolerance remains bounded |
| Broker mutation leaks into WP11 | Dedicated AST/text boundary guard bans broker/Sandbox/Real mutation surfaces |

## Data minimization

WP11 stores no broker token, raw account identifier, personal identity record, order identifier or broker response. It consumes only already-normalized internal contracts and masked/pseudonymous stable instrument identifiers.

## Non-goals

- no order submission;
- no order cancellation/replacement;
- no autonomous execution;
- no broker confirmation state;
- no durable execution journal;
- no public OpenAPI/GPT Action;
- no GPT Editor configuration change.

## WP12 handoff

WP12 must require an exact valid WP11 plan/review identity and must preserve the proven v8.6.1 explicit-owner-confirmed, idempotent, capped and broker-reconciled execution lifecycle. WP11 approval challenge alone is never sufficient to submit an order.
