# Omni-CIO V10 — WP5 Thermal Retest

Status: **ACTIVE WP5 owner action runbook**

## Why a retest is required

The first completed AIDA64 combined CPU/cache/memory/GPU run lasted 30m30s and proved system stability, but it did **not** satisfy the conservative WP5 thermal headroom gate:

- CPU core peak: 96 °C;
- CPU throttling maximum: 33%;
- CPU throttling average: 18%;
- no crash, BSOD or thermal shutdown;
- GPU load started, but GPU peak temperature was not recorded.

This evidence is intentionally retained as `FAIL` for the sustained-load Exit Gate. Thresholds must not be relaxed merely to make WP5 pass.

## Acceptance profile

The WP5 acceptance retest uses the intended conservative 24/7 node operating profile, not a game-boost profile:

1. keep AC connected and battery conservation enabled;
2. close/disable any temporary game-boost or auto-overclock mode for the duration of the test;
3. select the standard Windows **Balanced** power plan before the retest;
4. keep the notebook on a hard unobstructed surface with normal cooling airflow;
5. do not change BIOS voltage/clock limits and do not disable thermal protection.

The power-plan change is reversible and is an operating-profile decision, not a threshold change.

## AIDA64 workload

Use AIDA64 Extreme System Stability Test with exactly:

- `Stress CPU` — ON;
- `Stress FPU` — OFF;
- `Stress cache` — ON;
- `Stress system memory` — ON;
- `Stress local disks` — OFF;
- `Stress GPU(s)` — ON.

Minimum duration is 30 minutes. Stop immediately for a crash, thermal shutdown, visibly sustained thermal runaway, or any lower manufacturer protection limit.

## GPU telemetry

A combined load test is accepted only when GPU peak temperature is recorded. In a second elevated PowerShell window, run the repository sampler at the same time as AIDA64:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File infrastructure\windows\measure_wp5_gpu_load.ps1 `
  -DurationSeconds 1800 `
  -SampleIntervalSeconds 5 `
  -OutputPath "$env:TEMP\wp5-gpu-load.json"
```

The sampler records only aggregate temperature/utilization/power values. It does not record GPU UUID, serial number, addresses, usernames, process lists or secrets.

After the run, inspect only the aggregate values:

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
