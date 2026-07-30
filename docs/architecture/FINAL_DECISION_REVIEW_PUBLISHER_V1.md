# Final decision-review internal publisher v1

## Scope

PR-62 adds the trusted process-local publication boundary that connects an already
validated final-review route plan and input binding to the bounded registry introduced
by PR-61.

The publisher is not an Action and is not an HTTP endpoint. It does not fetch portfolio
or market data, recalculate a recommendation, call a broker, or authorize execution.

## Internal API

```python
publish_final_decision_review_source(
    registry,
    route_plan,
    input_binding,
    correlation_id=...,
    request_id=...,
    published_at=...,
)
```

One `FinalDecisionReviewPublisherV1` instance and one publication lock are attached to
each registry. Concurrent calls for the same registry therefore share replacement and
capacity semantics.

## Preconditions

Publication fails closed unless all of the following are exact:

- route plan status is `ready_for_implementation_review`;
- route plan is blocker-free;
- input binding status is `valid`;
- masked account matches the compact response;
- requested and final options match;
- intent fingerprint matches;
- ordered instrument set and count match;
- query, response and Action-candidate SHA-256 values match the readiness dossier;
- correlation ID and optional request ID satisfy the safe trace format;
- publication timestamp is timezone-aware.

Trace identifiers and timestamps are validated before registry mutation.

## Publication semantics

The result disposition is:

- `published` when the exact context was not active;
- `replaced` when the same exact context was already active.

The publisher reports:

- publication and expiry timestamps;
- masked account;
- exact identity digests;
- instrument count;
- active source count;
- capacity eviction count;
- safe observability event.

With a bounded registry, adding another context may evict the oldest source. Replacing the
same context does not increase the active-source count.

## Concurrency

Publisher attachment is protected by a process-level lock. Each registry then owns one
publisher with its own `RLock`. Lookup, publication and active-count inspection form one
atomic publication decision for that registry.

This guarantees that concurrent identical calls produce one initial `published` result
and subsequent `replaced` results rather than multiple independent initial publications.

## Safe observability

`ObservabilityEventV1` contains only:

- correlation ID;
- optional request ID;
- masked account;
- active-source count;
- eviction count;
- replacement flag;
- instrument count.

External-call status is always `not_called`. The event contains no holdings, prices,
credentials, full account ID, private response payload or user confirmation.

## Security invariants

Every publication result preserves:

- `internal_only=true`;
- `http_publication_method_created=false`;
- `external_broker_called=false`;
- `source_values_recomputed=false`;
- `trade_authorized=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

Publishing a source does not modify production OpenAPI and does not add `POST`, `PUT`,
`PATCH` or `DELETE` methods.

## Lifecycle

- The source remains subject to the PR-61 registry TTL.
- Expired sources are removed on lookup or count inspection.
- A new process starts with an empty registry.
- No publisher state is persisted across restart or deployment.

## Remaining boundary

PR-62 exposes the safe internal publication primitive. It does not yet compose the entire
PR-53 through PR-58 chain from raw read-only analytical evidence in one orchestration
call. A later package may add that composition, but it must still call this publisher only
after all upstream gates pass.

Render deployment acceptance, GPT Editor schema import, authenticated Preview and rollback
remain separate real-world checks and are not completed by this package.

## Rollback

Revert PR-62. The PR-61 production route and empty-registry `503` behavior remain intact;
no public contract changes are required.
