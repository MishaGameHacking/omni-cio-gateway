# Self-hosted Windows runner service

## Purpose

The repository uses the dedicated self-hosted Windows runner label set:

```text
[self-hosted, Windows, X64, omni-cio-ci]
```

Regression Shield requires the listener to remain available between jobs. A
manually started `run.cmd` process is not considered a durable operating mode.
The supported durable mode is the GitHub Actions runner application configured
as a Windows service with automatic startup.

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

Healthy output requires all of the following:

- runner root exists;
- `.runner` configuration marker exists;
- `run.cmd` exists;
- a matching `actions.runner.*.omni-cio-ci.service` service exists;
- service state is `Running`;
- service start mode is `Auto`.

The diagnostic script is read-only. It does not start, stop, install, remove or
reconfigure the runner service.

## Native Windows inspection

```powershell
Get-Service "actions.runner.*"
Get-CimInstance Win32_Service |
  Where-Object { $_.Name -like "actions.runner.*" } |
  Select-Object Name, State, StartMode, PathName
```

The runner installation directory normally contains a `.service` file with the
exact Windows service name:

```powershell
Get-Content C:\actions-runner\.service
```

Do not print or copy `.credentials`, `.credentials_rsaparams`, registration
tokens, GitHub App credentials or workflow secrets into issues, Pull Requests,
logs or repository files.

## Recovery when the service exists

Run PowerShell as Administrator:

```powershell
$service = Get-Service "actions.runner.*" |
  Where-Object { $_.Name -like "*.omni-cio-ci.service" } |
  Select-Object -First 1

Set-Service -Name $service.Name -StartupType Automatic
Start-Service -Name $service.Name
Get-Service -Name $service.Name
```

Then run the read-only health check again. The queued Regression Shield job
should be picked up by GitHub after the service reconnects.

## Recovery when the service is missing

On Windows, service installation is selected during runner configuration. If
the runner was configured only for interactive execution, GitHub documents that
the runner must be removed and configured again, choosing service mode during
`config.cmd`.

Operational sequence:

1. Stop any interactive `run.cmd` listener.
2. In GitHub, remove only the stale `omni-cio-ci` runner registration.
3. Open an Administrator shell on the runner machine.
4. Follow the repository runner setup page to obtain a new short-lived
   registration command.
5. Reconfigure in `C:\actions-runner` and choose Windows service installation.
6. Confirm that the service uses automatic startup and is running.
7. Run the read-only diagnostic script.
8. Re-run only cancelled or failed GitHub Actions jobs; do not modify code merely
   to create a new workflow run.

Registration tokens are short-lived operational inputs and must never be stored
in GitHub, shell history files committed to the repository, screenshots, chat
messages or documentation.

## Failure classification

| Diagnostic code | Meaning | Correct response |
|---|---|---|
| `RUNNER_ROOT_MISSING` | Expected installation directory is absent | Locate or reinstall the official runner application |
| `RUNNER_CONFIGURATION_MISSING` | `.runner` marker is absent | Reconfigure the runner through GitHub |
| `RUNNER_COMMAND_MISSING` | `run.cmd` is absent | Restore the official runner application package |
| `RUNNER_SERVICE_MISSING` | Interactive-only or removed service | Reconfigure the runner in service mode |
| `RUNNER_SERVICE_NOT_AUTOMATIC` | Service will not reliably survive reboot | Set startup type to Automatic |
| `RUNNER_SERVICE_NOT_RUNNING` | Registered service is stopped | Start the service and inspect Windows event/service logs |

## Security boundaries

- repository workflow permissions remain `contents: read`;
- checkout credentials remain non-persistent;
- fork Pull Requests do not execute on the trusted runner;
- the runner host must not contain production broker credentials for CI;
- CI uses only regression placeholders;
- workspace and temporary virtual environments are cleaned after every job;
- `app:app`, the 14 GET Actions and `trading_methods=false` are unchanged.

## Official references

- GitHub Docs: Configuring the self-hosted runner application as a service
- GitHub Docs: Adding self-hosted runners
- GitHub Docs: Monitoring and troubleshooting self-hosted runners
