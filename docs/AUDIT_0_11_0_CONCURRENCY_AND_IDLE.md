# 0.11.0 source audit: concurrency, idle rendering and failure preservation

Audit started from PR #880 head `2395557b60acf80969d1ee8db3e3478ca66d6705` on 2026-10-19. This document supplements [PLAN_STATUS](PLAN_STATUS.md), [3D100 evidence](3D100_EVIDENCE.md) and [CI repair history](CI_REPAIR_0_11_0.md); it does not mark the full release complete.

## Reproduced defects and changes

1. `AnalysisQueue.initialize` read the legacy schema without a write reservation. Two startup workers can both observe a missing cancellation column and race in ALTER TABLE. A deterministic two-connection, file-backed SQLite regression reproduced `duplicate column name: cancel_requested_at`. Acquire BEGIN IMMEDIATE after executescript and before PRAGMA/ALTER; include the column in new databases. Failed migration rolls back; an existing queued row remains intact. No paid request is retried.
2. Physical rotation cleanup caught RuntimeError only. TimeoutExpired/OSError could replace the original UI assertion and skip later settings restoration. Regression tests reproduced all five affected paths. Collect ordinary cleanup exceptions, attempt every remaining restore, preserve the original failure with a note. Successful body plus failed cleanup still fails. Interrupts are not swallowed by the cleanup collector.
3. Android run [39214714079](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39214714079) failed on `Settled native scene unexpectedly resumed frame submissions`, not the older signed-out rotation assertion. `SpatialWindow.onGloballyPositioned` unconditionally invalidated native rendering even for identical placement. Only actual origin/density changes now invalidate. Density-only and subpixel changes still require a frame; surface resize, palette, input and asset invalidation paths are unchanged. Five JVM cases cover the predicate. Whether this resolves the entire emulator failure must be established by the unchanged native idle scenario, not inferred from unit tests.

## Wider checks

Backend CI now enumerates every Git-tracked Python source and compiles it without executing imports or bodies. Four bounded workers produce a deterministic report with exact checked-file count and locations, not source literals. A dirty/unmerged Git index fails. Both legacy backend compileall and all backend tests remain. Changes to Python files outside backend now trigger this gate as well.

Local checks used byte-verified selected source files, not a complete checkout. Independent queue and rotation suites ran concurrently in separate processes. Eighteen new Python methods passed (6 SQLite/queue/budget; 5 rotation cleanup; 7 source-audit). Existing invariants checked include one owner after 16 concurrent claims, one coalesced job after 16 submissions, an expired owner's inability to finish work, a project cap under 16 simultaneous reservations, and unresolved charges across midnight. Kotlin/JVM, full backend, Sonar and Android 15/16 results require CI at the new SHA and are not declared passed here.

## Boundaries

No Timeweb/server APK/backend deployment, broker trades, paid model calls, merge, published release or update-channel changes. Existing private draft APK retention is permitted only after its full exact-head validator succeeds. Native motion, gesture, pixel, process-identity, upgrade and 16KB gates are not disabled or relaxed. Global syntax checks do not prove all business logic correct; calibration, personal suitability, live financial integrations and physical-phone testing remain separate open work.

References: [SQLite transaction semantics](https://www.sqlite.org/lang_transaction.html), [Compose global-position callback](https://developer.android.com/reference/kotlin/androidx/compose/ui/layout/OnGloballyPositionedModifier), [Android 16KB testing](https://developer.android.com/guide/practices/page-sizes).
