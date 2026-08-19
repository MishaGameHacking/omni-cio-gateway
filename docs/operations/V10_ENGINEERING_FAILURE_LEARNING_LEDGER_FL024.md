# FL-024 — Concurrency rehearsals need database-side time bounds, not only a parent-process timeout

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR PR #336; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-19**  
WP / PR / reference: **WP22A Phase 2 Product-auth / tenant-security correction / PR #336**

## Symptom / failing gate

The focused Phase-2 PostgreSQL rehearsal contains an intentional concurrent registration race. An earlier exact-head cycle remained inside `Run isolated PostgreSQL tenant-security rehearsal` long enough to monopolize the single authoritative Lenovo runner. A first correction wrapped the Python child process in a 120-second `Process.WaitForExit()` timeout.

On later exact head `ce40f7a9ed9eeb45bd9e7a3800e2c1456c5cf61e`, static quality, unit tests and PowerShell parsing all succeeded, but the focused gate again remained inside the PostgreSQL rehearsal beyond the intended child-process bound. This is not acceptance evidence and must not be treated as an infrastructure PASS.

## Root cause

The first correction bounded only the parent PowerShell process's wait for the Python child. The deliberate Python concurrency race could still block inside a PostgreSQL statement while `ThreadPoolExecutor` teardown waited for a running worker. The synthetic PostgreSQL sessions themselves had no `statement_timeout` or `lock_timeout`, so the database wait was not independently fail-closed.

Cleanup also relied on the default `pg_ctl` wait bound, making the total failure domain larger than the intended focused timeout.

## Blast radius searched

The issue is confined to the synthetic WP22A Phase-2 rehearsal harness. Production registration semantics, tenant constraints, RLS policies, session handling and broker authority are unchanged.

The correction does not:

- weaken the concurrent-registration test;
- remove the advisory-lock serialization proof;
- change application registration behavior;
- disable PostgreSQL RLS or negative tests;
- relax CI thresholds;
- add broker-write authority;
- enable public registration/provider apply;
- change `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` or protected V9 rollback.

## Corrective change

The fresh-cluster wrapper now provides server-side time bounds to every probe connection through libpq `options`:

- `statement_timeout=15000`;
- `lock_timeout=10000`.

The wrapper retains the independent 120-second child-process watchdog, kills the child process tree through Windows `taskkill /T /F` on timeout, and explicitly bounds PostgreSQL start/stop waits with `pg_ctl -t 10` / `PGCTLTIMEOUT=10`.

This creates layered fail-closed bounds: database statement/lock -> child probe -> PostgreSQL lifecycle -> outer GitHub job.

## Permanent regression / guard

The focused Phase-2 workflow continues to execute this wrapper against a fresh PostgreSQL 18 cluster. A database/concurrency stall must now become an explicit focused failure rather than consume the authoritative runner until the outer job timeout.

All final acceptance evidence must come from the new exact head after this correction; previous GREEN results are obsolete for merge acceptance.

## Future prevention rule

Any CI rehearsal that intentionally exercises locks, leases, concurrent transactions or blocking recovery paths must bound the operation at the subsystem that can block. A parent shell/process timeout is a second line of defence, not a substitute for database-side `statement_timeout` / `lock_timeout` or equivalent service-level bounds.

Cleanup commands that wait for an external service must also have explicit finite timeouts.

## Dependency/tooling knowledge change

PostgreSQL `pg_ctl` supports an explicit `-t/--timeout` bound for start/stop wait operations. PostgreSQL sessions also support `statement_timeout` and `lock_timeout`; supplying them to the isolated rehearsal connection prevents a deliberately adversarial concurrency test from creating an unbounded CI failure domain.
