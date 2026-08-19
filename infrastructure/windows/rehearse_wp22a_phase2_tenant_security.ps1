[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PythonPath,
    [ValidateRange(30, 300)][int]$ProbeTimeoutSeconds = 120,
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$oldPgConnectTimeout = $env:PGCONNECT_TIMEOUT
$oldPgCtlTimeout = $env:PGCTLTIMEOUT
$env:PGCONNECT_TIMEOUT = "5"
$env:PGCTLTIMEOUT = "10"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Probe = Join-Path $RepoRoot "scripts\rehearse_v10_wp22a_phase2_tenant_security.py"

function Resolve-PostgresTool {
    param([Parameter(Mandatory = $true)][string]$Name)

    $preferred = Join-Path ${env:ProgramFiles} "PostgreSQL\18\bin\$Name.exe"
    if (Test-Path -LiteralPath $preferred -PathType Leaf) {
        return $preferred
    }
    $command = Get-Command "$Name.exe" -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw "POSTGRES_TOOL_NOT_FOUND:$Name"
    }
    return [string]$command.Source
}

function Get-FreeLoopbackPort {
    $listener = New-Object System.Net.Sockets.TcpListener(
        [System.Net.IPAddress]::Loopback,
        0
    )
    try {
        $listener.Start()
        return ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    }
    finally {
        $listener.Stop()
    }
}

function Stop-ProcessTree {
    param([Parameter(Mandatory = $true)][System.Diagnostics.Process]$Process)

    try {
        if (-not $Process.HasExited) {
            $processId = [int]$Process.Id
            & taskkill.exe /PID $processId /T /F *> $null
            if ($LASTEXITCODE -ne 0 -and -not $Process.HasExited) {
                $Process.Kill()
            }
            [void]$Process.WaitForExit(10000)
        }
    }
    catch {
        # The timeout/failure remains authoritative; cleanup is best-effort.
    }
}

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Reason,
        [ValidateRange(5, 120)][int]$TimeoutSeconds = 30
    )

    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments `
        -PassThru -WindowStyle Hidden
    try {
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            Stop-ProcessTree -Process $process
            throw ($Reason + "_TIMEOUT")
        }
        if ($process.ExitCode -ne 0) {
            throw $Reason
        }
    }
    finally {
        Stop-ProcessTree -Process $process
        $process.Dispose()
    }
}

function Test-PostgresReadyBounded {
    param(
        [Parameter(Mandatory = $true)][string]$PgIsReady,
        [Parameter(Mandatory = $true)][int]$Port
    )

    $arguments = @(
        "--host=127.0.0.1",
        "--port=$Port",
        "--username=wp22a_owner",
        "--dbname=postgres",
        "--timeout=1",
        "--quiet"
    )
    $probe = Start-Process -FilePath $PgIsReady -ArgumentList $arguments `
        -PassThru -WindowStyle Hidden
    try {
        if (-not $probe.WaitForExit(3000)) {
            Stop-ProcessTree -Process $probe
            return $false
        }
        return $probe.ExitCode -eq 0
    }
    finally {
        Stop-ProcessTree -Process $probe
        $probe.Dispose()
    }
}

function Start-TemporaryPostgresBounded {
    param(
        [Parameter(Mandatory = $true)][string]$PgCtl,
        [Parameter(Mandatory = $true)][string]$PgIsReady,
        [Parameter(Mandatory = $true)][string]$DataDirectory,
        [Parameter(Mandatory = $true)][string]$LogPath,
        [Parameter(Mandatory = $true)][int]$Port,
        [ValidateRange(5, 60)][int]$ReadyTimeoutSeconds = 20
    )

    # Do not rely on pg_ctl's own synchronous wait as the only boundary. On the
    # authoritative Windows runner an obsolete exact-head run remained inside
    # that native invocation despite -t/PGCTLTIMEOUT. Launch without waiting,
    # then prove readiness with an independently bounded pg_isready loop.
    $argumentLine = @(
        "start",
        "-D `"$DataDirectory`"",
        "-l `"$LogPath`"",
        "-W",
        "-s",
        "-o `"-h 127.0.0.1 -p $Port`""
    ) -join " "
    $launcher = Start-Process -FilePath $PgCtl -ArgumentList $argumentLine `
        -PassThru -WindowStyle Hidden
    try {
        if (-not $launcher.WaitForExit(10000)) {
            Stop-ProcessTree -Process $launcher
            throw "WP22A_PHASE2_POSTGRES_LAUNCH_TIMEOUT"
        }
        if ($launcher.ExitCode -ne 0) {
            throw "WP22A_PHASE2_POSTGRES_START_FAILED"
        }
    }
    finally {
        Stop-ProcessTree -Process $launcher
        $launcher.Dispose()
    }

    $deadline = [DateTime]::UtcNow.AddSeconds($ReadyTimeoutSeconds)
    do {
        if (Test-PostgresReadyBounded -PgIsReady $PgIsReady -Port $Port) {
            return
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)

    throw "WP22A_PHASE2_POSTGRES_NOT_READY"
}

function Stop-TemporaryPostgresBounded {
    param(
        [Parameter(Mandatory = $true)][string]$PgCtl,
        [Parameter(Mandatory = $true)][string]$DataDirectory
    )

    if (-not (Test-Path -LiteralPath $DataDirectory -PathType Container)) {
        return
    }
    $argumentLine = "stop -D `"$DataDirectory`" -m fast -w -t 10 -s"
    $stopper = Start-Process -FilePath $PgCtl -ArgumentList $argumentLine `
        -PassThru -WindowStyle Hidden
    try {
        if (-not $stopper.WaitForExit(15000)) {
            Stop-ProcessTree -Process $stopper
            return
        }
    }
    finally {
        Stop-ProcessTree -Process $stopper
        $stopper.Dispose()
    }
}

if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "PYTHON_NOT_FOUND"
}
if (-not (Test-Path -LiteralPath $Probe -PathType Leaf)) {
    throw "WP22A_PHASE2_PROBE_NOT_FOUND"
}

$initDb = Resolve-PostgresTool -Name "initdb"
$pgCtl = Resolve-PostgresTool -Name "pg_ctl"
$pgIsReady = Resolve-PostgresTool -Name "pg_isready"
$createdb = Resolve-PostgresTool -Name "createdb"
$psql = Resolve-PostgresTool -Name "psql"

$versionText = (& $psql --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $versionText -notmatch "18\.") {
    throw "POSTGRES_18_REQUIRED"
}

$tempBase = if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) {
    [System.IO.Path]::GetTempPath()
}
else {
    $env:RUNNER_TEMP
}
$root = Join-Path $tempBase ("wp22a-phase2-" + [Guid]::NewGuid().ToString("N"))
$dataDir = Join-Path $root "pgdata"
$logPath = Join-Path $root "postgres.log"
$port = Get-FreeLoopbackPort
$oldDsn = $env:OMNI_CIO_WP22A_PHASE2_DSN
$oldPythonPath = $env:PYTHONPATH
$started = $false
$probeProcess = $null

try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null

    Write-Host "WP22A_PHASE2_STAGE=initdb"
    Invoke-NativeChecked -FilePath $initDb -Arguments @(
        "--pgdata=$dataDir",
        "--username=wp22a_owner",
        "--auth=trust",
        "--encoding=UTF8",
        "--no-sync",
        "--no-instructions"
    ) -Reason "WP22A_PHASE2_INITDB_FAILED" -TimeoutSeconds 45

    # Arm cleanup before any startup attempt. pg_ctl can launch postgres and then
    # fail readiness; cleanup must still attempt a bounded stop in that case.
    $started = $true
    Write-Host "WP22A_PHASE2_STAGE=postgres_start"
    Start-TemporaryPostgresBounded -PgCtl $pgCtl -PgIsReady $pgIsReady `
        -DataDirectory $dataDir -LogPath $logPath -Port $port

    Write-Host "WP22A_PHASE2_STAGE=postgres_ready"
    if (-not (Test-PostgresReadyBounded -PgIsReady $pgIsReady -Port $port)) {
        throw "WP22A_PHASE2_POSTGRES_NOT_READY"
    }

    Write-Host "WP22A_PHASE2_STAGE=database_create"
    Invoke-NativeChecked -FilePath $createdb -Arguments @(
        "--host=127.0.0.1",
        "--port=$port",
        "--username=wp22a_owner",
        "--no-password",
        "wp22a_phase2"
    ) -Reason "WP22A_PHASE2_DATABASE_CREATE_FAILED" -TimeoutSeconds 15

    # The probe deliberately exercises concurrent registration. Bound database
    # lock/statement waits at the PostgreSQL session itself so ThreadPoolExecutor
    # teardown cannot wait indefinitely on a blocked SQL statement.
    $env:OMNI_CIO_WP22A_PHASE2_DSN = (
        "host=127.0.0.1 port=$port user=wp22a_owner " +
        "dbname=wp22a_phase2 connect_timeout=5 " +
        "options='-c statement_timeout=15000 -c lock_timeout=10000'"
    )
    if ([string]::IsNullOrWhiteSpace($oldPythonPath)) {
        $env:PYTHONPATH = $RepoRoot
    }
    else {
        $env:PYTHONPATH = "$RepoRoot;$oldPythonPath"
    }

    # Keep the child process bounded as a second line of defence. A future
    # regression must fail this focused gate instead of monopolizing the single
    # authoritative Lenovo runner until the outer workflow timeout.
    Write-Host "WP22A_PHASE2_STAGE=python_probe"
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $PythonPath
    $startInfo.Arguments = '"' + $Probe.Replace('"', '\"') + '"'
    $startInfo.WorkingDirectory = $RepoRoot
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $probeProcess = New-Object System.Diagnostics.Process
    $probeProcess.StartInfo = $startInfo
    if (-not $probeProcess.Start()) {
        throw "WP22A_PHASE2_PROBE_START_FAILED"
    }
    $stdoutTask = $probeProcess.StandardOutput.ReadToEndAsync()
    $stderrTask = $probeProcess.StandardError.ReadToEndAsync()
    if (-not $probeProcess.WaitForExit($ProbeTimeoutSeconds * 1000)) {
        Stop-ProcessTree -Process $probeProcess
        throw "WP22A_PHASE2_PROBE_TIMEOUT"
    }

    $probeExit = $probeProcess.ExitCode
    $text = ($stdoutTask.GetAwaiter().GetResult() | Out-String).Trim()
    $stderrText = ($stderrTask.GetAwaiter().GetResult() | Out-String).Trim()
    if ($probeExit -ne 0) {
        if ($AsJson -and -not [string]::IsNullOrWhiteSpace($text)) {
            Write-Output $text
        }
        throw "WP22A_PHASE2_PROBE_FAILED"
    }
    if (-not [string]::IsNullOrWhiteSpace($stderrText)) {
        throw "WP22A_PHASE2_PROBE_STDERR_NOT_EMPTY"
    }
    if ([string]::IsNullOrWhiteSpace($text)) {
        throw "WP22A_PHASE2_PROBE_OUTPUT_EMPTY"
    }
    try {
        $parsed = $text | ConvertFrom-Json
    }
    catch {
        throw "WP22A_PHASE2_PROBE_OUTPUT_INVALID"
    }
    if ([string]$parsed.status -ne "PASS") {
        throw "WP22A_PHASE2_PROBE_DID_NOT_PASS"
    }

    if ($AsJson) {
        Write-Output ($parsed | ConvertTo-Json -Compress -Depth 6)
    }
    else {
        Write-Output "WP22A Phase 2 tenant-security rehearsal: PASS"
        Write-Output "Product account isolation: $($parsed.product_accounts_isolated)"
        Write-Output "Provider binding HMAC: $($parsed.provider_binding_hmac)"
        Write-Output "Server session tenant scope: $($parsed.server_session_tenant_scope)"
        Write-Output "Broker PostgreSQL RLS: $($parsed.broker_rls_enabled)"
        Write-Output "Cross-tenant insert rejected: $($parsed.cross_tenant_insert_rejected)"
        Write-Output "Real secrets used: NO"
        Write-Output "Private portfolio data used: NO"
    }
}
finally {
    $env:OMNI_CIO_WP22A_PHASE2_DSN = $oldDsn
    $env:PYTHONPATH = $oldPythonPath
    $env:PGCONNECT_TIMEOUT = $oldPgConnectTimeout
    $env:PGCTLTIMEOUT = $oldPgCtlTimeout
    if ($null -ne $probeProcess) {
        Stop-ProcessTree -Process $probeProcess
        $probeProcess.Dispose()
    }
    if ($started) {
        Write-Host "WP22A_PHASE2_STAGE=postgres_stop"
        try {
            Stop-TemporaryPostgresBounded -PgCtl $pgCtl -DataDirectory $dataDir
        }
        catch {
            # Cleanup is best-effort; the focused failure remains authoritative.
        }
    }
    if (Test-Path -LiteralPath $root) {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
}
