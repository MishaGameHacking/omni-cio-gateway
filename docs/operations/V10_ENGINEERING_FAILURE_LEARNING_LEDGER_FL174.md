# FL-174 — Synthetic cluster creation acceptance is not terminal startup readiness

Date: 2026-09-27  
WP / reference: TIMEWEB-PLATFORM-CONSOLIDATION / V10 RU-PG-B Timeweb Synthetic Create workflow ordinal #6 / accepted main `dee72c4fadd775ffcf878ce7dd7484aa57ed35f1`

## Symptom / failing gate

The manual `V10 RU-PG-B Timeweb Synthetic Create #6` run passed the protected-main policy, source-contract, parity-transport, GitHub Environment and paid-create confirmation gates. The provider step then stopped after approximately five minutes with:

`TIMEWEB_RU_PG_SYNTHETIC_CREATE=STOPPED code=TIMEWEB_CLUSTER_START_TIMEOUT`

The screenshot evidence and source path agree: this was not a Python syntax failure, not a GitHub bootstrap failure and not evidence that the create POST should be replayed.

## Root cause

The synthetic-cluster provisioner correctly modeled Timeweb creation as asynchronous and already prohibited blind POST retry, but its terminal-readiness waiter still used a locally invented 288-second start budget. A valid provider state could remain `starting` longer than that budget.

That local budget therefore acted as an accidental readiness SLA. The program had the right state machine but an insufficient observation horizon.

This is the same defect class recorded in FL-171 for public IPv4/TLS readiness: provider mutation acceptance and provider readiness are separate events. A bounded waiter is necessary, but its timeout is a local safety bound, not proof that the provider operation failed.

## Why existing checks did not catch it

The source contract and unit tests required only that the start waiter be multi-minute and shorter than ten minutes. They proved:

- no second create POST;
- exact-target GET-only recovery;
- transient control-plane read retry;
- safe `starting` shape validation;
- exact `started` terminal shape;
- a generic timeout code.

They did not prove that the chosen live budget was large enough to tolerate actual Timeweb startup behavior, and they did not distinguish "provider is still safely starting" from a generic observed-state timeout.

The code was therefore internally consistent and GREEN while the live system could still stop before the provider converged.

## Blast radius searched

The repair review covered:

- synthetic cluster POST and ambiguous-response reconciliation;
- existing-target recovery;
- project membership re-check;
- safe `starting` and exact `started` shape verification;
- transient Timeweb control-plane read failures;
- workflow timeout and secret scope;
- public IPv4/TLS eventual-consistency handling;
- P3 PostgreSQL production transport/readiness handling;
- failure-learning FL-171 convergence rules;
- contract, runbook, source guard and focused regression tests.

No evidence authorizes a second cluster create, delete, resize, public-network widening, IPv6, backup add-on, replica add-on, production DSN cutover, public-user activation, broker write or Real Trading.

## Corrective change

The focused repair keeps provider authority unchanged and strengthens observation only:

1. extend the synthetic `starting` GET-only budget from 288 seconds to 708 seconds;
2. bound each start-readiness GET to a 10-second socket-attempt timeout while preserving the control-plane client's finite two-retry policy;
3. raise the enclosing create job ceiling from 15 to 35 minutes so the **complete** worst-case nested read/retry envelope plus the 708-second delay budget retains more than ten minutes of workflow headroom;
4. classify a final safe `starting` observation as `TIMEWEB_CLUSTER_STARTING_READY_TIMEOUT`;
5. preserve `TIMEWEB_CLUSTER_START_CONTROL_PLANE_READ_TIMEOUT` for read-only control-plane unavailability;
6. preserve immediate failure for unsafe status or configuration drift;
7. preserve exact-target `existing-recovery` as GET-only and never issue a second POST for an existing target.

The new timeout is still fail-closed. It does not turn `starting` into success. If Timeweb remains `starting` after the larger bounded window, the workflow stops with a more precise sanitized code and the next action is read-only reconciliation.

A second pre-merge review found that the first correction's "workflow headroom" calculation counted only sleep delays. That was incomplete because `TimewebReadOnlyApi.get()` can itself make three bounded network attempts with 1s+2s retry sleeps. With the default 30-second socket timeout, 18 outer observations plus 708 seconds of sleeps could exceed the 20-minute Actions ceiling and be killed by GitHub before our semantic STOP code ran. The replacement proof therefore bounds the outer readiness read timeout and calculates headroom from the nested retry stack, not from sleeps alone.

## Permanent regression protection

The source contract, guard and tests now require:

- at least 600 seconds of synthetic start-readiness observation;
- less than 13 minutes of start-readiness delay budget;
- a 10-second bound on each outer readiness control-plane read;
- worst-case headroom calculated from both the 708-second delay vector and the nested provider read retry envelope;
- at least 600 seconds of enclosing workflow headroom after that complete worst-case wait;
- exactly one 35-minute create-job timeout marker;
- a distinct sanitized persistent-`starting` timeout code;
- successful convergence after multiple safe `starting` observations;
- continued no-replay / existing-target GET-only recovery semantics.

## Future prevention rule

For every asynchronous provider mutation:

- mutation authority and readiness observation are separate contracts;
- a locally selected observation budget must never be described or treated as a provider SLA;
- timeouts must preserve the last safe semantic predicate when doing so does not leak provider-private data;
- timeout repair may extend observation but must not silently widen mutation authority;
- restarting after an ambiguous or incomplete mutation must adopt a uniquely identifiable existing intent/resource by read-only reconciliation before any new mutation can be considered.

