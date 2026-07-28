# Operations Analytics Contracts v1

## Purpose

PR-07 introduces an immutable, versioned boundary for the current read-only
`getOperationsAnalytics` payload. It normalizes aggregate operation counts,
cash flows, turnover, instrument activity, pagination, reconciliation and data
quality into `OperationsAnalyticsV1`.

The public FastAPI route and GPT Action response remain unchanged. The adapter
is a data-only layer and imports no broker SDK.

## Contract structure

```text
OperationsAnalyticsV1
├── ContractMetadata
│   ├── masked account
│   ├── UTC retrieved_at
│   ├── T-Invest provenance
│   └── quality / completeness / issues
├── OperationsPeriodV1
├── OperationsPaginationV1
├── state and category counts
├── CurrencyCashFlowV1[]
│   └── all supported operation categories
├── NetExternalFlowV1[]
├── TurnoverV1[]
├── InstrumentActivityV1[]
├── OperationsReconciliationV1
└── OperationsSourceQualityV1
```

## Financial arithmetic

All amounts use Python `Decimal`, never binary `float`.

Each category bucket validates:

- `gross_amount = inflow + outflow`;
- `net_payment = inflow - outflow`;
- zero-count buckets cannot contain non-zero money.

Per currency:

- `net_external_flow = deposits - withdrawals`;
- `turnover = purchases + sales`;
- category reconciliation difference must equal
  `categories_net_payment - operations_net_payment`.

Currencies remain separate. The source contract rejects
`no_cross_currency_aggregation=false`.

## Double-count protection

The contract requires both existing protections to remain active:

- commission cash totals use top-level `operation.payment` only;
- repeated parent-linked commission updates are collapsed;
- embedded child operations and embedded trades are not independently summed;
- financial summaries include executed top-level operations only.

A payload that reports these protections as disabled cannot satisfy contract v1.

## Quality mapping

The adapter maps source diagnostics into bounded `DataIssue` records:

- invalid dates or money;
- truncated pagination;
- unconfirmed reconciliation;
- unknown operation types;
- limited instrument activity;
- component errors;
- unstable instrument identity;
- duplicate removal and excluded out-of-period rows.

Raw upstream error content is not copied into the normalized contract.

A source is `verified/complete` only when it is explicitly complete, fully
paginated, reconciled, free of invalid rows and contains no warning/error issue.
Partial or degraded data remains representable but cannot be silently promoted
to verified data.

## Compatibility and safety

PR-07 does not change:

- FastAPI paths or HTTP methods;
- OpenAPI schemas or operation IDs;
- legacy Action response fields;
- T-Invest calls or permissions;
- `trading_methods=false`;
- Render entrypoint `app:app`;
- Gateway API component version `3.9.1`.

The adapter rejects any payload where `trading_methods` is not explicitly
`false`, the account is not masked, currencies are combined, required quality
counters are missing, or arithmetic does not reconcile.

## Rollback

Revert the PR merge commit. Existing runtime routes do not depend on the new
contract package, so rollback requires no API, database, Render or broker-side
migration.
