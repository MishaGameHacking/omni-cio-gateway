# FL-024 — Database rehearsals need layered subprocess and server-side time bounds

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR PR #336; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-19**  
WP / PR / reference: **WP22A Phase 2 Product-auth / tenant-security correction / PR #336**

## Symptom / failing gate

The focused Phase-2 PostgreSQL rehearsal contains an intentional concurrent registration race. An earlier exact-head cycle remained inside `Run isolated PostgreSQL tenant-security rehearsal` long enough to monopolize the single authoritative Lenovo runner. A first correction wrapped only the Python child process in a 120-second `Process.WaitForExit()` timeout.

On later exact head `ce40f7a9ed9eeb45bd9e7a3800e2c1456c5cf61e`, static quality, unit tests and PowerShell parsing all succeeded. The focused PostgreSQL step began at `07:12:44Z` and was still running when the obsolete-head workflow was cancelled by a later commit at `07:23:42Z` — almost eleven minutes later. The intended 120-second child bound therefore did not bound the complete rehearsal failure domain. Downstream recovery/source/permanent-guard stages were skipped and are not acceptance evidence.

## Root cause

The first correction bounded only one subprocess boundary inside a larger orchestration script. It did not establish an independently finite bound for every operation capable of blocking before, during or after the Python child:

- fresh-cluster native bootstrap (`initdb` / database creation);
- PostgreSQL start/stop lifecycle waits;
- SQL lock/statement waits inside the deliberate concurrency race;
- process-tree termination and cleanup.

Because the old wrapper emitted no safe stage markers inside the rehearsal, the cancelled log cannot truthfully identify one narrower substage as the sole eleven-minute wait. The engineering root cause is therefore **incomplete timeout coverage and insufficient stage observability**, not a fabricated claim about one specific database call.

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

The fresh-cluster wrapper now layers explicit bounds at every relevant boundary:

- `initdb`: 45-second native-process timeout;
- `createdb`: 15-second native-process timeout;
- PostgreSQL start/stop: `pg_ctl -t 10` plus `PGCTLTIMEOUT=10`;
- every probe PostgreSQL session: `statement_timeout=15000` and `lock_timeout=10000` supplied through libpq `options`;
- Python probe: independent 120-second watchdog;
- timed-out native/Python process: Windows process-tree termination with `taskkill /T /F` and bounded post-kill wait.

The wrapper also emits non-secret `WP22A_PHASE2_STAGE=...` markers for initdb, PostgreSQL startup/readiness, database creation, Python probe and shutdown. A future failure can therefore be classified by exact stage without exposing SQL payloads, credentials or private data.

This creates layered fail-closed bounds: native bootstrap -> PostgreSQL lifecycle -> database statement/lock -> child probe -> outer GitHub job.

## Permanent regression / guard

The focused Phase-2 workflow continues to execute this wrapper against a fresh PostgreSQL 18 cluster. A database/concurrency/bootstrap stall must now become an explicit focused failure rather than consume the authoritative runner until the outer job timeout.

All final acceptance evidence must come from the new exact head after this correction; previous GREEN results are obsolete for merge acceptance.

## Future prevention rule

Any CI rehearsal that starts external services or intentionally exercises locks, leases, concurrent transactions or blocking recovery paths must bound the operation at **each subsystem that can block**. A parent shell/process timeout is a second line of defence, not a substitute for database-side timeouts or bounded service lifecycle commands.

Long-running focused steps must also emit sanitized stage markers so a timeout can be attributed without rerunning blindly or leaking sensitive state.

## Dependency/tooling knowledge change

PostgreSQL `pg_ctl` supports an explicit `-t/--timeout` bound for start/stop wait operations. PostgreSQL sessions support `statement_timeout` and `lock_timeout`. Windows `taskkill /T /F` can terminate a child process tree when a bounded rehearsal process fails to exit normally. Together these mechanisms provide a finite failure domain for the isolated CI rehearsal without weakening the security assertions it exercises.
