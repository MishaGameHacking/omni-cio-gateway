# FL-171 — Provider mutation success must not be converted into failure by an invented readiness SLA

Date: 2026-09-26  
WP / PR / reference: TIMEWEB-PLATFORM-CONSOLIDATION / RU-PG-B Public IPv4/TLS workflow ordinal #6 / exact main `86294ebb0e5b6eb0a56aa8d4b28f1692f483a8d8`

## Symptom / failing gate

The manual Timeweb Public IPv4/TLS run passed exact-main/source policy, verifier `/32`, GitHub Environment, cost confirmation and the durable existing-IPv4 allocation prerequisite. The prior workflow-#5 deterministic HTTP 400 did not recur after PR #588 separated public IPv4 and TLS transitions.

The provider step instead stopped after about the source-defined wait window with:

`TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=STOPPED code=TIMEWEB_PUBLIC_IPV4_TLS_READY_TIMEOUT`

The old TLS/domain readiness delay vector was `2+3+5+8+15+20+30 = 83` seconds.

## Root cause

Repository code treated an internally chosen 83-second polling budget as if it were an external Timeweb readiness SLA. Timeweb's API documentation explicitly allows a successful mutation response while the resource remains in a startup/transition state. The PostgreSQL TLS procedure also requires the operator to wait for protected-connection setup to finish and does not document an 83-second completion guarantee.

The deterministic mutation rejection class from workflow #5 was therefore fixed; workflow #6 exposed the next boundary: asynchronous readiness can validly outlive the repository's short GET-only waiter.

The OWNER subsequently reported that a domain visible in the Timeweb UI had been added manually earlier and no further manual configuration was performed. That fact is treated only as unverified pre-existing provider state. It does not prove certificate issuance, DNS correctness or transport readiness, and it is not used as authority to create, overwrite or log a hostname.

## Blast radius searched

- public IPv4 readiness polling;
- secure-connection readiness polling;
- provider technical-domain / certificate `issued` predicate;
- workflow timeout ceiling;
- public-network rollback after TLS/readiness failure;
- restart behavior when secure connection is already enabled;
- managed floating-IP binding and firewall re-verification;
- operation-specific sanitized stop codes;
- current machine contract, source guard, runbook and current-state ledger.

No evidence from run #6 indicates a new OWNER-input, allocation-custody, firewall-authority, second-IPv4 or deterministic HTTP-rejection defect.

## Why preflight missed it

Unit tests proved transition ordering and immediate ready/pending semantics but did not bind the polling budget to live asynchronous-provider behavior. The source guard froze the existence of a waiter, not the adequacy of its bounded time budget or the diagnostic value of its terminal state.

## Corrective change

Keep exactly one provider mutation per state transition and keep reconciliation GET-only. Preserve the short public-IPv4 waiter because run #6 passed that boundary, but extend the TLS/domain/certificate readiness budget to a bounded multi-minute window below the workflow's 20-minute ceiling.

When that bounded window is exhausted, classify the last sanitized readiness predicate without exposing IDs, IPs, hostnames or provider response bodies:

- `TIMEWEB_PUBLIC_IPV4_STATE_DRIFT_DURING_TLS`;
- `TIMEWEB_TLS_ENABLE_READY_TIMEOUT`;
- `TIMEWEB_TLS_CERTIFICATE_READY_TIMEOUT`;
- `TIMEWEB_TLS_CLUSTER_STATE_READY_TIMEOUT`;
- generic `TIMEWEB_PUBLIC_IPV4_TLS_READY_TIMEOUT` only when no more specific safe class applies.

Unsafe provider status remains an immediate hard stop. Rollback remains mandatory when public exposure may exist.

## Permanent regression / guard

Focused tests require the TLS readiness budget to be at least five minutes and below fifteen minutes, prove delayed certificate issuance can reconcile via GET without another mutation, and prove secure-enable and certificate timeouts emit only sanitized stage-specific codes. The machine guard requires the bounded TLS delay vector and the stage-specific timeout markers.

## Future prevention rule

Never infer a provider readiness SLA from a locally convenient polling duration. For asynchronous infrastructure mutations, distinguish mutation acceptance from readiness, use a bounded budget justified against the enclosing workflow deadline, reconcile by read-only state, and preserve enough sanitized predicate evidence to diagnose a timeout without widening authority or leaking provider data.

## Dependency / tooling knowledge change

Current Timeweb DBaaS documentation states that successful resource operations can return before a resource is fully ready, and PostgreSQL TLS setup requires waiting for configuration completion. The current public documentation does not establish an 83-second TLS readiness SLA.
