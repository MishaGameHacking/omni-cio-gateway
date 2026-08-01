# Self-hosted Windows runner service

## Purpose

The repository uses the dedicated self-hosted Windows runner label set:

```text
[self-hosted, Windows, X64, omni-cio-ci]
```

Regression Shield requires the listener to remain available between jobs. A
manually started `run.cmd` process is not considered a durable operating mode.
The supported durable mode is the GitHub Actions runner application configured
as a persistent, non-ephemeral Windows service with automatic startup.

This runbook never stores or requests a registration token, repository secret,
runner credential file, broker token or Gateway key.

## Read-only health check

Open PowerShell on the runner machine and run:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive `
  -ExecutionPolicy Bypass `
  -File .\scripts\check_self_hosted_windows_runner_service.ps1 `
  -RunnerRoot C:\actions-runner `
  -ExpectedRunnerName omni-cio-ci `
  -AsJson
```

`ExpectedRunnerName` accepts only letters, digits, `.`, `_` and `-`, with a
maximum length of 64 characters. The script performs ordinal case-insensitive
exact comparisons. Neither caller input nor the `.service` marker is ever used
as a PowerShell wildcard pattern.

Healthy output requires all of the following:

- runner root exists;
- `.runner` configuration marker exists and is no larger than 64 KiB;
- `.runner` is valid JSON with a non-empty `AgentName`;
- configured `AgentName` exactly matches `omni-cio-ci`;
- `Ephemeral` is `false` or omitted from `.runner`;
- `run.cmd` exists;
- `.service` exists, is between 1 byte and 1 KiB, and contains one bounded
  official-style Windows service name;
- `.service` contains no wildcard, whitespace, shell or filter metacharacters;
- the service marker ends with the exact `.omni-cio-ci.service` identity;
- exactly one installed Windows service has the exact declared service name;
- Windows service metadata can be queried for that exact service;
- service state is `Running`;
- service start mode is `Auto`.

The official `actions/runner` implementation persists `AgentName` and
`Ephemeral` in the `.runner` `RunnerSettings` structure. GitHub documents that
an ephemeral runner automatically de-registers after processing one job. That
mode is therefore incompatible with this repository's two-job Regression Shield
unless an external autoscaler creates a fresh replacement runner, which this
repository does not use.

The diagnostic script is read-only. It does not start, stop, install, remove or
reconfigure the runner service. Automatic output contains only bounded booleans,
typed status, the expected runner name and service state; it omits the local
runner root, declared service name, executable path and raw `.runner` or
`.service` values.

## Native Windows inspection

```powershell
Get-Service "actions.runner.*"
Get-CimInstance Win32_Service |
  Where-Object { $_.Name -like "actions.runner.*" } |
  Select-Object Name, State, StartMode, PathName
```

The runner installation directory normally contains `.service` and `.runner`
configuration files. Manual inspection is allowed on the runner machine, but do
not paste their raw contents into GitHub or chat because they may expose
machine, repository or runner configuration details.

Do not print or copy `.credentials`, `.credentials_rsaparams`, registration
tokens, GitHub App credentials, workflow secrets or machine-local paths into
issues, Pull Requests, logs or repository files.

## Recovery when the persistent service exists

Use this recovery path only when the diagnostic reports
`RUNNER_SERVICE_NOT_AUTOMATIC` or `RUNNER_SERVICE_NOT_RUNNING`. Open PowerShell
as Administrator in the runner installation directory:

```powershell
$serviceName = (Get-Content -LiteralPath .\.service -Raw -ErrorAction Stop).Trim()
$expectedSuffix = ".omni-cio-ci.service"

if ($serviceName -notmatch '^actions\.runner\.[A-Za-z0-9._-]{1,480}\.service$') {
    throw "Invalid runner service marker"
}
if (-not $serviceName.EndsWith(
    $expectedSuffix,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Runner service identity mismatch"
}

$service = Get-Service -Name $serviceName -ErrorAction Stop
Set-Service -Name $service.Name -StartupType Automatic
Start-Service -Name $service.Name
Get-Service -Name $service.Name
```

Then run the read-only health check again. The queued Regression Shield job
should be picked up by GitHub after the persistent service reconnects.

Do not use this recovery path for configuration, identity, marker or query
failures. Those states require inspection or runner reconfiguration, not a blind
service restart.

## Recovery when registration must be rebuilt

On Windows, service installation is selected during runner configuration. If
the runner was configured only for interactive execution, GitHub documents that
the runner must be removed from GitHub and configured again, choosing service
mode during `config.cmd`.

The same re-registration boundary applies when `.runner` identifies the runner
as ephemeral or as a different runner name. Configure a persistent runner and
do not use the optional `--ephemeral` registration flag.

Operational sequence:

1. Stop any interactive `run.cmd` listener.
2. In GitHub, remove only the stale `omni-cio-ci` runner registration.
3. Open an Administrator shell on the runner machine.
4. Follow the repository runner setup page to obtain a new short-lived
   registration command.
5. Reconfigure in `C:\actions-runner`, keep the registration persistent, and
   choose Windows service installation.
6. Confirm that `.runner`, `.service` and `run.cmd` were created by the official
   runner configuration flow.
7. Confirm that the service uses automatic startup and is running.
8. Run the read-only diagnostic and require `healthy=true` and
   `runner_ephemeral=false`.
9. Re-run only cancelled or failed GitHub Actions jobs; do not modify code merely
   to create a workflow run.

Registration tokens are short-lived operational inputs and must never be stored
in GitHub, shell history files committed to the repository, screenshots, chat
messages or documentation.

## Failure classification

| Diagnostic code | Meaning | Correct response |
|---|---|---|
| `RUNNER_ROOT_MISSING` | Expected installation directory is absent | Locate or reinstall the official runner application |
| `RUNNER_CONFIGURATION_MISSING` | `.runner` marker is absent | Reconfigure the runner through GitHub |
| `RUNNER_CONFIGURATION_INVALID` | `.runner` is oversized, unreadable, invalid JSON, or has an invalid `AgentName`/`Ephemeral` type | Reconfigure from the official runner package; do not repair secrets/config manually |
| `RUNNER_CONFIGURATION_IDENTITY_MISMATCH` | `.runner` belongs to another runner name | Remove the stale/mismatched registration and configure exact `omni-cio-ci` identity |
| `RUNNER_EPHEMERAL_UNSUPPORTED` | `.runner` has `Ephemeral=true` | Re-register as a persistent Windows-service runner without `--ephemeral` |
| `RUNNER_COMMAND_MISSING` | `run.cmd` is absent | Restore the official runner application package |
| `RUNNER_SERVICE_MARKER_MISSING` | `.service` marker is absent | Reconfigure the runner in Windows service mode |
| `RUNNER_SERVICE_MARKER_INVALID` | `.service` is empty, oversized, unreadable or contains an unsafe/non-standard service name | Reconfigure through the official runner package; do not pass the marker to service commands |
| `RUNNER_SERVICE_MARKER_IDENTITY_MISMATCH` | `.service` declares a different runner identity | Remove the stale/mismatched registration and configure exact `omni-cio-ci` identity |
| `RUNNER_SERVICE_MISSING` | The exact service declared by `.service` is not installed | Reconfigure the runner in service mode |
| `RUNNER_SERVICE_IDENTITY_MISMATCH` | The installed service does not match the exact validated marker and runner suffix | Stop and inspect the registration; do not treat it as `omni-cio-ci` |
| `RUNNER_SERVICE_QUERY_FAILED` | Windows service inventory or metadata could not be read unambiguously | Check Windows service/WMI health and permissions; do not guess a service by wildcard |
| `RUNNER_SERVICE_NOT_AUTOMATIC` | Service will not reliably survive reboot | Set startup type to Automatic using the exact validated service name |
| `RUNNER_SERVICE_NOT_RUNNING` | Registered service is stopped | Start the exact validated service and inspect Windows event/service logs |

## Security boundaries

- repository workflow permissions remain `contents: read`;
- checkout credentials remain non-persistent;
- fork Pull Requests do not execute on the trusted runner;
- the runner host must not contain production broker credentials for CI;
- CI uses only regression placeholders;
- workspace and temporary virtual environments are cleaned after every job;
- raw `.runner` and `.service` content is never emitted by the diagnostic;
- service discovery is exact after bounded marker validation, not wildcard-first;
- `app:app`, the 14 GET Actions and `trading_methods=false` are unchanged.

## Official references

- GitHub Docs: Configuring the self-hosted runner application as a service
  (`https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/configure-the-application`)
- GitHub Docs: Adding self-hosted runners
  (`https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners`)
- GitHub Docs: Self-hosted runners reference (`--ephemeral` behavior)
  (`https://docs.github.com/en/actions/reference/runners/self-hosted-runners`)
- GitHub Docs: Monitoring and troubleshooting self-hosted runners
  (`https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/monitor-and-troubleshoot`)
- Official `actions/runner` source: `RunnerSettings` persistence
  (`https://github.com/actions/runner/blob/main/src/Runner.Common/ConfigurationStore.cs`)
