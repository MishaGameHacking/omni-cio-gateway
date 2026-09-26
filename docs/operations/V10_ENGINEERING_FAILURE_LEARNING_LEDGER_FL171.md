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

## Cross-milestone systemic hardening discovered by blast-radius review

The live timeout was not treated as an isolated `sleep()` defect. A source review of the accepted Timeweb production-delivery consumers found the same broader failure class in later gates that had not yet been executed live: deterministic CI can prove syntax and invariants while a real provider still exposes eventual consistency, transient control-plane failures, route propagation, restart windows or an already-running prior intent.

The repair therefore introduces one fail-closed convergence law across the currently authorized Timeweb delivery path:

1. **Retry observation, never authority.** Only bounded GET/read/probe operations may retry on explicit transient network errors or HTTP `408/429/500/502/503/504`. Authentication/authorization failures, malformed state, wrong release SHA, security-header drift, tenant/security failures and certificate-verification failures remain terminal.
2. **Adopt exact intent instead of replaying mutation.** App Platform deployment recovery first looks for one existing non-terminal deploy of the exact accepted SHA. If found, the controller adopts and observes it. If multiple exact-SHA in-flight deploys exist, the state is ambiguous and stops. A timeout or ambiguous POST never grants a second POST.
3. **Provider acceptance is not readiness.** Public IPv4, TLS/certificate issuance and App Platform deployment each use bounded multi-minute GET-only reconciliation budgets below their enclosing workflow deadline. A local poll budget is never treated as a provider SLA.
4. **Separate transient transport from semantic failure.** Timeweb DB control-plane `500`, network errors, CA download transport and PostgreSQL socket propagation can recover within bounded budgets. TLS certificate verification, unsafe resource status, wrong binding, widened firewall, wrong release identity and invalid provider state never retry into GREEN.
5. **Rollback is also eventually consistent.** A rollback request is not proof of rollback. Public-network rollback now gets its own bounded GET reconciliation and still fails closed to manual reconciliation if closure cannot be proved.
6. **Later production gates inherit resilience, not authority.** P3 PostgreSQL connection establishment gets a longer production-only retry budget; P4 ingress, P5 Telegram activation and P6 production acceptance retry only transient read-only public probes. None of these changes authorizes DNS mutation, public-user activation, broker write, Real money or destructive provider operations.

This is intentionally stronger than adding longer sleeps. The controller models **intent identity + observed provider state + bounded convergence + terminal semantic predicates**. That makes interrupted/restarted workflows restart-safe without converting uncertainty into duplicate side effects.

## Additional latent defects closed by the same review

The provider-state audit found three failure modes that ordinary unit/state checks could leave dormant until repeated live use:

- App Platform deploy history was read from only the first `limit=100` page. Once history exceeded 100 rows, exact-SHA adoption and last-known-good proof could fail despite valid provider state. The controller now exhausts `limit`/`offset` pages, requires a stable provider `meta.total`, rejects truncated/changing history and caps traversal.
- rollback polling previously slept after its last observation and then stopped. A provider transition completing during that final backoff could therefore be falsely classified as unresolved. Rollback now always performs one final GET after the last bounded sleep.
- post-exposure firewall verification reused convergence helpers that could mutate a rule or resource link. Under eventual consistency, a stale empty GET after public exposure could therefore trigger a duplicate POST/PATCH. Firewall mutation/reconciliation is now confined to the pre-exposure phase; post-exposure checks are structurally read-only and machine-guarded.

These defects share the same root cause: **an observation surface was allowed to carry hidden mutation or incomplete-state assumptions**. The durable correction is to make observation complete, state-stable and side-effect free.
## Permanent prevention rule added after full blast-radius review

Every future provider-facing controller in the current Timeweb production path must classify each operation before implementation as one of:

- **MUTATION** — single-attempt under explicit authority; ambiguous result is reconciled by reads and is never blindly replayed;
- **OBSERVATION** — bounded retry is allowed only for explicit transient transport/status classes;
- **SEMANTIC/SECURITY PROOF** — mismatch is terminal and cannot be healed by retries;
- **ROLLBACK** — mutation remains bounded and the resulting safe state must be independently re-proved by observation.

For asynchronous provider operations, a restart must prefer adoption of a uniquely identifiable in-flight exact intent over creating a new intent. If identity is not unique or state cannot be proved, stop rather than guess.
