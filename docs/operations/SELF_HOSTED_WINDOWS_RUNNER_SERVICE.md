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

From the repository root on the runner machine, run this as one complete
PowerShell command on one physical line:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ".\scripts\check_self_hosted_windows_runner_service.ps1" -RunnerRoot "C:\actions-runner" -ExpectedRunnerName "omni-cio-ci" -AsJson
```

`ExpectedRunnerName` accepts only letters, digits, `.`, `_` and `-`, with a
maximum length of 64 characters. The script performs ordinal case-insensitive
exact comparisons. Neither caller input nor the `.service` marker is ever used
as a PowerShell wildcard pattern.

Healthy output requires all of the following:

- runner root exists;
- `.runner` configuration marker exists, is non-empty and is no larger than
  64 KiB;
- `.runner` is valid JSON with a non-empty runner `agentName`;
- configured runner identity exactly matches `omni-cio-ci`;
- `ephemeral` is `false` or omitted from `.runner`;
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
`Ephemeral` in its `RunnerSettings` model and serializes the settings through
the runner's JSON formatter. The diagnostic resolves the resulting JSON
property names explicitly with ordinal case-insensitive comparison so Windows
PowerShell 5.1 behavior does not depend on property-collection indexing details.

When `.runner` is present but structurally invalid, sanitized
`runner_configuration_error_detail` may report only one of these bounded
classifications: `SIZE_INVALID`, `JSON_INVALID`, `AGENT_NAME_INVALID`,
`EPHEMERAL_INVALID`, or `READ_FAILED`. It never reports the raw `.runner`
content or any URL, ID, path, credential, token, or service name.

GitHub documents that an ephemeral runner automatically de-registers after
processing one job. That mode is therefore incompatible with this repository's
two-job Regression Shield unless an external autoscaler creates a fresh
replacement runner, which this repository does not use.

The diagnostic script is read-only. It does not start, stop, install, remove or
reconfigure the runner service. Automatic output contains only bounded booleans,
typed status, the expected runner name and service state; it omits the local
runner root, declared service name, executable path and raw `.runner` or
`.service` values.

## Native Windows inspection

The following commands are for local human inspection only:

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

The wildcard inspection commands above are never a recovery authority. Never
feed their multi-service output into `Set-Service`, `Start-Service`,
`Stop-Service`, or another mutating command.

## Fail-safe recovery when the persistent service exists

The only repository-supported in-place service recovery is the source-controlled
helper:

`scripts/recover_self_hosted_windows_runner_service.ps1`.

It mechanically runs the read-only diagnostic first and refuses to mutate
anything unless the diagnostic code is exactly one of:

- `RUNNER_SERVICE_NOT_AUTOMATIC`;
- `RUNNER_SERVICE_NOT_RUNNING`.

Configuration, identity, ephemeral, marker, missing-service and service-query
failures are non-recoverable through this helper. They return
`RUNNER_RECOVERY_BLOCKED_BY_DIAGNOSTIC` with `mutations_attempted=false`.

The helper also re-reads the `.service` marker using the absolute
`RunnerRoot`, revalidates its bounded official-style identity, requires exactly
one exact Windows service and exactly one matching `Win32_Service` record, and
uses only that validated immutable service-name string for any mutation. It
never uses a service array or `$service.Name` as mutation authority.

### Preview

From the repository root, run one complete command:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ".\scripts\recover_self_hosted_windows_runner_service.ps1" -RunnerRoot "C:\actions-runner" -ExpectedRunnerName "omni-cio-ci" -AsJson
```

Default mode is read-only preview. If recovery is actually needed, the only
expected preview result is:

- `error_code=RUNNER_SERVICE_RECOVERY_PREVIEW`;
- `diagnostic_error_code` equals one of the two recoverable codes above;
- `recovery_action` is `SET_AUTOMATIC`, `START`, or
  `SET_AUTOMATIC_AND_START`;
- `mutations_attempted=false`.

Any other non-healthy result means stop. Do not continue with hand-written
service commands.

### Apply

Only after an accepted preview, open PowerShell **as Administrator** and run one
complete command from the repository root:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ".\scripts\recover_self_hosted_windows_runner_service.ps1" -RunnerRoot "C:\actions-runner" -ExpectedRunnerName "omni-cio-ci" -Apply -AsJson
```

`-Apply` does not bypass validation. It can only set `StartupType=Automatic`
and/or start the one exact validated runner service. After mutation it reruns
the read-only diagnostic and requires the final postcondition
`healthy=true`, `service_state=Running`, and `service_start_mode=Auto`.

The helper never stops, removes, installs or re-registers a service. It never
edits `.runner`, `.service`, `.credentials`, or runner registration state.

Do not copy internal `Set-Service` or `Start-Service` implementation lines from
the helper into an interactive shell. Do not continue a partially failed
manual sequence using variables left over in the current PowerShell session.
Each supported recovery attempt is a fresh invocation of the source-controlled
helper.

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
| `RUNNER_CONFIGURATION_INVALID` | `.runner` is empty/oversized, unreadable, invalid JSON, or has an invalid runner-name/ephemeral type | Use sanitized `runner_configuration_error_detail`; do not repair private runner config manually |
| `RUNNER_CONFIGURATION_IDENTITY_MISMATCH` | `.runner` belongs to another runner name | Remove the stale/mismatched registration and configure exact `omni-cio-ci` identity |
| `RUNNER_EPHEMERAL_UNSUPPORTED` | `.runner` has `ephemeral=true` | Re-register as a persistent Windows-service runner without `--ephemeral` |
| `RUNNER_COMMAND_MISSING` | `run.cmd` is absent | Restore the official runner application package |
| `RUNNER_SERVICE_MARKER_MISSING` | `.service` marker is absent | Reconfigure the runner in Windows service mode |
| `RUNNER_SERVICE_MARKER_INVALID` | `.service` is empty, oversized, unreadable or contains an unsafe/non-standard service name | Reconfigure through the official runner package; do not pass the marker to service commands |
| `RUNNER_SERVICE_MARKER_IDENTITY_MISMATCH` | `.service` declares a different runner identity | Remove the stale/mismatched registration and configure exact `omni-cio-ci` identity |
| `RUNNER_SERVICE_MISSING` | The exact service declared by `.service` is not installed | Reconfigure the runner in service mode |
| `RUNNER_SERVICE_IDENTITY_MISMATCH` | The installed service does not match the exact validated marker and runner suffix | Stop and inspect the registration; do not treat it as `omni-cio-ci` |
| `RUNNER_SERVICE_QUERY_FAILED` | Windows service inventory or metadata could not be read unambiguously | Check Windows service/WMI health and permissions; do not guess a service by wildcard |
| `RUNNER_SERVICE_NOT_AUTOMATIC` | Exact validated service will not reliably survive reboot | Use the source-controlled recovery helper |
| `RUNNER_SERVICE_NOT_RUNNING` | Exact validated service is stopped | Use the source-controlled recovery helper |

Recovery-specific results are deliberately narrower:

| Recovery code | Meaning |
|---|---|
| `RUNNER_RECOVERY_BLOCKED_BY_DIAGNOSTIC` | Diagnostic state is not one of the two safe in-place recovery states; zero mutations are attempted |
| `RUNNER_SERVICE_RECOVERY_PREVIEW` | Validation passed and a bounded exact-service recovery action is available, but `-Apply` was not supplied |
| `RUNNER_SERVICE_RECOVERY_ADMIN_REQUIRED` | `-Apply` was requested for a valid recovery action, but the shell is not elevated; zero mutations are attempted |
| `RUNNER_SERVICE_RECOVERY_MUTATION_FAILED` | The single-target mutation failed; inspect the sanitized `mutation_stage`, do not execute manual fallback commands |
| `RUNNER_SERVICE_RECOVERY_POSTCONDITION_FAILED` | A mutation ran but final read-only health verification did not become healthy; stop and inspect before any further action |

## Security boundaries

- repository workflow permissions remain `contents: read`;
- checkout credentials remain non-persistent;
- fork Pull Requests do not execute on the trusted runner;
- the runner host must not contain production broker credentials for CI;
- CI uses only regression placeholders;
- workspace and temporary virtual environments are cleaned after every job;
- raw `.runner` and `.service` content is never emitted by the diagnostic or
  recovery helper;
- service discovery is exact after bounded marker validation, not wildcard-first;
- recovery is preview-by-default, `-Apply` requires elevation, and mutation is
  limited to one exact validated service;
- configuration/identity/marker/query failures cannot fall through into service
  mutation;
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
