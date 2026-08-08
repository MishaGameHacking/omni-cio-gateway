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

## 3. Selected prerequisites

Version authority is `docs/architecture/V10_TOOLCHAIN_BASELINE.json`.

WP7 requires exactly:

- Python `3.14.6`;
- Node.js `24.18.0`;
- npm `11.16.0`;
- PostgreSQL `18.4` (major 18).

The repository bootstrap contract additionally pins exact WinGet package identities/versions rather than resolving `latest`.

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

If one or more approved public prerequisites are missing, use the same reviewed script with exact-package installation enabled:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\infrastructure\windows\bootstrap-v10.ps1 `
  -Apply -InstallPrerequisites
```

Do not:

- add token/password/secret arguments;
- paste a GitHub registration token;
- run `git fetch` or `git pull` in the privileged hand-off;
- disable certificate/package hash verification;
- select `latest` package versions;
- manually reconfigure the GitHub runner as a shortcut.

### PostgreSQL installer interaction

If WinGet starts the reviewed PostgreSQL installer and it asks for a local database password, enter it only in the installer UI. Do not paste it into this chat, a GitHub issue, PowerShell, a log or a screenshot.

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

- exact selected prerequisites;
- healthy persistent `omni-cio-ci` runner;
- WP6 runtime/execution roles present, disabled and non-admin;
- all WP7 directories correctly marked;
- exact service-definition/state files;
- future application services still absent;
- privacy flags false;
- no secret-value use.

The authoritative GitHub workflow performs this privacy-safe verification from the CI identity after OWNER apply.

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
| `PREREQUISITES_NOT_EXACT` | One or more selected runtime versions are missing/mismatched | Use reviewed exact install path for missing packages; inspect mismatch rather than silently upgrade/downgrade |
| `RUNNER_NOT_HEALTHY` | Existing durable runner contract is not green | Follow `SELF_HOSTED_WINDOWS_RUNNER_SERVICE.md`; do not re-register blindly |
| `WP6_ROLES_NOT_VALID` | Required least-privilege anchors are missing/enabled/admin/unknown | Stop; repair WP6 boundary rather than recreating it in WP7 |
| `WP7_DIRECTORIES_NOT_READY` | Bootstrap-owned state has not been applied | OWNER apply from reviewed checkout |
| `SERVICE_DEFINITIONS_NOT_READY` | Definition file absent or changed | Stop and inspect repository/local drift |
| `FUTURE_SERVICE_ACTIVATED_EARLY` | Later application service exists before its owning WP | FAIL; remove/resolve unauthorized early activation through reviewed recovery |
| `WINGET_NOT_AVAILABLE` | Windows Package Manager unavailable for a requested install | OWNER action required to restore supported Windows package-management capability |
| `PREREQUISITE_VERSION_MISMATCH:*` | A different version is already installed | Do not auto-replace; inspect compatibility/rollback first |
| cleanup `safe_to_cleanup=false` | WP7 state is unowned or already consumed | Do not delete; classify ownership before recovery |

## 11. Exit Gate evidence

WP7 is accepted only after:

1. hosted/static checks pass;
2. hosted Windows clean-room preview proves non-mutation;
3. exact-head Lenovo preflight is reviewed;
4. OWNER applies the exact reviewed checkout once;
5. the bootstrap proves its second ensure pass makes zero structural changes;
6. authoritative Lenovo `-Verify` passes;
7. no review blockers remain;
8. squash merge completes;
9. post-merge Regression Shield passes on the exact resulting `main` SHA.

Only then may WP8 Local Secret Store and rotation begin.