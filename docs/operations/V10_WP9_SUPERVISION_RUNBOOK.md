# V10 WP9 — Autostart, supervision and self-healing runbook

This runbook is limited to WP9. It does not activate Core/Web/Telegram/Watchtower/AI product runtimes, the execution contour, broker write, or any Real-money capability.

## Safety boundary

- Use only the exact reviewed PR merge checkout SHA published in PR #259 before OWNER apply.
- Run mutation commands only from an elevated local PowerShell on the Lenovo.
- Do not use `git pull` / `git fetch` during the reviewed handoff.
- Do not paste or enter broker, Telegram, AI, encryption, database or API credential values.
- WP9 acceptance needs no real credential value.
- Do not manually enable the sealed `OmniCIO.V10.CoreApi`, `.Web`, `.Telegram`, `.Watchtower` or `.AIWorker` task slots.
- Do not create/enable an execution task.
- PostgreSQL 18 is observed/readiness-probed only; the WP9 rehearsal does not stop the production database service.

## Non-mutating preview

From repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\provision_wp9_supervision.ps1
```

Before OWNER apply, `OWNER_ACTION_REQUIRED` is expected. Preview must not create the WP9 ProgramData root or Scheduled Tasks.

## Reviewed OWNER acceptance command

Only after PR #259 remote/hosted/self-hosted gates are green and the exact merge checkout SHA is published, the OWNER will use one elevated PowerShell sequence:

```powershell
Set-Location "C:\actions-runner\_work\omni-cio-gateway\omni-cio-gateway"
git rev-parse HEAD
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\provision_wp9_supervision.ps1 -Apply -RunRehearsals -ArmReboot -RestartComputer
```

The SHA printed by `git rev-parse HEAD` must exactly match the reviewed merge checkout published in PR #259. If it does not, stop and do not run the provisioner.

The provisioner is required to refuse reboot unless:

- inherited WP7 and WP8 verification passes;
- OWNER administrator authority is present;
- the WP9 layout/tasks converge idempotently with second-pass structural changes `0`;
- current status is safely `HEALTHY` or truthfully `DEGRADED`;
- all five synthetic bounded-restart rehearsals pass;
- the synthetic dependency-loss/recovery rehearsal passes;
- reboot evidence is armed.

The machine then schedules a full reboot. Do **not** manually open/start Omni-CIO application terminals after Windows returns. The existing self-hosted runner and the WP9 health supervisor must recover automatically.

## Expected pre-reboot result

Because later product runtimes are intentionally not implemented yet, the expected accepted current health is normally:

```text
WP9 current health: DEGRADED
```

That is correct. A fake `HEALTHY` result while later product slots are absent would be a defect.

Expected safety lines include:

```text
WP9 second-pass structural changes: 0
Restart rehearsal: True
Dependency rehearsal: True
Reboot armed: True
Future product slots sealed: True
Execution task created: False
Real secret values used: NO
Real-money authority changed: NO
```

## Post-reboot acceptance

After Windows returns:

1. Do not manually launch application terminals.
2. Allow the existing GitHub self-hosted runner service to reconnect.
3. The exact-head `V10 WP9 Supervision Audit` is rerun from GitHub.
4. The audit must prove that the WP9 health supervisor wrote status after the new Windows boot, not before it.
5. The accepted status may be `DEGRADED` while later product slots remain sealed.

The audit also verifies:

- health task present/enabled under `LOCAL SERVICE`;
- five future product slots present but disabled;
- bounded restart policy retained;
- no execution task;
- WP6 runtime/execution anchors still disabled/non-admin;
- no LocalService read grant on WP8 protected payloads;
- restart/dependency rehearsal evidence PASS;
- all privacy flags false.

## Local verify

After apply but before/after reboot an OWNER can inspect the provisioner status without mutation:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\provision_wp9_supervision.ps1 -Verify
```

`OWNER_REBOOT_REQUIRED` is valid before the reviewed reboot. `PASS` is valid only after the supervisor has observed a new boot.

## Rollback preview

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\rollback_wp9_supervision.ps1
```

Rollback is marker guarded. It refuses unowned task/root collisions.

## Rollback apply

Only if WP9 rollback is explicitly required, from elevated PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\rollback_wp9_supervision.ps1 -Apply
```

Rollback removes only WP9 marker-owned tasks/files. It must preserve PostgreSQL, the GitHub runner, WP6 identities/ACLs, WP7 bootstrap/prerequisites, WP8 secret-store state and the V9 recovery/production path.

## Exit Gate

WP9 is PASS only after exact-head CI, reviewed OWNER apply/rehearsals, a full reboot, automatic runner return and fresh post-boot `HEALTHY`/`DEGRADED` evidence all pass. WP9A remains locked until then.
