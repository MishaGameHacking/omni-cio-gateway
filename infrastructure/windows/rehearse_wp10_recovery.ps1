[CmdletBinding()]
param(
    [string]$PythonPath,
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PGCONNECT_TIMEOUT = "5"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$BackupRunner = Join-Path $PSScriptRoot "run_wp10_backup.ps1"
$BundleTool = Join-Path $RepoRoot "scripts\v10_wp10_backup_bundle.py"
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

function Resolve-Python {
    param([string]$ExplicitPath)
    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        if (-not (Test-Path -LiteralPath $ExplicitPath -PathType Leaf)) {
            throw "PYTHON_NOT_FOUND"
        }
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }
    $preferred = "C:\Program Files\Python314\python.exe"
    if (Test-Path -LiteralPath $preferred -PathType Leaf) {
        return $preferred
    }
    try {
        $candidate = & py.exe -3.14 -c "import sys; print(sys.executable)" 2>$null |
            Select-Object -First 1
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    catch {
        # Fall through.
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw "PYTHON_NOT_FOUND"
    }
    return [string]$command.Source
}

function Get-FreeLoopbackPort {
    $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0)
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
        if ($LASTEXITCODE -ne 0) { throw $Reason }
        return $output
    }
    & $FilePath @Arguments *> $null
    if ($LASTEXITCODE -ne 0) { throw $Reason }
}

function Start-TemporaryPostgres {
    param(
        [string]$PgCtl,
        [string]$PgIsReady,
        [string]$DataDirectory,
        [string]$LogPath,
        [int]$Port
    )

    $argumentLine = @(
        "start",
        "-D `"$DataDirectory`"",
        "-l `"$LogPath`"",
        "-W",
        "-s",
        "-o `"-h 127.0.0.1 -p $Port`""
    ) -join " "
    $launcher = Start-Process -FilePath $PgCtl -ArgumentList $argumentLine -WindowStyle Hidden -PassThru
    if ($null -eq $launcher) { throw "POSTGRES_PG_CTL_PROCESS_MISSING" }
    if (-not $launcher.WaitForExit($PostgresWaitSeconds * 1000)) {
        try { $launcher.Kill() } catch { }
        throw "POSTGRES_PG_CTL_LAUNCH_TIMEOUT"
    }
    if ($launcher.ExitCode -ne 0) { throw "POSTGRES_PG_CTL_START_FAILED" }

    $deadline = [DateTime]::UtcNow.AddSeconds($PostgresWaitSeconds)
    do {
        & $PgIsReady --host=127.0.0.1 --port=$Port --username=wp10_owner `
            --dbname=postgres --timeout=1 --quiet *> $null
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "POSTGRES_START_READINESS_TIMEOUT"
}

function Stop-TemporaryPostgres {
    param([string]$PgCtl, [string]$DataDirectory)
    if ([string]::IsNullOrWhiteSpace($DataDirectory) -or -not (Test-Path -LiteralPath $DataDirectory)) {
        return
    }
    try {
        $arguments = "stop -D `"$DataDirectory`" -m fast -w -s"
        $stopper = Start-Process -FilePath $PgCtl -ArgumentList $arguments -WindowStyle Hidden -PassThru
        if ($null -ne $stopper) {
            $null = $stopper.WaitForExit(15000)
        }
    }
    catch {
        # Cleanup remains best effort; the primary result is already fail closed.
    }
}

function Write-Result {
    param([hashtable]$Result)
    if ($AsJson) {
        $Result | ConvertTo-Json -Compress -Depth 5
        return
    }
    Write-Output "WP10 synthetic recovery rehearsal: $($Result.status)"
    Write-Output "Reason: $($Result.reason_code)"
    Write-Output "Bundle integrity: $($Result.bundle_integrity_pass)"
    Write-Output "Corruption rejected: $($Result.corruption_rejected)"
    Write-Output "Separate restore DB: $($Result.separate_restore_database_used)"
    Write-Output "Restore probe exact match: $($Result.restore_probe_exact_match)"
    Write-Output "Duration ms: $($Result.duration_ms)"
    Write-Output "Real secrets used: NO"
    Write-Output "Private portfolio data used: NO"
}

$startedAt = [DateTime]::UtcNow
$result = @{
    schema_version = "1"
    work_package = "WP10"
    evidence_class = "LENOVO_SYNTHETIC_RECOVERY_REHEARSAL"
    status = "FAIL"
    reason_code = "REHEARSAL_NOT_COMPLETED"
    postgres_major = 18
    postgres_version_class = "UNKNOWN"
    bundle_integrity_pass = $false
    corruption_rejected = $false
    separate_restore_database_used = $false
    restore_probe_exact_match = $false
    temporary_state_cleaned = $false
    real_secret_values_used = $false
    private_portfolio_data_used = $false
    production_database_accessed = $false
    duration_ms = 0
}

$root = $null
$dataDir = $null
$pgCtl = $null
try {
    if (-not (Test-Path -LiteralPath $BackupRunner -PathType Leaf)) { throw "BACKUP_RUNNER_MISSING" }
    if (-not (Test-Path -LiteralPath $BundleTool -PathType Leaf)) { throw "BUNDLE_TOOL_MISSING" }

    $python = Resolve-Python -ExplicitPath $PythonPath
    $initDb = Resolve-PostgresTool -Name "initdb"
    $pgCtl = Resolve-PostgresTool -Name "pg_ctl"
    $pgIsReady = Resolve-PostgresTool -Name "pg_isready"
    $psql = Resolve-PostgresTool -Name "psql"
    $createdb = Resolve-PostgresTool -Name "createdb"
    $pgRestore = Resolve-PostgresTool -Name "pg_restore"
    $pgDump = Resolve-PostgresTool -Name "pg_dump"

    $versionOutput = Invoke-NativeChecked -FilePath $psql -Arguments @("--version") -CaptureOutput -Reason "POSTGRES_VERSION_FAILED"
    $versionText = ($versionOutput | Out-String).Trim()
    if ($versionText -notmatch "([0-9]+\.[0-9]+)") { throw "POSTGRES_VERSION_UNKNOWN" }
    $versionClass = $Matches[1]
    if (-not $versionClass.StartsWith("18.")) { throw "POSTGRES_MAJOR_MISMATCH" }
    $result.postgres_version_class = $versionClass

    $tempBase = if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) {
        [System.IO.Path]::GetTempPath()
    } else { $env:RUNNER_TEMP }
    $root = Join-Path $tempBase ("wp10-rehearsal-" + [Guid]::NewGuid().ToString("N"))
    $dataDir = Join-Path $root "pgdata"
    $workingDir = Join-Path $root "working"
    $bundleDir = Join-Path $root "bundle"
    $corruptDir = Join-Path $root "corrupt"
    $serverLog = Join-Path $root "postgres.log"
    New-Item -ItemType Directory -Path $root, $workingDir, $bundleDir, $corruptDir -Force | Out-Null

    Invoke-NativeChecked -FilePath $initDb -Arguments @(
        "--pgdata=$dataDir",
        "--username=wp10_owner",
        "--auth=trust",
        "--encoding=UTF8",
        "--no-sync",
        "--no-instructions"
    ) -Reason "INITDB_FAILED"

    $port = Get-FreeLoopbackPort
    Start-TemporaryPostgres -PgCtl $pgCtl -PgIsReady $pgIsReady -DataDirectory $dataDir -LogPath $serverLog -Port $port

    $common = @(
        "--host=127.0.0.1",
        "--port=$port",
        "--username=wp10_owner",
        "--no-password"
    )
    Invoke-NativeChecked -FilePath $createdb -Arguments ($common + @("wp10_source")) -Reason "SOURCE_DB_CREATE_FAILED"
    $seedSql = "CREATE TABLE recovery_probe (id integer PRIMARY KEY, payload text NOT NULL); INSERT INTO recovery_probe VALUES (1,'alpha'),(2,'beta'),(3,'gamma');"
    Invoke-NativeChecked -FilePath $psql -Arguments ($common + @(
        "--dbname=wp10_source",
        "--set=ON_ERROR_STOP=1",
        "--command=$seedSql"
    )) -Reason "SOURCE_DB_SEED_FAILED"

    $backupRaw = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
        -File $BackupRunner `
        -DatabaseName "wp10_source" `
        -DatabaseUser "wp10_owner" `
        -DatabaseHost "127.0.0.1" `
        -DatabasePort $port `
        -WorkingDirectory $workingDir `
        -OutputDirectory $bundleDir `
        -BackupClass "POSTGRES_LOGICAL_RECOVERY_REHEARSAL" `
        -PgDumpPath $pgDump `
        -PsqlPath $psql `
        -PythonPath $python `
        -AsJson 2>$null
    if ($LASTEXITCODE -ne 0) { throw "BACKUP_RUNNER_FAILED" }
    try { $backupResult = ($backupRaw | Out-String) | ConvertFrom-Json } catch { throw "BACKUP_RUNNER_OUTPUT_INVALID" }
    if ([string]$backupResult.status -ne "PASS") { throw "BACKUP_RUNNER_DID_NOT_PASS" }

    $archives = @(Get-ChildItem -LiteralPath $bundleDir -File -Filter "wp10-*.dump")
    if ($archives.Count -ne 1) { throw "BUNDLE_ARCHIVE_COUNT_INVALID" }
    $archive = $archives[0]
    $manifest = "$($archive.FullName).manifest.json"
    if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) { throw "BUNDLE_MANIFEST_MISSING" }

    & $python $BundleTool verify --archive $archive.FullName --manifest $manifest *> $null
    if ($LASTEXITCODE -ne 0) { throw "BUNDLE_VERIFY_FAILED" }
    $result.bundle_integrity_pass = $true

    $corruptArchive = Join-Path $corruptDir $archive.Name
    $corruptManifest = Join-Path $corruptDir ([System.IO.Path]::GetFileName($manifest))
    Copy-Item -LiteralPath $archive.FullName -Destination $corruptArchive
    Copy-Item -LiteralPath $manifest -Destination $corruptManifest
    [System.IO.File]::AppendAllText($corruptArchive, "tamper")
    & $python $BundleTool verify --archive $corruptArchive --manifest $corruptManifest *> $null
    if ($LASTEXITCODE -eq 0) { throw "CORRUPT_ARCHIVE_ACCEPTED" }
    $result.corruption_rejected = $true

    Invoke-NativeChecked -FilePath $pgRestore -Arguments @("--list", $archive.FullName) -Reason "PG_RESTORE_LIST_FAILED"
    Invoke-NativeChecked -FilePath $createdb -Arguments ($common + @("wp10_restore")) -Reason "RESTORE_DB_CREATE_FAILED"
    $result.separate_restore_database_used = $true
    Invoke-NativeChecked -FilePath $pgRestore -Arguments ($common + @(
        "--dbname=wp10_restore",
        "--no-owner",
        "--no-privileges",
        "--exit-on-error",
        $archive.FullName
    )) -Reason "PG_RESTORE_FAILED"

    $probe = Invoke-NativeChecked -FilePath $psql -Arguments ($common + @(
        "--dbname=wp10_restore",
        "--tuples-only",
        "--no-align",
        "--field-separator=|",
        "--command=SELECT id,payload FROM recovery_probe ORDER BY id;"
    )) -CaptureOutput -Reason "RESTORE_PROBE_QUERY_FAILED"
    $actual = @($probe | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ })
    $expected = @("1|alpha", "2|beta", "3|gamma")
    if (($actual -join "`n") -ne ($expected -join "`n")) { throw "RESTORE_PROBE_MISMATCH" }
    $result.restore_probe_exact_match = $true

    $result.status = "PASS"
    $result.reason_code = "SYNTHETIC_BACKUP_CORRUPTION_RESTORE_PASS"
}
catch {
    $message = [string]$_.Exception.Message
    if ($message -notmatch '^[A-Z0-9_:\-]+$') { $message = "RECOVERY_REHEARSAL_ERROR" }
    $result.status = "FAIL"
    $result.reason_code = $message
}
finally {
    if ($null -ne $pgCtl -and $null -ne $dataDir) {
        Stop-TemporaryPostgres -PgCtl $pgCtl -DataDirectory $dataDir
    }
    if ($null -ne $root -and (Test-Path -LiteralPath $root)) {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
    $result.temporary_state_cleaned = ($null -eq $root -or -not (Test-Path -LiteralPath $root))
    $result.duration_ms = [int64]([DateTime]::UtcNow - $startedAt).TotalMilliseconds
    if ($result.duration_ms -gt 14400000 -and $result.status -eq "PASS") {
        $result.status = "FAIL"
        $result.reason_code = "RTO_OBJECTIVE_EXCEEDED"
    }
}

Write-Result -Result $result
if ($result.status -ne "PASS") { exit 1 }
