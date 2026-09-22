# Self-hosted Windows runner service

## Purpose

The repository uses the dedicated self-hosted Windows runner label set:

```text
[self-hosted, Windows, X64, omni-cio-ci]
```

Regression Shield requires the listener to remain available between jobs. A
manually started `run.cmd` process is not a durable operating mode. The supported
mode is the official GitHub Actions runner configured as a persistent,
non-ephemeral Windows service with automatic startup.

This runbook never stores or requests a registration token, repository secret,
runner credential file, broker token or Gateway key.

## Read-only health check

From the repository root on the runner machine, use one complete physical line:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ".\scripts\check_self_hosted_windows_runner_service.ps1" -RunnerRoot "C:\actions-runner" -ExpectedRunnerName "omni-cio-ci" -AsJson
```

`ExpectedRunnerName` accepts only letters, digits, `.`, `_` and `-`, maximum 64
characters. Comparisons are ordinal case-insensitive. Caller input and marker
content are never used as wildcard mutation targets.

Healthy output requires:

- runner root exists;
- `.runner` exists, is non-empty, at most 64 KiB, valid JSON, and contains the
  expected runner `AgentName` plus `Ephemeral=false` or no `Ephemeral` field;
- `run.cmd` exists;
- `.service` exists, is non-empty and at most 1 KiB;
- `.service` contains exactly one bounded official Windows service name;
- the declared Windows service identity is the expected `omni-cio-ci` runner;
- exactly one installed Windows service and one `Win32_Service` record match the
  exact declared name;
- the service executable is exactly `<RunnerRoot>\bin\RunnerService.exe` after
  Windows path normalization; extra command-line arguments or another runner
  installation root are rejected;
- service state is `Running` and start mode is `Auto`.

The filename `.service` must not be confused with its content. Official
`actions/runner` Windows code writes the service name as
`actions.runner.{repo-or-org}.{runner-name}`; there is **no `.service` suffix in
the Windows service name**. The official implementation constrains the Windows
service name to at most 80 characters and writes the `.service` marker as a
hidden UTF-8 file.

The official `NativeWindowsServiceHelper` installs the service executable from
the runner's own `bin\RunnerService.exe`. The repository diagnostic therefore
binds the exact service name to the exact configured `RunnerRoot` executable
before treating service identity as valid. `PathName` is used only internally
for this comparison and is never emitted in diagnostic or recovery JSON.

Likewise, `.runner` is a hidden runner configuration file. The diagnostic reads
both hidden markers through direct .NET file I/O, matching the class of I/O used
by the official runner and avoiding PowerShell provider hidden-file semantics.
Windows ACLs are still enforced; there is no permission bypass.

When `.runner` is structurally invalid, the only bounded
`runner_configuration_error_detail` values are `SIZE_INVALID`, `READ_FAILED`,
`JSON_INVALID`, `AGENT_NAME_INVALID`, and `EPHEMERAL_INVALID`. Raw configuration,
service name, paths, URLs, IDs, tokens and credentials are never emitted.

The diagnostic is read-only. It never starts, stops, installs, removes or
reconfigures a service.

## Native Windows inspection

These are local human-inspection commands only:

```powershell
Get-Service "actions.runner.*"
Get-CimInstance Win32_Service |
  Where-Object { $_.Name -like "actions.runner.*" } |
  Select-Object Name, State, StartMode, PathName
```

Never feed wildcard or multi-service inspection output into `Set-Service`,
`Start-Service`, `Stop-Service`, or another mutation command.

Do not paste raw `.runner`, `.service`, `.credentials`,
`.credentials_rsaparams`, registration tokens, GitHub App credentials, workflow
secrets or machine-local paths into GitHub, chat, screenshots or evidence.

## T-Bank package CA trust boundary

Dependency installation has an independent machine-trust prerequisite. Verify it
read-only with:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ".\scripts\check_v10_tbank_ca_trust.ps1" -AsJson
```

If this reports `TBANK_CA_TRUST_STORE_NOT_READY`, do not rerun dependency jobs
blindly and do not disable TLS validation. Follow
`docs/operations/V10_TBANK_CA_TRUST_RUNBOOK.md`. Certificate-store mutation is a
separate OWNER/Administrator action and is never granted to the ordinary
GitHub Actions runner.

## Fail-safe recovery

The only repository-supported in-place recovery is:

`scripts/recover_self_hosted_windows_runner_service.ps1`.

It always executes the read-only diagnostic first and mechanically refuses all
mutations unless the exact diagnostic code is one of:

- `RUNNER_SERVICE_NOT_AUTOMATIC`;
- `RUNNER_SERVICE_NOT_RUNNING`.

All configuration, identity, ephemeral, marker, missing-service and query
failures return `RUNNER_RECOVERY_BLOCKED_BY_DIAGNOSTIC` with
`mutations_attempted=false`.

Before any mutation the helper independently re-reads the absolute `.service`
marker through direct .NET I/O, validates the official bounded
`actions.runner.{repo-or-org}.{runner-name}` shape and exact runner-name suffix,
requires exactly one matching Windows service plus one matching
`Win32_Service` record, and independently requires that service's executable to
be exactly `<RunnerRoot>\bin\RunnerService.exe`. A stale marker that names a
service from another runner installation therefore cannot become mutation
authority.

Only the immutable validated service-name string can become mutation authority;
an array or `$service.Name` never can. Neither the exact service name nor its
executable path is emitted by the helper.

### Preview

Run from the repository root:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ".\scripts\recover_self_hosted_windows_runner_service.ps1" -RunnerRoot "C:\actions-runner" -ExpectedRunnerName "omni-cio-ci" -AsJson
```

Preview is read-only. If repair is actually needed, the only acceptable preview
has all of these properties:

- `error_code=RUNNER_SERVICE_RECOVERY_PREVIEW`;
- `diagnostic_error_code` is one of the two recoverable codes above;
- `recovery_action` is `SET_AUTOMATIC`, `START`, or
  `SET_AUTOMATIC_AND_START`;
- `mutations_attempted=false`.

Any other non-healthy result means stop. Do not continue with hand-written
service commands or variables left in the current shell.

### Apply

Only after an accepted preview, open PowerShell **as Administrator** and run one
complete command from the repository root:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ".\scripts\recover_self_hosted_windows_runner_service.ps1" -RunnerRoot "C:\actions-runner" -ExpectedRunnerName "omni-cio-ci" -Apply -AsJson
```

`-Apply` cannot bypass the diagnostic contract. It can only set
`StartupType=Automatic` and/or start the one exact validated runner service.
After mutation it reruns the read-only diagnostic and requires
`healthy=true`, `service_state=Running`, and `service_start_mode=Auto`.

The helper never stops, removes, installs or re-registers a runner service and
never edits `.runner`, `.service`, `.credentials`, or registration state.

## Re-registration boundary

If the runner configuration/identity/marker is missing or invalid, if the
runner is ephemeral, if the exact declared service is absent, or if its
executable is not the exact `RunnerService.exe` under the configured runner
root, do not use the in-place helper. Re-registration is a separate OWNER/admin
operation through the official GitHub runner configuration flow.

On Windows, service installation is selected during runner configuration. If a
runner was configured only for interactive execution, GitHub documents that it
must be removed and configured again with Windows service mode selected. Do not
use `--ephemeral` for this persistent runner.

Safe re-registration sequence, only when explicitly required:

1. Stop any interactive `run.cmd` listener.
2. Remove only the stale `omni-cio-ci` runner registration in GitHub.
3. Open an Administrator shell on the runner machine.
4. Obtain a fresh short-lived registration command from the repository runner
   setup page.
5. Configure inside `C:\actions-runner`, persistent and as a Windows service.
6. Confirm `.runner`, `.service`, and `run.cmd` were created by the official
   runner flow.
7. Run the repository read-only diagnostic and require `healthy=true` and
   `runner_ephemeral=false`.
8. Re-run only jobs that actually need retrying.

Registration tokens must never be stored in GitHub, committed shell history,
screenshots, chat or documentation.

## Failure classification

| Diagnostic code | Meaning | Correct response |
|---|---|---|
| `RUNNER_ROOT_MISSING` | Runner installation root is absent | Locate/reinstall official runner |
| `RUNNER_CONFIGURATION_MISSING` | `.runner` is absent | Reconfigure through GitHub |
| `RUNNER_CONFIGURATION_INVALID` | `.runner` is empty/oversized/unreadable/invalid JSON or has invalid identity/ephemeral structure | Use only sanitized detail; do not repair private config manually |
| `RUNNER_CONFIGURATION_IDENTITY_MISMATCH` | `.runner` belongs to another runner identity | Reconfigure exact `omni-cio-ci` identity |
| `RUNNER_EPHEMERAL_UNSUPPORTED` | Runner is ephemeral | Re-register persistent, without `--ephemeral` |
| `RUNNER_COMMAND_MISSING` | `run.cmd` is absent | Restore official runner package |
| `RUNNER_SERVICE_MARKER_MISSING` | `.service` marker is absent | Reconfigure service mode |
| `RUNNER_SERVICE_MARKER_INVALID` | Marker is unreadable/oversized or not an official bounded service-name shape | Reconfigure; never guess by wildcard |
| `RUNNER_SERVICE_MARKER_IDENTITY_MISMATCH` | Marker is valid-shaped but not the expected runner identity | Inspect/reconfigure exact identity |
| `RUNNER_SERVICE_MISSING` | Exact declared Windows service is absent | Reconfigure service mode |
| `RUNNER_SERVICE_IDENTITY_MISMATCH` | Installed service name or executable is not the exact validated marker plus `<RunnerRoot>\bin\RunnerService.exe` identity | Stop and inspect/reconfigure registration; do not mutate it |
| `RUNNER_SERVICE_QUERY_FAILED` | Exact service metadata could not be read unambiguously | Inspect Windows service/WMI health |
| `RUNNER_SERVICE_NOT_AUTOMATIC` | Exact service is not automatic | Use source-controlled recovery helper |
| `RUNNER_SERVICE_NOT_RUNNING` | Exact service is stopped | Use source-controlled recovery helper |

Recovery-specific results:

| Recovery code | Meaning |
|---|---|
| `RUNNER_RECOVERY_BLOCKED_BY_DIAGNOSTIC` | State is not one of the two safe recovery states; zero mutations |
| `RUNNER_RECOVERY_SERVICE_IDENTITY_MISMATCH` | Revalidation found a service-name or executable-path identity mismatch; zero mutations |
| `RUNNER_SERVICE_RECOVERY_PREVIEW` | Exact bounded repair is available; preview made zero mutations |
| `RUNNER_SERVICE_RECOVERY_ADMIN_REQUIRED` | Valid `-Apply` requested without elevation; zero mutations |
| `RUNNER_SERVICE_RECOVERY_MUTATION_FAILED` | Single-target mutation failed; do not hand-enter fallback commands |
| `RUNNER_SERVICE_RECOVERY_POSTCONDITION_FAILED` | Mutation ran but final health contract did not become healthy; stop and inspect |

## Security boundaries

- workflow permissions remain `contents: read`;
- checkout credentials are non-persistent;
- fork PRs do not execute on the trusted runner;
- the runner host must not hold production broker credentials for CI;
- CI uses regression placeholders only;
- workspace and temporary environments are cleaned after jobs;
- raw `.runner`/`.service` content is never emitted by diagnostic or recovery;
- exact `Win32_Service.PathName` is used only internally and is never emitted;
- recovery is preview-by-default and `-Apply` requires elevation;
- mutations are limited to one exact service whose name and executable path are independently validated;
- configuration/identity/marker/query failures cannot fall through to mutation;
- `app:app`, the 14 GET Actions and `trading_methods=false` remain unchanged.

## Official references

- GitHub Docs: configuring the self-hosted runner application as a service;
- GitHub Docs: adding self-hosted runners;
- GitHub Docs: self-hosted runners reference (`--ephemeral` behavior);
- GitHub Docs: monitoring/troubleshooting self-hosted runners;
- official `actions/runner` source: `ConfigurationStore.cs`,
  `WindowsServiceControlManager.cs`, `ServiceControlManager.cs`, and
  `NativeWindowsServiceHelper.cs`.