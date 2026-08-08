# Omni-CIO V10 — WP5 Thermal Retest

Status: **ACTIVE WP5 owner action runbook**

## Why a retest is required

The first completed AIDA64 combined CPU/cache/memory/GPU run lasted 30m30s and proved system stability, but it did **not** satisfy the conservative WP5 thermal headroom gate:

- CPU core peak: 96 °C;
- CPU throttling maximum: 33%;
- CPU throttling average: 18%;
- no crash, BSOD or thermal shutdown;
- GPU load started, but GPU peak temperature was not recorded.

A second automated-owner run improved the thermals materially, but still did not pass the fail-closed gate:

- AIDA64 elapsed time was approximately 29m13s because telemetry started before AIDA64;
- CPU core peak: 97 °C;
- CPU throttling maximum: 26%;
- CPU throttling average: 5.8%;
- CPU utilization average: 99.6%;
- no crash, BSOD or thermal shutdown.

A third run proved the conservative 90% processor profile provides ample CPU thermal headroom:

- AIDA64 elapsed time: 33m36s;
- CPU core peak: 77 °C;
- CPU throttling maximum: 0%;
- CPU throttling average: 0.0%;
- CPU utilization average: 99.5%;
- no crash, BSOD or thermal shutdown.

The third run is not accepted as the final combined-load evidence because the launcher was still waiting at its manual ENTER synchronization prompt, so concurrent sanitized NVIDIA telemetry was not started for that run. The CPU result is therefore useful engineering evidence but is not combined with GPU evidence from a different attempt. WP5 remains fail-closed until one coherent combined run records all required fields.

The thresholds are not relaxed merely to make WP5 pass.

## Acceptance profile

The WP5 acceptance retest uses the intended conservative 24/7 node operating profile, not a game-boost profile:

1. keep AC connected and battery conservation enabled;
2. close/disable any temporary game-boost or auto-overclock mode for the duration of the test;
3. use the repository launcher, which creates a **temporary** Windows Balanced-derived power scheme;
4. the temporary scheme caps AC maximum processor performance at **90%** for the acceptance run;
5. keep the notebook on a hard unobstructed surface with normal cooling airflow;
6. do not change BIOS voltage/clock limits and do not disable thermal protection.

The temporary power scheme is deleted after the run and the previously active scheme is restored. This is an operating-profile decision for the 24/7 node, not a relaxation of thermal thresholds.

Microsoft documents `PROCTHROTTLEMAX` / maximum processor performance as a percentage of maximum processor performance. The WP5 launcher uses that standard Windows mechanism rather than BIOS voltage or clock manipulation.

## Preferred launcher

From the repository root, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File infrastructure\windows\run_wp5_owner_acceptance.ps1
```

The launcher self-elevates only for the local acceptance run. It does **not** elevate the GitHub Actions runner service.

The launcher performs preflight checks, creates the temporary conservative power scheme, launches AIDA64, automatically detects when combined CPU+GPU load has actually begun, collects privacy-safe GPU telemetry, scans relevant system events, restores the previous power scheme, and removes the temporary test scheme.

## AIDA64 workload

Use AIDA64 Extreme System Stability Test with exactly:

- `Stress CPU` — ON;
- `Stress FPU` — OFF;
- `Stress cache` — ON;
- `Stress system memory` — ON;
- `Stress local disks` — OFF;
- `Stress GPU(s)` — ON.

**Synchronization rule:** configure the checkboxes, click `Clear`, then click `Start` in AIDA64. No PowerShell ENTER timing step is required. The launcher polls only coarse CPU utilization and NVIDIA GPU utilization until it observes combined load for three consecutive samples; only then does it begin the 30-minute evidence window. If combined load is not detected within five minutes, the launcher fails closed and records no acceptance evidence.

Minimum duration is 30 minutes. Stop immediately for a crash, thermal shutdown, visibly sustained thermal runaway, or any lower manufacturer protection limit.

## GPU telemetry

The launcher invokes the repository sampler automatically. The sampler records only aggregate temperature/utilization/power values. It does not record GPU UUID, serial number, addresses, usernames, process lists or secrets.

Manual fallback:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File infrastructure\windows\measure_wp5_gpu_load.ps1 `
  -DurationSeconds 1800 `
  -SampleIntervalSeconds 5 `
  -OutputPath "$env:TEMP\wp5-gpu-load.json"
```

After a manual run, inspect only the aggregate values:

```powershell
Get-Content "$env:TEMP\wp5-gpu-load.json"
```

Do not commit machine identifiers, screenshots containing identifiers, BitLocker recovery material or private paths.

## Pass criteria

The evidence overlay computes the result deterministically from `infrastructure/windows/wp5_node_thresholds.json`. Current conservative criteria include:

- duration >= 30 minutes;
- no crash or thermal shutdown;
- CPU core peak <= 95 °C;
- CPU throttling average <= 5%;
- GPU load actually started;
- GPU peak temperature present and <= 87 °C.

A lower manufacturer limit always takes precedence.

## Current limitation: AC-attach auto-start

The Lenovo Legion Y540 firmware audit did not expose `Power On with AC Attach`, `Restore after AC Loss` or an equivalent setting. The canonical state is therefore `NOT_SUPPORTED_BY_FIRMWARE`, not an invented `ENABLED` value.

This is accepted as an availability limitation for WP5 because the notebook battery provides ride-through for normal short AC interruptions. A complete battery depletion/full shutdown after a prolonged outage still requires manual power-on and must remain documented for later WP9 operations design.

## After a successful retest

Update only the sanitized numeric fields in `docs/architecture/V10_WP5_OWNER_PHYSICAL_EVIDENCE.json`, then let authoritative Lenovo CI recompute the combined OWNER_NODE_PROFILE and WP5 Exit Gate. Do not edit `exit_gate` by hand.
