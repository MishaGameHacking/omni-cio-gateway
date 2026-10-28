# F01 / F22 / F23 — first-boot readiness, 19 October 2026

## Observed failure, not a presumed application crash

Android run 39174144047 / job 117813217168 on head 8f081e4 built and linted all APK variants successfully. API35 upgraded and launched the preview, then completed a clean install and initially launched MainActivity. At 00:07:36 the guest system_server PackageManager thread failed with IllegalStateException: Shouldn't be here, through Environment.isExternalStorageLegacy and PackageManager.LegacyPackageDeleteObserver during package deletion. DeadSystemException cascaded, init restarted zygote, and the candidate process disappeared. The final process-liveness assertion correctly failed. No complete UI suite or API36 pass was obtained.

## Repair under test

The driver previously proceeded from sys.boot_completed directly to package installation while first-boot system package activity continued. User setup was completed only much later around the predictive-Back scenario. The whole installation and UI session now runs inside completed, scoped user setup, after Android's own PackageManager foreground and background handler barriers. Both commands require exit code zero AND exact Success; each retains a 60-second device limit and a 70-second host limit. A changed or missing system_server PID fails preparation or the session instead of silently rebinding to a restarted OS. Settings are restored; physical devices, other AVDs and secondary users are rejected before writes.

This removes a setup-ordering defect; only the next emulator result can establish whether it also resolves the observed platform crash. It is not proof of a JIT, GPU or hypervisor defect. JIT, system images, acceleration, renderer, page-size requirements, application code, UI thresholds and retry classification are unchanged. No restart-until-green mechanism was added. All upgrade, clean install, preview launch, complete synthetic UI and API35/API36 checks remain mandatory before retaining a private APK.

Primary command contract: AOSP PackageManagerShellCommand.runWaitForHandler, https://android.googlesource.com/platform/frameworks/base/+/4c1bdc28c6d91af5e4bfb0ebd48118150748602a/services/core/java/com/android/server/pm/PackageManagerShellCommand.java . PackageManager barriers drain already queued handler work, not all future system activity.

Local validation: 16 new tests passed against the actual preparation and setup contexts; compileall passed. The original transport, app-result, retry and main orchestration helpers are AST-identical. These are code tests, not emulator proof. The API35 experimental x86_64 ps16k image verifies 16KB userspace simulation, not a physical ARM 16KB kernel.

Timeweb, server APK, backend deployment, production channel, base branch and merge remain unchanged. Version 0.11.0 is still in development; manual-test attachment does not authorize production release.
