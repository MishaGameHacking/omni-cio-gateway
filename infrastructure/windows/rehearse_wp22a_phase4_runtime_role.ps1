[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PythonPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PGCONNECT_TIMEOUT = "5"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$PostgresWaitSeconds = 45

function Resolve-PostgresTool {
    param([Parameter(Mandatory = $true)][string]$Name)

    $preferred = Join-Path ${env:ProgramFiles} "PostgreSQL\18\bin\$Name.exe"
    if (Test-Path -LiteralPath $preferred -PathType Leaf) {
        return $preferred
    }
    $command = Get-Command "$Name.exe" -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw "POSTGRES_TOOL_NOT_FOUND"
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

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$Reason = "NATIVE_COMMAND_FAILED",
        [switch]$CaptureOutput
    )

    if ($CaptureOutput) {
        $output = & $FilePath @Arguments 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw $Reason
        }
        return $output
    }

    & $FilePath @Arguments *> $null
    if ($LASTEXITCODE -ne 0) {
        throw $Reason
    }
}

function Start-TemporaryPostgres {
    param(
        [Parameter(Mandatory = $true)][string]$PgCtl,
        [Parameter(Mandatory = $true)][string]$PgIsReady,
        [Parameter(Mandatory = $true)][string]$DataDirectory,
        [Parameter(Mandatory = $true)][string]$LogPath,
        [Parameter(Mandatory = $true)][int]$Port
    )

    $argumentLine = @(
        "start",
        "-D `"$DataDirectory`"",
        "-l `"$LogPath`"",
        "-W",
        "-s",
        "-o `"-h 127.0.0.1 -p $Port`""
    ) -join " "
    $launcher = Start-Process `
        -FilePath $PgCtl `
        -ArgumentList $argumentLine `
        -WindowStyle Hidden `
        -PassThru
    if ($null -eq $launcher) {
        throw "POSTGRES_PG_CTL_PROCESS_MISSING"
    }
    if (-not $launcher.WaitForExit($PostgresWaitSeconds * 1000)) {
        try { $launcher.Kill() } catch { }
        throw "POSTGRES_PG_CTL_LAUNCH_TIMEOUT"
    }
    if ($launcher.ExitCode -ne 0) {
        throw "POSTGRES_PG_CTL_START_FAILED"
    }

    $deadline = [DateTime]::UtcNow.AddSeconds($PostgresWaitSeconds)
    do {
        & $PgIsReady --host=127.0.0.1 --port=$Port --username=phase4_owner `
            --dbname=postgres --timeout=1 --quiet *> $null
        if ($LASTEXITCODE -eq 0) {
            return
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)

    throw "POSTGRES_START_READINESS_TIMEOUT"
}

function Stop-TemporaryPostgres {
    param(
        [string]$PgCtl,
        [string]$DataDirectory
    )

    if (
        [string]::IsNullOrWhiteSpace($PgCtl) -or
        [string]::IsNullOrWhiteSpace($DataDirectory) -or
        -not (Test-Path -LiteralPath $DataDirectory -PathType Container)
    ) {
        return
    }
    try {
        $arguments = "stop -D `"$DataDirectory`" -m fast -w -s"
        $stopper = Start-Process `
            -FilePath $PgCtl `
            -ArgumentList $arguments `
            -WindowStyle Hidden `
            -PassThru
        if ($null -ne $stopper) {
            $null = $stopper.WaitForExit(15000)
        }
    }
    catch {
        # Best effort; temporary-directory cleanup remains fail-closed below.
    }
}

function Invoke-Rehearsal {
    param(
        [Parameter(Mandatory = $true)][string]$DatabaseName,
        [Parameter(Mandatory = $true)][string]$Mode,
        [Parameter(Mandatory = $true)][int]$Port
    )

    $oldDsn = $env:OMNI_CIO_WP13_DSN
    $oldPythonPath = $env:PYTHONPATH
    try {
        $env:OMNI_CIO_WP13_DSN = (
            "host=127.0.0.1 port=$Port user=phase4_owner " +
            "dbname=$DatabaseName connect_timeout=5"
        )
        if ([string]::IsNullOrWhiteSpace($oldPythonPath)) {
            $env:PYTHONPATH = $RepoRoot
        }
        else {
            $env:PYTHONPATH = "$RepoRoot;$oldPythonPath"
        }
        & $PythonPath -m scripts.rehearse_v10_wp22a_phase4_runtime_role $Mode
        if ($LASTEXITCODE -ne 0) {
            throw "PHASE4_POSTGRES_REHEARSAL_FAILED"
        }
    }
    finally {
        $env:OMNI_CIO_WP13_DSN = $oldDsn
        $env:PYTHONPATH = $oldPythonPath
    }
}

if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "PYTHON_NOT_FOUND"
}

$root = $null
$dataDir = $null
$pgCtl = $null
try {
    $initDb = Resolve-PostgresTool -Name "initdb"
    $pgCtl = Resolve-PostgresTool -Name "pg_ctl"
    $pgIsReady = Resolve-PostgresTool -Name "pg_isready"
    $createdb = Resolve-PostgresTool -Name "createdb"
    $psql = Resolve-PostgresTool -Name "psql"

    $clientVersion = Invoke-NativeChecked `
        -FilePath $psql `
        -Arguments @("--version") `
        -CaptureOutput `
        -Reason "POSTGRES_VERSION_FAILED"
    $clientVersionText = ($clientVersion | Out-String).Trim()
    if ($clientVersionText -notmatch "([0-9]+\.[0-9]+)") {
        throw "POSTGRES_VERSION_UNKNOWN"
    }
    if (-not $Matches[1].StartsWith("18.")) {
        throw "POSTGRES_MAJOR_MISMATCH"
    }

    $tempBase = if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) {
        [System.IO.Path]::GetTempPath()
    }
    else {
        $env:RUNNER_TEMP
    }
    $root = Join-Path $tempBase ("wp22a-phase4-pg18-" + [Guid]::NewGuid().ToString("N"))
    $dataDir = Join-Path $root "pgdata"
    $serverLog = Join-Path $root "postgres.log"
    New-Item -ItemType Directory -Path $root -Force | Out-Null

    Invoke-NativeChecked -FilePath $initDb -Arguments @(
        "--pgdata=$dataDir",
        "--username=phase4_owner",
        "--auth=trust",
        "--encoding=UTF8",
        "--no-sync",
        "--no-instructions"
    ) -Reason "INITDB_FAILED"

    $port = Get-FreeLoopbackPort
    Start-TemporaryPostgres `
        -PgCtl $pgCtl `
        -PgIsReady $pgIsReady `
        -DataDirectory $dataDir `
        -LogPath $serverLog `
        -Port $port

    $serverVersion = Invoke-NativeChecked `
        -FilePath $psql `
        -Arguments @(
            "--host=127.0.0.1",
            "--port=$port",
            "--username=phase4_owner",
            "--dbname=postgres",
            "--no-password",
            "--tuples-only",
            "--no-align",
            "--command=SHOW server_version_num"
        ) `
        -CaptureOutput `
        -Reason "POSTGRES_SERVER_VERSION_FAILED"
    $serverVersionText = ($serverVersion | Out-String).Trim()
    $serverVersionNumber = 0
    if (-not [int]::TryParse($serverVersionText, [ref]$serverVersionNumber)) {
        throw "POSTGRES_SERVER_VERSION_INVALID"
    }
    if ([math]::Floor($serverVersionNumber / 10000) -ne 18) {
        throw "POSTGRES_MAJOR_MISMATCH"
    }

    $common = @(
        "--host=127.0.0.1",
        "--port=$port",
        "--username=phase4_owner",
        "--no-password"
    )

    Invoke-NativeChecked `
        -FilePath $createdb `
        -Arguments ($common + @("phase4_creator")) `
        -Reason "PHASE4_CREATOR_DB_CREATE_FAILED"
    Invoke-Rehearsal `
        -DatabaseName "phase4_creator" `
        -Mode "creator-edge" `
        -Port $port

    Invoke-NativeChecked `
        -FilePath $createdb `
        -Arguments ($common + @("phase4_bootstrap")) `
        -Reason "PHASE4_BOOTSTRAP_DB_CREATE_FAILED"
    Invoke-Rehearsal `
        -DatabaseName "phase4_bootstrap" `
        -Mode "bootstrap" `
        -Port $port

    Write-Output "V10_WP22A_PHASE4_WINDOWS_POSTGRES18=PASS"
    Write-Output "POSTGRES_MAJOR=18"
    Write-Output "SYNTHETIC_DATABASE_ONLY=YES"
    Write-Output "REAL_SECRETS_USED=NO"
}
finally {
    Stop-TemporaryPostgres -PgCtl $pgCtl -DataDirectory $dataDir
    if (-not [string]::IsNullOrWhiteSpace($root)) {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $root) {
            throw "POSTGRES_TEMPORARY_STATE_CLEANUP_FAILED"
        }
    }
}
