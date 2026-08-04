# WP11 Immutable Portfolio Plan — Data Contract

## Object graph

`PORTFOLIO_PLAN` is a frozen, versioned object composed only from normalized v9 contracts.

### Identity bindings

- `portfolio_snapshot_sha256`
- `policy_reference`
- `current_risk_assessment_sha256`
- `strategy_selection_sha256`
- `optimizer_sha256`
- `target_risk_assessment_sha256`
- canonical `plan_sha256`

### Target state

The plan preserves every WP10 `OptimizerTargetPositionV1`, including current lots, target lots, lot size, desired weight, target value and target weight.

### Ordered leg state

Each actionable `PortfolioPlanLegV1` embeds one exact `OptimizerRebalanceLegV1`. No reconstructed or free-form order parameters are allowed. `NO_ACTION` is represented explicitly and carries no optimizer leg.

### Market baseline state

Each actionable stable key has exactly one `PlanMarketBaselineV1` containing:

- lot size;
- market evidence hash and timestamp;
- clean unit price;
- bond accrued interest per lot when applicable;
- spread;
- average daily turnover;
- top-of-book depth;
- friction timestamp and source hashes;
- commission and estimated sell-tax rates;
- account eligibility state;
- optional complete FX rate/source/timestamp tuple.

### Portfolio and risk totals

The plan stores current/target portfolio value, current/target cash, clean turnover, НКД, settlement turnover, commission, estimated tax and exact WP8 risk states before/after. Validators reconcile these fields to target rows and embedded optimizer legs.

### Validity state

The plan stores `created_at`, `expires_at`, deterministic drift tolerances and the complete hard-cancellation code set.

### Approval state

For actionable plans, `owner_approval_phrase` is derived only from `plan_sha256`. The plan never carries execution authorization, broker order state or a reusable confirmation code.

## Review input

`PortfolioPlanReviewInputV1` carries:

- current exact upstream identities;
- review timestamp;
- zero or one current market observation per actionable plan leg.

Unknown observation keys are rejected. Missing required observations cancel the plan.

## Review output

`PortfolioPlanReviewV1` carries:

- exact plan SHA;
- valid/cancelled/expired status;
- per-leg drift results;
- canonical cancellation codes;
- expected owner approval phrase only while valid;
- canonical review SHA;
- `execution_authorized=false`;
- `trading_methods=false`.

## Canonicalization

Collections whose source order is not semantically meaningful are sorted deterministically. Plan legs retain explicit contiguous `sequence` values. SHA-256 payloads use canonical JSON with stable key ordering and exclude only the self-referential hash field plus the derived approval phrase where required.
