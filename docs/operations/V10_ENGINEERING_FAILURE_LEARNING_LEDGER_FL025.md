# FL-025 — A service-start timeout must be enforced outside the blocking native invocation

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR PR #336; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-19**  
WP / PR / reference: **WP22A Phase 2 Product-auth / tenant-security correction / PR #336**

## Symptom / failing gate

Exact head `65f05856c18183cff1805fc06e5c42ab2a35f0cc` completed Phase-2 Ruff, formatter, mypy, 42 focused tests and PowerShell parsing successfully. The PostgreSQL rehearsal then emitted:

- `WP22A_PHASE2_STAGE=initdb` at `08:14:40Z`;
- `WP22A_PHASE2_STAGE=postgres_start` at `08:14:42Z`.

No later stage marker was emitted. The obsolete-head run remained inside that startup stage until synchronization with a newer branch head cancelled it at about `08:26:15Z`. Downstream migration-recovery and source/permanent guards were skipped and are not acceptance evidence.

## Root cause

FL-024 correctly added `pg_ctl -t`, `PGCTLTIMEOUT`, SQL timeouts, a Python-child timeout and stage markers, but the new stage evidence exposed a narrower orchestration flaw: the PowerShell process itself invoked `pg_ctl start -w` synchronously through the native call operator.

`pg_ctl` documents `-t` as the bound for its own wait operation, but a parent shell cannot use that internal contract as its only containment boundary when the native invocation itself fails to return to the parent as expected. In this run the parent never regained control after the `postgres_start` marker, so its later Python watchdog and cleanup logic could not protect the single Lenovo runner.

The exact low-level Windows/PostgreSQL reason that the native invocation failed to return is not fabricated here. The proven engineering defect is relying on the blocking invocation to enforce the only startup wait boundary visible to the orchestrating process.

A full-diff follow-up also found a cleanup-order edge case before another CI result was trusted: if `pg_ctl` successfully launches PostgreSQL but the separate readiness proof fails, cleanup must already be armed before the startup attempt. Otherwise the wrapper could return a bounded failure while leaving a temporary PostgreSQL process behind.

## Blast radius searched

The defect is limited to the isolated Phase-2 PostgreSQL rehearsal lifecycle. Product identity, HMAC bindings, session semantics, tenant constraints, broker RLS policies and production authority are unchanged.

The correction does not:

- weaken the concurrent identity race;
- remove SQL `statement_timeout` or `lock_timeout`;
- bypass PostgreSQL readiness validation;
- relax any CI threshold or source guard;
- enable public registration/provider apply;
- add broker-write authority;
- alter `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` or V9 rollback.

## Corrective change

PostgreSQL startup is now split into independently bounded operations:

1. arm temporary-PostgreSQL cleanup **before** any startup attempt;
2. launch `pg_ctl start -W` through `Start-Process`, with a parent-enforced 10-second launcher timeout;
3. verify actual server readiness through a separately bounded `pg_isready` loop;
4. retain the existing session-level SQL lock/statement limits and Python probe timeout;
5. wrap the **entire PowerShell rehearsal process tree** in a separate Python watchdog with a 240-second bound;
6. if the outer bound is exceeded, terminate the complete Windows child process tree with a separately bounded `taskkill /T /F` call and fail the focused gate.

The shutdown path also uses a bounded `Start-Process` invocation rather than an unbounded direct native call.

This makes the failure domains independent: cleanup arming -> launcher -> readiness probe -> SQL -> Python probe -> outer rehearsal process.

## Permanent regression / guard

The Phase-2 source contract now requires:

- `Start-TemporaryPostgresBounded`;
- bounded `pg_isready` readiness checks;
- the non-waiting `pg_ctl -W` launch path;
- cleanup arming before the startup helper is invoked;
- absence of the former direct `& $pgCtl start` invocation;
- the independent outer watchdog and its 240-second workflow bound.

A future regression can fail, but it must not consume the authoritative runner indefinitely or leave a known temporary PostgreSQL lifecycle unowned after a readiness failure.

## Future prevention rule

Do not treat a child tool's documented timeout as the only timeout for a CI orchestration layer. If losing control of the native invocation would prevent the parent from enforcing cleanup or progressing, launch that operation under an independently bounded parent process and validate success through a separate observable condition.

For service startup specifically, prefer bounded launch plus bounded readiness verification over a single blocking call when CI runner availability is a scarce shared resource. Arm cleanup before the first operation that can create durable process state, not after readiness is already proven.

## Dependency/tooling knowledge change

PostgreSQL `pg_ctl -W` starts the requested action without waiting for readiness, so successful launch must be followed by an external readiness check. `pg_isready` provides that separate readiness signal. This split is useful on the Windows self-hosted CI lane because parent-side process timeouts remain enforceable even if the service's own synchronous wait path misbehaves.
