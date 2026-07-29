# Sell Tax Evidence V1

## Purpose

PR-31 introduces a strict evidence contract for the tax estimate used by a sell
pre-trade preview. It does not implement tax advice, determine final tax
liability or infer tax from a single portfolio average price.

The layer exists to close a safety gap between:

- the live sale-capacity collector, which intentionally returns tax as
  unavailable; and
- the typed sell preview, which requires confirmed tax evidence before it can
  become preview-ready.

## Evidence contract

`SellTaxEvidenceV1` binds an estimate to exact proposed sale terms:

- masked account;
- stable portfolio key;
- instrument UID and optional position UID;
- currency;
- lot size;
- number of lots and units;
- gross proceeds;
- canonical commission;
- evidence method and timestamp;
- optional complete report period;
- estimated tax.

Every object retains:

- `final_tax_liability=false`;
- `no_legal_tax_guarantee=true`;
- `execution_ready=false`;
- `trading_methods=false`.

## Evidence methods

### Broker-confirmed estimate

An external broker-backed source produced an estimate for the exact sale terms.
The contract records the estimate but does not represent it as final tax.

### Verified report reconstruction

A separately validated report workflow reconstructed an estimate. This method
requires both source-period boundaries. A later PR must implement the actual
report-to-tax reconstruction and its jurisdiction-specific methodology.

### Unavailable

The absence of tax evidence is represented explicitly. An unavailable object:

- cannot contain an estimated-tax amount;
- cannot contain a zero-tax reason;
- is incomplete and degraded;
- cannot enrich a sale-capacity payload.

## Zero-tax protection

A confirmed estimate of zero requires a non-empty verified reason. This prevents
missing data from being silently converted into a zero value.

Examples of acceptable future reasons include a broker-confirmed zero estimate
for the exact terms or a verified loss/zero taxable base from a complete source.
The contract does not validate tax law; source adapters remain responsible for
the factual basis.

## Exact-term enrichment

`enrich_sale_capacity_with_tax_evidence` accepts only confirmed evidence and
requires an exact match for:

- masked account;
- stable key;
- instrument UID;
- currency;
- lot size;
- lot and unit quantity;
- gross proceeds;
- canonical commission.

It also requires the source sale-capacity payload to be complete, read-only,
currency-consistent and protected from commission double counting.

When every check passes, the enricher:

1. inserts the confirmed estimated tax;
2. computes `net proceeds = gross proceeds - commission - estimated tax`;
3. marks tax and arithmetic checks as confirmed;
4. preserves a compact evidence summary;
5. retains `trading_methods=false`.

The source payload is copied and is not mutated.

## Relationship to broker data

T-Invest exposes portfolio average-price fields and an asynchronous broker
report. Those are potential inputs for future source adapters, not automatic
proof of tax liability. The report workflow already handles pending tasks,
pagination, duplicate removal and reconciliation, but it does not yet implement
jurisdiction-specific tax reconstruction.

Until that future adapter is implemented and validated, production live sale
preview remains blocked by unavailable tax evidence.

## Public API boundary

PR-31 adds no FastAPI route, HTTP method, OpenAPI operation or GPT Action. It
adds no broker SDK call, database or execution adapter.

## Validation

Focused tests cover:

- confirmed and unavailable evidence;
- zero-tax reason requirements;
- exact quantity and currency invariants;
- non-mutating enrichment;
- net-proceeds reconciliation;
- successful construction of a preview-ready typed sell preview while
  execution remains disabled;
- rejection of account, instrument, quantity, currency, proceeds and commission
  mismatches;
- rejection of incomplete, trading-enabled, future or unconfirmed evidence.

Regression Shield must pass lock verification, repository policy, compile,
Ruff, formatting, mypy, stable entrypoint, read-only release contract, full
pytest with coverage, dependency audit, Bandit and secret scanning.

## Rollback

Revert the PR merge commit. The live collector will continue returning tax as
unavailable, and the typed sell preview will remain fail-closed. Public API,
broker permissions and Render deployment remain unchanged.
