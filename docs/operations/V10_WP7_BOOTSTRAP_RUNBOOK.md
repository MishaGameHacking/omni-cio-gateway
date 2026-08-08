# Omni-CIO V10 — WP7 One-Time Bootstrap Runbook

Status: **WP7 implementation runbook / no real secrets**

## 1. Purpose

WP7 turns the first Lenovo V10 infrastructure setup into one reviewed, repeatable PowerShell bootstrap instead of a long manual configuration checklist.

The bootstrap is dry-run/preview by default and is idempotent. It prepares only the WP7 infrastructure foundation. It does not activate Core/Web/Telegram/AI/execution services and does not provision any real secret.

## 2. Protected boundaries

The following remain outside WP7 mutation authority:

- `C:\actions-runner\.runner`, `.credentials`, `.credentials_rsaparams`, `.service` and runner registration;
- `C:\ProgramData\OmniCIO\secrets` and all future WP8 secret values;
- WP6-owned runtime/execution role creation and runner-root/secret-boundary ACL ownership;
- current V9 Render `app:app` runtime and `trading_methods=false` contract;
- broker/Telegram credentials, private DB payloads and portfolio data;
- future Windows application-service activation owned by later work packages.

WP7 reuses the accepted `omni-cio-runtime` and `omni-cio-execution` disabled non-admin role anchors. It refuses apply if those WP6 postconditions are absent.

The WP7 runner probe deliberately does **not** read `.runner`, `.service` or credential material after WP6 hardening. It discovers the standard `actions.runner.*` Windows service through the service manager, binds it to the reviewed runner-name suffix and `C:\actions-runner` service path, requires running/automatic state and a non-admin service identity, and requires the executing CI process to match that service identity. The probe emits booleans/error codes only.

## 3. Selected prerequisites

Version authority is `docs/architecture/V10_TOOLCHAIN_BASELINE.json`.

WP7 requires exactly:

- Python `3.14.6`;
- Node.js `24.18.0`;
- npm `11.16.0`;
- PostgreSQL `18.4` (major 18).

These are the **accepted WP2 project baseline**, not an instruction to resolve the newest upstream release during bootstrap. A later toolchain upgrade requires its own compatibility/recovery evidence.

### Python installation policy

Python is not installed through `Python.Python.3.14 --scope machine`. The current upstream WinGet package path has a documented scope defect in which a requested machine install can be recorded/resolved as user scope. WP7 therefore uses the official Python.org traditional x64 installer for the frozen `3.14.6` baseline.

The repository contract pins:

- exact URL: `https://www.python.org/ftp/python/3.14.6/python-3.14.6-amd64.exe`;
- SHA-256: `14B3E9A710A3FCF0BD9B55AB6B60412BD91227563F813FC49040CABC0209E0BD`;
- all-users installation (`InstallAllUsers=1`);
- no user PATH mutation (`PrependPath=0`);
- SHA-256 verification before execution;
- valid Authenticode signature before execution.

The downloaded installer is temporary and is removed after the installation attempt. WP7 detects the machine installation at `C:\Program Files\Python314\python.exe` before consulting any per-user Python launcher result.

### Node.js and PostgreSQL installation policy

Node.js and PostgreSQL continue to use exact WinGet package identities and exact versions with `--exact`, `--version`, `--source winget` and `--scope machine`. No package is resolved from `latest`.

The bootstrap never passes a password/token/secret as a command-line argument. If the official PostgreSQL installer needs a local database password, it is entered only in that installer UI; it is never typed into the PowerShell command, printed by the bootstrap or stored in GitHub. WP7 does not create an Omni-CIO application schema or private database payload.

## 4. Preview — safe default

From a reviewed checkout:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\infrastructure\windows\bootstrap-v10.ps1
```

Preview does not mutate the machine. It reports only bounded prerequisite states, runner health, role booleans, WP7 owned-state booleans and reason codes.

Expected pre-apply state may be `OWNER_ACTION_REQUIRED`; that is not permission to weaken a check.

Machine-readable preview:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\infrastructure\windows\bootstrap-v10.ps1 -AsJson
```

## 5. OWNER apply hand-off

The privileged hand-off uses the already checked-out exact PR merge ref left by the authoritative Lenovo workflow. Do not use interactive `git fetch` or `git pull` in the elevated step.

Open **PowerShell as Administrator**:

```powershell
Set-Location "C:\actions-runner\_work\omni-cio-gateway\omni-cio-gateway"
git rev-parse HEAD
```

The SHA must exactly equal the reviewed merge SHA from the latest completed exact-head WP7 Lenovo audit/check run before applying.

If prerequisites are already exact:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\infrastructure\windows\bootstrap-v10.ps1 -Apply
```

If one or more approved public prerequisites are missing or exist only in a non-machine-visible user location, use the same reviewed script with exact prerequisite installation enabled:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\infrastructure\windows\bootstrap-v10.ps1 `
  -Apply -InstallPrerequisites
```

This option may access only the reviewed public package/installer sources described in the committed contract. It does not accept or retrieve an Omni-CIO secret.

Do not:

- add token/password/secret arguments;
- paste a GitHub registration token;
- run `git fetch` or `git pull` in the privileged hand-off;
- disable certificate, Authenticode or package-hash verification;
- select `latest` package versions;
- manually reconfigure the GitHub runner as a shortcut.

### PostgreSQL installer interaction

If WinGet starts the reviewed PostgreSQL installer and it asks for a local database password, enter it only in the installer UI. Do not paste it into chat, a GitHub issue, PowerShell, a log or a screenshot.

WP7 records no password value. Application DB schema/credentials/private data remain outside this WP.

## 6. Idempotence proof

Each successful `-Apply` performs the owned-state ensure pass twice. Acceptance requires:

```text
WP7 bootstrap second-pass structural changes: 0
WP7 bootstrap status: PASS
Idempotence verified: True
Real secret values used: NO
```

Re-running the same reviewed `-Apply` over an already bootstrapped node must also complete with no duplicate directory/service-definition state.

The bootstrap owns only:

```text
C:\ProgramData\OmniCIO\bootstrap
C:\ProgramData\OmniCIO\runtime
C:\ProgramData\OmniCIO\data
C:\ProgramData\OmniCIO\logs
C:\ProgramData\OmniCIO\services
```

Each owned directory carries the fixed non-secret WP7 marker. A pre-existing unmarked directory is a blocker; the script does not adopt it.

## 7. Service definitions are not services

WP7 stores future service **definitions only** for:

- Core runtime;
- Web/API;
- Research/AI;
- isolated execution.

No `New-Service`, `sc.exe create` or `Start-Service` action for those application services occurs in WP7. Their absence is an acceptance postcondition. Autostart/supervision belongs to WP9 and component runtime activation belongs to later owning WPs.

## 8. Verification

Non-mutating verification:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\infrastructure\windows\bootstrap-v10.ps1 -Verify
```

WP7 verification requires simultaneously:

- exact selected prerequisites from machine-visible locations;
- healthy persistent `omni-cio-ci` Windows service without reading protected runner-private configuration;
- WP6 runtime/execution roles present, disabled and non-admin;
- all WP7 directories correctly marked;
- exact service-definition/state files;
- future application services still absent;
- privacy flags false;
- no secret-value use.

The authoritative GitHub workflow performs this privacy-safe verification from the CI service identity after OWNER apply.

## 9. Guarded cleanup / rollback

Preview cleanup:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\infrastructure\windows\rollback_wp7_bootstrap.ps1
```

Actual cleanup before WP7 is consumed by later accepted work:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\infrastructure\windows\rollback_wp7_bootstrap.ps1 -Apply
```

Cleanup refuses to run if:

- a WP7 path lacks the ownership marker;
- an owned path contains unexpected files/directories;
- any future application service already exists;
- state changes between preflight and removal.

Cleanup deliberately leaves public prerequisites installed. It does not alter WP6 users/ACLs, runner registration/credentials, the WP8 secret boundary or V9 runtime.

## 10. Failure classification

| Code/state | Meaning | Response |
|---|---|---|
| `PREREQUISITES_NOT_EXACT` | One or more selected runtime versions are missing/mismatched/not machine-visible | Use the reviewed exact install path; inspect a real machine-version mismatch rather than silently replacing it |
| `PYTHON_INSTALLER_URL_POLICY_MISMATCH` | Contract URL is not the reviewed Python.org artifact | Stop; review repository drift |
| `PYTHON_INSTALLER_HASH_POLICY_INVALID` | Contract SHA-256 is malformed | Stop; review repository drift |
| `PYTHON_INSTALLER_SHA256_MISMATCH` | Download does not match committed SHA-256 | Delete/stop; do not execute the artifact |
| `PYTHON_INSTALLER_AUTHENTICODE_INVALID` | Windows cannot validate the downloaded installer signature | Stop; do not execute the artifact |
| `RUNNER_NOT_HEALTHY` | Existing durable runner service contract is not green | Inspect service/identity state; do not re-register blindly |
| `WP6_ROLES_NOT_VALID` | Required least-privilege anchors are missing/enabled/admin/unknown | Stop; repair WP6 boundary rather than recreating it in WP7 |
| `WP7_DIRECTORIES_NOT_READY` | Bootstrap-owned state has not been applied | OWNER apply from reviewed checkout |
| `SERVICE_DEFINITIONS_NOT_READY` | Definition file absent or changed | Stop and inspect repository/local drift |
| `FUTURE_SERVICE_ACTIVATED_EARLY` | Later application service exists before its owning WP | FAIL; remove/resolve unauthorized early activation through reviewed recovery |
| `WINGET_NOT_AVAILABLE` | Windows Package Manager unavailable for Node/PostgreSQL install | OWNER action required to restore supported package-management capability |
| `PREREQUISITE_VERSION_MISMATCH:*` | A different machine-visible version is already installed | Do not auto-replace; inspect compatibility/rollback first |
| cleanup `safe_to_cleanup=false` | WP7 state is unowned or already consumed | Do not delete; classify ownership before recovery |

## 11. Upstream references captured during WP7 hardening

- Python Windows installer documentation: traditional installer supports `/quiet` plus `InstallAllUsers=1` and machine-wide default target selection.
- Python `3.14.6` official release artifact and checksum are the source pinned in the machine-readable contract.
- Microsoft `winget-pkgs` issue `#355596` documents the current `Python.Python.3.14 --scope machine` user-scope defect that WP7 avoids rather than working around after installation.
- GitHub's Windows self-hosted runner documentation exposes `Get-Service "actions.runner.*"` as the service-health surface; WP7 uses the service manager instead of reading WP6-protected runner-private files.

These references justify the installer transport and runner audit surface only. The selected V10 runtime version remains governed by the accepted WP2 toolchain baseline.

## 12. Exit Gate evidence

WP7 is accepted only after:

1. hosted/static checks pass;
2. hosted Windows clean-room preview proves non-mutation and PowerShell 5.1 parsing;
3. exact-head Lenovo preflight is reviewed;
4. OWNER applies the exact reviewed checkout once;
5. the bootstrap proves its second ensure pass makes zero structural changes;
6. authoritative Lenovo `-Verify` passes;
7. no review blockers remain;
8. squash merge completes;
9. post-merge Regression Shield passes on the exact resulting `main` SHA.

Only then may WP8 Local Secret Store and rotation begin.
