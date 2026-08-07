# Omni-CIO V10 — Lenovo Node Hardware/OS Audit Runbook

Status: **WP5 operating procedure**  
Scope: factual hardware/OS/security/network/time/power/thermal evidence only.

## 1. Safety boundary

WP5 is a read-only node audit. It does not install V10 product runtimes and does not change broker, GitHub, Render or Real-money authority.

Never put any of the following into `OWNER_NODE_PROFILE`, GitHub logs, artifacts, issues or chat:

- BitLocker recovery password/key material;
- broker/Telegram/API tokens;
- serial numbers/device UUIDs;
- MAC/IP addresses, SSIDs or interface identities;
- Windows username/hostname;
- account identifiers or private portfolio data.

If a diagnostic command displays one of those values, do not copy it into repository evidence.

## 2. Passive audit

Canonical collector:

```powershell
$profile = Join-Path $env:TEMP "owner-node-profile.json"
.\infrastructure\windows\collect_owner_node_profile.ps1 -OutputPath $profile
python .\scripts\assess_v10_node_profile.py $profile --thresholds .\infrastructure\windows\wp5_node_thresholds.json
python .\scripts\validate_v10_node_profile.py $profile --thresholds .\infrastructure\windows\wp5_node_thresholds.json
```

The collector is deliberately passive. It queries existing Windows/NVIDIA state and does not:

- enable BitLocker;
- expose or enumerate BitLocker recovery material;
- alter firewall rules;
- change Windows Time configuration;
- change power/firmware settings;
- start a broker or V10 service;
- install a dependency.

The resulting JSON may be committed only after the privacy validator passes.

## 3. Evidence sources

WP5 relies on Windows/NVIDIA supported interfaces where available:

- BitLocker state: Microsoft `Get-BitLockerVolume` documentation — https://learn.microsoft.com/powershell/module/bitlocker/get-bitlockervolume
- Windows Time diagnostics: Microsoft `w32tm` documentation — https://learn.microsoft.com/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings
- Windows Firewall profile state: Microsoft `Get-NetFirewallProfile` documentation — https://learn.microsoft.com/powershell/module/netsecurity/get-netfirewallprofile
- Physical disk health: Microsoft `Get-PhysicalDisk` documentation — https://learn.microsoft.com/powershell/module/storage/get-physicaldisk
- Volume/free-space state: Microsoft `Get-Volume` documentation — https://learn.microsoft.com/powershell/module/storage/get-volume
- Power diagnostics: Microsoft `powercfg` command-line documentation — https://learn.microsoft.com/windows-hardware/design/device-experiences/powercfg-command-line-options
- NVIDIA telemetry, where supported: NVIDIA System Management Interface documentation — https://docs.nvidia.com/deploy/nvidia-smi/

The repository stores only reduced operational facts, not raw command dumps.

## 4. BitLocker / physical-loss check

WP5 requires the system volume to be fully encrypted and protection enabled.

The profile may record only:

- provider = `BITLOCKER`;
- volume/protection state;
- encryption percentage/method;
- whether OWNER separately confirmed recovery-key custody.

The recovery key itself must stay outside the node/repository/CI/chat. OWNER confirmation is binary: `OWNER_CONFIRMED_SEPARATE` or not confirmed.

If BitLocker is unavailable/off/partial, WP5 remains blocked. Enabling or changing encryption is an OWNER/admin action and is not performed by the passive collector.

## 5. Windows Time / UTC guard

Application/event timestamps use UTC canonically. The audit measures offset against the fixed audit target `time.windows.com`; it does not record a private NTP endpoint.

Initial fail-closed thresholds:

- warning: absolute offset > 500 ms;
- sensitive-operation block: absolute offset > 2,000 ms;
- unknown offset or stopped Windows Time service: sensitive-operation block.

WP5 does not create Real-money execution. The time gate is a deterministic safety prerequisite for later sensitive operations.

## 6. Storage guard

System-volume initial limits:

- warning below 20% or 50 GiB free;
- block below 10% or 20 GiB free;
- physical-disk health must report `Healthy`.

No disk serial/model/unique ID is required for WP5.

## 7. Network/firewall guard

For the intended 24/7 OWNER node:

- a wired connection must be active;
- Domain/Private/Public Windows Firewall profiles must be enabled;
- inbound baseline must remain block/not-configured-to-inherit-block;
- WP5 must not create a public V10 listener;
- audit output may record only a wildcard-listener count, never addresses, ports or process names.

A nonzero wildcard-listener count is an observation to review; it is not by itself proof that V10 is publicly exposed because WP5 has not installed V10 runtime services.

## 8. Power and battery facts

Record only normalized operational state:

- battery present/not present;
- AC online where queryable;
- active power-scheme label;
- Lenovo battery-conservation state where queryable;
- restart-after-power-loss state where queryable.

Firmware-only values that Windows cannot prove remain `UNKNOWN_*` and block WP5 until verified. Unknown is never silently converted to PASS.

## 9. Controlled thermal/load test

Master Plan requires a controlled 30–60 minute CPU/GPU load test. The accepted initial target is 45 minutes, sampled every 5 seconds.

Abort immediately when:

- GPU reaches 87 °C;
- ACPI thermal zone reaches 95 °C;
- a lower manufacturer-defined safe limit is reached;
- Windows reports thermal shutdown/throttling instability;
- the OWNER observes abnormal fan/power/battery behavior.

Warnings begin at 80 °C GPU / 85 °C ACPI zone.

A CPU-only burn is **not** accepted as the mandatory CPU/GPU test. If no reviewed GPU workload generator exists locally, record `GPU_LOAD_GENERATOR_REQUIRED`; do not fake a PASS from `nvidia-smi` telemetry alone. WP5 must use a bounded, reviewed local workload and temperature-abort monitor before acceptance.

## 10. Reboot and network-reconnect checks

WP5 needs factual PASS evidence for both:

- Windows clean reboot -> self-hosted runner returns -> same sanitized node-profile contract remains valid;
- wired link reconnect -> network restores -> Windows Time remains healthy -> profile remains valid.

A reboot/reconnect is an intentional service interruption. Perform it only when no critical operation is active. The checks must not send broker orders or modify trading authority.

## 11. Exit-Gate validation

During development, structural profile validation may succeed while the Exit Gate remains `BLOCKED`:

```powershell
python .\scripts\validate_v10_node_profile.py $profile --thresholds .\infrastructure\windows\wp5_node_thresholds.json
```

Final WP5 acceptance requires zero computed blockers:

```powershell
python .\scripts\validate_v10_node_profile.py $profile --thresholds .\infrastructure\windows\wp5_node_thresholds.json --require-exit-gate
```

The validator recomputes blockers. Editing the JSON to claim `PASS` cannot bypass the deterministic assessment.

## 12. Troubleshooting rule

When data cannot be queried:

1. preserve `UNKNOWN`/`NOT_RUN`;
2. identify whether the missing fact is a permissions, driver, firmware or sensor limitation;
3. use another read-only supported interface if available;
4. request OWNER action only if the fact cannot be safely established remotely;
5. never disable a safety check merely to close WP5.
