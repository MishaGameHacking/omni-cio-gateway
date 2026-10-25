# Runtime assessment — API 37 / 4096 / 1200 s

The one actual Timeweb leaf started at 2026-10-25 11:05:08.322004 UTC and finished at 11:26:41.638975 UTC with `status=failed`. The boot window itself elapsed after **1200.002 seconds**. Android did not report boot completion within the deadline. Both installation result arrays are empty: the APK was not installed or launched.

- Source SHA256: `fdb272e3b396586631babd98392590c1562b2c5bafd981dffa831e035b9b7f5c`.
- Candidate APK38 SHA256: `d57ea8c55642aaf1b18703cf0170fdd78b5d73912d57b3415d34c563fcab9649`.
- Raw evidence gzip/tar: 83,380 bytes, SHA256 `2df858f45f32487e54a9dc66a222bf0ed9a6db3e021dba2f97219770c3a2ebb7`.
- Cleanup recorded zero remaining owned processes. Source, APK, fixture, verification, public manifest/APK and image metadata hashes were unchanged. Publication was not authorized.

## Observed guest progress

Zygote PID439 starts at kernel time 109.147–109.416s. SystemServer PID731 is already present by 281.833s; the same PID appears around 815–832s, controls artd/idmap2d around 839–862s and still logs at 11:26:14.996 UTC. ART first-boot verification of system applications continues after the deadline; Pulse explicitly uses `--compiler-filter=verify --compilation-reason=first-boot`, and Chrome/GMS verification messages continue until 11:26:20.210.

This is evidence of continued boot progress, not a successful boot. The late diagnostic collection does not extend or pass the boot gate. No confirmed fatal restart of the principal Zygote/SystemServer is found in the retained logs. Nearby crash_dump and untracked camera child exit lines lack a tombstone tying a fatal signal to a principal service. They do not establish a crash of our app, which was never installed.

## Measured resource pressure

The two detailed memory snapshots are 295.869298 seconds apart (11:20:11.780348 and 11:25:07.649646 UTC). Memory PSI some grows from 817,034 to 1,657,858 microseconds: **0.840824 seconds, 0.284188%** of that interval. Full grows by 0.840806 seconds. CPU PSI some grows by 0.593523 seconds; I/O PSI some by 0.213619 seconds.

Reclaim and swap did occur: the cgroup has memory.high=4800MiB, memory.max=5200MiB, peak near 4802MiB, and swap reaches 512MiB. The interval records +373,449 direct scans, +256,458 direct steals and +1,192 major faults. Host MemAvailable falls from 650.52 to 510.52MiB. All 44 resource samples record zero max/OOM/oom_kill/oom_group_kill events, and no quota throttling. Average cgroup use is about 1.06 CPU cores.

The measured memory stalls do not explain the entire 1200-second timeout. The presence of swap alone does not establish the cause.

## Limits and decision

The archive preserves a full kernel log but only a late guest-log tail (last 200 lines, output capped near 18,000 characters), predominantly collected after the deadline. It does not contain the complete early ART/SystemServer timeline or full tombstones. Detailed PSI/memory.stat were collected twice, with the last snapshot 93.989 seconds before the leaf ended; the calculated delta cannot be extrapolated over the remaining diagnostic cleanup.

No new retry, longer timeout, RAM/GPU/CPU change or disabled verification is justified by these findings. A future read-only audit of the installed image and preopt artifacts is a specific investigation direction, not proof of an image defect. ART's official default for first boot is verify: https://source.android.com/docs/core/runtime/configure/art-service .

The API37/16K matrix is also unpassed. The mandatory runtime/install/upgrade/UI publication gates remain in force. Layoutlib host renders are separate appearance evidence, not Android runtime screenshots. No claim about the current phone crash follows from this leaf.
