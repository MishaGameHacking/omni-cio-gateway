# F01 / F22 / F23 — retain the first runtime crash

## Evidence: 20b77ee / Android 39169578729

Attempt 1 failed before Back: `adb shell pidof ru.omnicio.app.debug` timed out in the chart scenario. The candidate PID was still present in later diagnostics. The timeout is not evidence that the app crashed.

Attempt 2 failed earlier, in the native shadow-control scenario. The UiAutomation connection ended, SystemUI and other system packages reported `DeadSystemException`, and init restarted zygote and dependent services. API36 was not reached. The software-navigation configuration is present, but guest `qemu.hw.mainkeys` was missing in provenance; the Back repair remains unverified. Neither attempt is a pass and neither authorizes an APK.

The failure reader had a confirmed diagnostic defect: `logcat -b crash -t 100` followed by another 16000-character tail discarded the initial crash headers behind the cascade. The retained crash text began at native frame 9 and could not establish the original system failure.

The repair reads the crash ring without the last-100-lines restriction. A bounded excerpt retains the head/tail and the first/last four fatal headers with adjacent timestamp, PID, process identity and cause. Overlaps are merged, omissions explicit, and output is bounded to 65536 characters. All reads retain their 10-second deadline. Existing package exit-info, process-death events, meminfo and activity diagnostics remain. There is no retry reclassification, JIT change, image replacement, callback substitution, new pass path or UI threshold change.

Local validation: 43 targeted tests passed, including seven new crash-evidence regressions. These are code tests, not emulator evidence. The next CI run must independently confirm API35/API36, Backend and exact-head Sonar. Private APK retention remains gated on all of those checks. Timeweb, server APK, backend deployment, production channel and merge remain untouched.
