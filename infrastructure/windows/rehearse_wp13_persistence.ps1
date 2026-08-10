[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PythonPath,
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PGCONNECT_TIMEOUT = "5"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$BackupRunner = Join-Path $PSScriptRoot "run_wp10_backup.ps1"
$BundleTool = Join-Path $RepoRoot "scripts\v10_wp10_backup_bundle.py"
$Probe = Join-Path $RepoRoot "scripts\rehearse_v10_wp13_persistence.py"
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
        & $PgIsReady --host=127.0.0.1 --port=$Port --username=wp13_owner `
            --dbname=postgres --timeout=1 --quiet *> $null
        if ($LASTEXITCODE -eq 0) {
            return
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)

    throw "POSTGRES_START_READINESS_TIMEOUT"
}

function Stop-TemporaryPostgres {
    param([string]$PgCtl, [string]$DataDirectory)

    if ([string]::IsNullOrWhiteSpace($DataDirectory)) {
        return
    }
    if (-not (Test-Path -LiteralPath $DataDirectory -PathType Container)) {
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
        # Best effort; cleanup status fails closed below.
    }
}

function Invoke-ProbeJson {
    param(
        [string]$Python,
        [string]$DatabaseName,
        [string]$Port,
        [string]$Command
    )

    $oldDsn = $env:OMNI_CIO_WP13_DSN
    try {
        $env:OMNI_CIO_WP13_DSN = (
            "host=127.0.0.1 port=$Port user=wp13_owner " +
            "dbname=$DatabaseName connect_timeout=5"
        )
        $raw = & $Python $Probe $Command 2>$null
        $probeExit = $LASTEXITCODE
        $rawText = ($raw | Out-String)
        if ([string]::IsNullOrWhiteSpace($rawText)) {
            if ($probeExit -ne 0) {
                throw "WP13_PROBE_FAILED:NO_OUTPUT"
            }
            throw "WP13_PROBE_OUTPUT_EMPTY"
        }
        try {
            $parsed = ($rawText | ConvertFrom-Json)
        }
        catch {
            throw "WP13_PROBE_OUTPUT_INVALID"
        }
        if ($probeExit -ne 0) {
            $probeReason = ([string]$parsed.reason).ToUpperInvariant()
            if ([string]::IsNullOrWhiteSpace($probeReason)) {
                $probeReason = "UNKNOWN"
            }
            if ($probeReason -notmatch '^[A-Z0-9_.-]+$') {
                $probeReason = "UNKNOWN"
            }
            throw "WP13_PROBE_FAILED:$probeReason"
        }
        return $parsed
    }
    finally {
        $env:OMNI_CIO_WP13_DSN = $oldDsn
    }
}

function Write-Result {
    param([hashtable]$Result)

    if ($AsJson) {
        $Result | ConvertTo-Json -Compress -Depth 5
        return
    }
    Write-Output "WP13 PostgreSQL audit: $($Result.status)"
    Write-Output "Reason: $($Result.reason_code)"
    Write-Output "Migration race serialized: $($Result.migration_race_serialized)"
    Write-Output "Decimal round-trip: $($Result.decimal_roundtrip)"
    Write-Output "Append-only rejection: $($Result.append_only_rejection)"
    Write-Output "Concurrent write idempotency: $($Result.concurrent_write_idempotency)"
    Write-Output "Backup integrity: $($Result.backup_integrity_pass)"
    Write-Output "Corruption rejected: $($Result.corruption_rejected)"
    Write-Output "Separate restore DB: $($Result.separate_restore_database_used)"
    Write-Output "Restore digest match: $($Result.restore_digest_exact_match)"
    Write-Output "Duration ms: $($Result.duration_ms)"
    Write-Output "Real secrets used: NO"
    Write-Output "Private portfolio data used: NO"
}

$startedAt = [DateTime]::UtcNow
$phase = "INITIALIZE"
$result = @{
    schema_version = "1"
    work_package = "WP13"
    evidence_class = "LENOVO_SYNTHETIC_POSTGRESQL_PERSISTENCE_REHEARSAL"
    status = "FAIL"
    reason_code = "AUDIT_NOT_COMPLETED"
    phase = $phase
    postgres_major = 18
    migration_count = 0
    migration_series_sha256 = ""
    state_digest_sha256 = ""
    migration_race_serialized = $false
    decimal_roundtrip = $false
    append_only_rejection = $false
    conflicting_replay_rejected = $false
    concurrent_write_idempotency = $false
    owner_scope_rejection = $false
    bounded_cache_retention = $false
    backup_integrity_pass = $false
    corruption_rejected = $false
    separate_restore_database_used = $false
    restore_digest_exact_match = $false
    temporary_state_cleaned = $false
    real_secret_values_used = $false
    private_portfolio_data_used = $false
    account_identifiers_used = $false
    production_database_accessed = $false
    duration_ms = 0
}

$root = $null
$dataDir = $null
$pgCtl = $null
try {
    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
        throw "PYTHON_NOT_FOUND"
    }
    if (-not (Test-Path -LiteralPath $BackupRunner -PathType Leaf)) {
        throw "BACKUP_RUNNER_MISSING"
    }
    if (-not (Test-Path -LiteralPath $BundleTool -PathType Leaf)) {
        throw "BUNDLE_TOOL_MISSING"
    }
    if (-not (Test-Path -LiteralPath $Probe -PathType Leaf)) {
        throw "WP13_PROBE_MISSING"
    }

    $phase = "RESOLVE_TOOLS"
    $initDb = Resolve-PostgresTool -Name "initdb"
    $pgCtl = Resolve-PostgresTool -Name "pg_ctl"
    $pgIsReady = Resolve-PostgresTool -Name "pg_isready"
    $createdb = Resolve-PostgresTool -Name "createdb"
    $pgRestore = Resolve-PostgresTool -Name "pg_restore"
    $pgDump = Resolve-PostgresTool -Name "pg_dump"
    $psql = Resolve-PostgresTool -Name "psql"

    $versionOutput = Invoke-NativeChecked `
        -FilePath $psql `
        -Arguments @("--version") `
        -CaptureOutput `
        -Reason "POSTGRES_VERSION_FAILED"
    $versionText = ($versionOutput | Out-String).Trim()
    if ($versionText -notmatch "([0-9]+\.[0-9]+)") {
        throw "POSTGRES_VERSION_UNKNOWN"
    }
    if (-not $Matches[1].StartsWith("18.")) {
        throw "POSTGRES_MAJOR_MISMATCH"
    }

    $phase = "CREATE_TEMP_CLUSTER"
    $tempBase = if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) {
        [System.IO.Path]::GetTempPath()
    }
    else {
        $env:RUNNER_TEMP
    }
    $root = Join-Path $tempBase ("wp13-audit-" + [Guid]::NewGuid().ToString("N"))
    $dataDir = Join-Path $root "pgdata"
    $workingDir = Join-Path $root "working"
    $bundleDir = Join-Path $root "bundle"
    $corruptDir = Join-Path $root "corrupt"
    $serverLog = Join-Path $root "postgres.log"
    New-Item -ItemType Directory -Path $root, $workingDir, $bundleDir, $corruptDir -Force |
        Out-Null

    Invoke-NativeChecked -FilePath $initDb -Arguments @(
        "--pgdata=$dataDir",
        "--username=wp13_owner",
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

    $common = @(
        "--host=127.0.0.1",
        "--port=$port",
        "--username=wp13_owner",
        "--no-password"
    )

    $phase = "CREATE_SOURCE_DB"
    Invoke-NativeChecked `
        -FilePath $createdb `
        -Arguments ($common + @("wp13_source")) `
        -Reason "SOURCE_DB_CREATE_FAILED"

    $phase = "EXERCISE_PERSISTENCE"
    $source = Invoke-ProbeJson `
        -Python $PythonPath `
        -DatabaseName "wp13_source" `
        -Port $port `
        -Command "exercise"
    if ([string]$source.status -ne "PASS") {
        throw "WP13_PROBE_DID_NOT_PASS"
    }
    $result.migration_count = [int]$source.migration_count
    $result.migration_series_sha256 = [string]$source.migration_series_sha256
    $result.state_digest_sha256 = [string]$source.state_digest_sha256
    $result.migration_race_serialized = [bool]$source.migration_race_serialized
    $result.decimal_roundtrip = [bool]$source.decimal_roundtrip
    $result.append_only_rejection = [bool]$source.append_only_rejection
    $result.conflicting_replay_rejected = [bool]$source.conflicting_replay_rejected
    $result.concurrent_write_idempotency = [bool]$source.concurrent_write_idempotency
    $result.owner_scope_rejection = [bool]$source.owner_scope_rejection
    $result.bounded_cache_retention = [bool]$source.bounded_cache_retention

    if (
        -not $result.migration_race_serialized -or
        -not $result.decimal_roundtrip -or
        -not $result.append_only_rejection -or
        -not $result.conflicting_replay_rejected -or
        -not $result.concurrent_write_idempotency -or
        -not $result.owner_scope_rejection -or
        -not $result.bounded_cache_retention
    ) {
        throw "WP13_PERSISTENCE_ASSERTION_FAILED"
    }

    $phase = "WP10_LOGICAL_BACKUP"
    $backupRaw = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
        -File $BackupRunner `
        -DatabaseName "wp13_source" `
        -DatabaseUser "wp13_owner" `
        -DatabaseHost "127.0.0.1" `
        -DatabasePort $port `
        -WorkingDirectory $workingDir `
        -OutputDirectory $bundleDir `
        -BackupClass "POSTGRES_LOGICAL_RECOVERY_REHEARSAL" `
        -PgDumpPath $pgDump `
        -PsqlPath $psql `
        -PythonPath $PythonPath `
        -AsJson 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "BACKUP_RUNNER_FAILED"
    }
    try {
        $backupResult = ($backupRaw | Out-String) | ConvertFrom-Json
    }
    catch {
        throw "BACKUP_RUNNER_OUTPUT_INVALID"
    }
    if ([string]$backupResult.status -ne "PASS") {
        throw "BACKUP_RUNNER_DID_NOT_PASS"
    }
    $result.backup_integrity_pass = $true

    $archives = @(Get-ChildItem -LiteralPath $bundleDir -File -Filter "wp10-*.dump")
    if ($archives.Count -ne 1) {
        throw "BUNDLE_ARCHIVE_COUNT_INVALID"
    }
    $archive = $archives[0]
    $manifest = "$($archive.FullName).manifest.json"
    if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
        throw "BUNDLE_MANIFEST_MISSING"
    }

    $phase = "PROVE_CORRUPTION_REJECTION"
    $corruptArchive = Join-Path $corruptDir $archive.Name
    $corruptManifest = "$corruptArchive.manifest.json"
    Copy-Item -LiteralPath $archive.FullName -Destination $corruptArchive
    Copy-Item -LiteralPath $manifest -Destination $corruptManifest
    [System.IO.File]::AppendAllText($corruptArchive, "tamper")
    & $PythonPath $BundleTool verify `
        --archive $corruptArchive --manifest $corruptManifest *> $null
    if ($LASTEXITCODE -eq 0) {
        throw "CORRUPT_ARCHIVE_ACCEPTED"
    }
    $result.corruption_rejected = $true

    $phase = "RESTORE_SEPARATE_DATABASE"
    Invoke-NativeChecked `
        -FilePath $createdb `
        -Arguments ($common + @("wp13_restore")) `
        -Reason "RESTORE_DB_CREATE_FAILED"
    $result.separate_restore_database_used = $true
    Invoke-NativeChecked -FilePath $pgRestore -Arguments ($common + @(
        "--dbname=wp13_restore",
        "--no-owner",
        "--no-privileges",
        "--exit-on-error",
        $archive.FullName
    )) -Reason "PG_RESTORE_FAILED"

    $phase = "VERIFY_RESTORE_DIGEST"
    $restored = Invoke-ProbeJson `
        -Python $PythonPath `
        -DatabaseName "wp13_restore" `
        -Port $port `
        -Command "digest"
    if ([string]$restored.status -ne "PASS") {
        throw "RESTORE_DIGEST_PROBE_FAILED"
    }
    if (
        [int]$restored.migration_count -ne [int]$source.migration_count -or
        [string]$restored.migration_series_sha256 -ne [string]$source.migration_series_sha256 -or
        [string]$restored.state_digest_sha256 -ne [string]$source.state_digest_sha256
    ) {
        throw "RESTORE_STATE_DIGEST_MISMATCH"
    }
    $result.restore_digest_exact_match = $true

    $phase = "COMPLETE"
    $result.status = "PASS"
    $result.reason_code = "WP13_POSTGRESQL_PERSISTENCE_BACKUP_RESTORE_PASS"
}
catch {
    $message = [string]$_.Exception.Message
    if ($message -match '^[A-Z0-9_:\-]+$') {
        $reasonCode = $message
    }
    else {
        $exceptionType = ([string]$_.Exception.GetType().Name).ToUpperInvariant()
        if ($exceptionType -notmatch '^[A-Z0-9_.-]+$') {
            $exceptionType = "UNKNOWN"
        }
        $errorId = ([string]$_.FullyQualifiedErrorId).ToUpperInvariant()
        if ([string]::IsNullOrWhiteSpace($errorId) -or $errorId -notmatch '^[A-Z0-9_.-]+$') {
            $errorId = "UNKNOWN"
        }
        $reasonCode = "WP13_AUDIT_ERROR:$exceptionType:$errorId"
    }
    $result.status = "FAIL"
    $result.reason_code = $reasonCode
}
finally {
    $result.phase = $phase
    if ($null -ne $pgCtl -and $null -ne $dataDir) {
        Stop-TemporaryPostgres -PgCtl $pgCtl -DataDirectory $dataDir
    }
    if ($null -ne $root -and (Test-Path -LiteralPath $root)) {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
    $result.temporary_state_cleaned = (
        $null -eq $root -or -not (Test-Path -LiteralPath $root)
    )
    $result.duration_ms = [int64]([DateTime]::UtcNow - $startedAt).TotalMilliseconds
}

Write-Result -Result $result
if ($result.status -ne "PASS") {
    exit 1
}
