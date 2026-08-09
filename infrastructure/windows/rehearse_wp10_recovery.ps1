[CmdletBinding()]
param(
    [switch]$UsePreparedOffdeviceTarget,
    [switch]$AsJson
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$TargetEvidencePath = "C:\ProgramData\OmniCIO\wp10\offdevice-target.json"
$RehearsalEvidencePath = "C:\ProgramData\OmniCIO\wp10\offdevice-rehearsal.json"
$PostgresWaitSeconds = 30
$env:PGCONNECT_TIMEOUT = "5"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function Write-RecoveryPhase {
    param([Parameter(Mandatory = $true)][string]$Name)

    # Keep stdout reserved for the optional sanitized JSON result. Phase names
    # contain no paths, identities, secrets or private payload data.
    [Console]::Error.WriteLine("WP10_RECOVERY_PHASE=$Name")
}

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$CaptureOutput
    )

    if ($CaptureOutput) {
        $output = & $FilePath @Arguments 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "NATIVE_COMMAND_FAILED"
        }
        return $output
    }

    & $FilePath @Arguments *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "NATIVE_COMMAND_FAILED"
    }
}

function Resolve-PostgresTool {
    param([Parameter(Mandatory = $true)][string]$Name)

    $preferred = Join-Path ${env:ProgramFiles} "PostgreSQL\18\bin\$Name.exe"
    if (Test-Path -LiteralPath $preferred -PathType Leaf) {
        return $preferred
    }

    $command = Get-Command "$Name.exe" -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    throw "POSTGRES_TOOL_NOT_FOUND"
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

function Get-SingleArchive {
    param([Parameter(Mandatory = $true)][string]$Directory)

    $archives = @(Get-ChildItem -LiteralPath $Directory -File -Filter "wp10-*.dump")
    if ($archives.Count -ne 1) {
        throw "BUNDLE_ARCHIVE_COUNT_INVALID"
    }
    return $archives[0]
}

function Get-PreparedOffdeviceDirectory {
    if (-not (Test-IsAdministrator)) {
        throw "OWNER_ADMIN_REQUIRED"
    }
    if (-not (Test-Path -LiteralPath $TargetEvidencePath -PathType Leaf)) {
        throw "OWNER_OFFDEVICE_EVIDENCE_MISSING"
    }

    try {
        $evidence = Get-Content -LiteralPath $TargetEvidencePath -Raw |
            ConvertFrom-Json
    }
    catch {
        throw "OWNER_OFFDEVICE_EVIDENCE_INVALID"
    }

    if (
        $evidence.schema_version -ne "1" -or
        $evidence.work_package -ne "WP10" -or
        $evidence.evidence_class -ne "OFFDEVICE_OWNER_APPLY" -or
        $evidence.target_class -ne "BITLOCKER_OWNER_CONTROLLED_NON_SYSTEM_VOLUME"
    ) {
        throw "OWNER_OFFDEVICE_EVIDENCE_INVALID"
    }
    foreach ($field in @(
        "non_system_volume",
        "data_volume",
        "bitlocker_fully_encrypted",
        "bitlocker_protection_on",
        "recovery_key_custody_confirmed"
    )) {
        if (-not [bool]$evidence.$field) {
            throw "OWNER_OFFDEVICE_EVIDENCE_INCOMPLETE"
        }
    }
    if ([bool]$evidence.runner_payload_access_granted) {
        throw "OWNER_EVIDENCE_RUNNER_ACCESS_ENABLED"
    }

    $mountPoint = [string]$evidence.target_mount_point
    if ($mountPoint -notmatch "^[A-Z]:$") {
        throw "OWNER_TARGET_MOUNT_POINT_INVALID"
    }
    $systemRoot = [System.IO.Path]::GetPathRoot($env:SystemRoot).TrimEnd("\")
    if ($mountPoint -eq $systemRoot) {
        throw "SYSTEM_VOLUME_FORBIDDEN"
    }

    $bitlocker = Get-BitLockerVolume -MountPoint $mountPoint -ErrorAction Stop
    if ($bitlocker.VolumeType.ToString() -ne "Data") {
        throw "TARGET_NOT_DATA_VOLUME"
    }
    if ($bitlocker.VolumeStatus.ToString() -ne "FullyEncrypted") {
        throw "TARGET_NOT_FULLY_ENCRYPTED"
    }
    if ($bitlocker.ProtectionStatus.ToString() -ne "On") {
        throw "TARGET_BITLOCKER_PROTECTION_OFF"
    }

    $backupRoot = Join-Path "$mountPoint\" ([string]$evidence.backup_root_name)
    if (-not (Test-Path -LiteralPath $backupRoot -PathType Container)) {
        throw "OWNER_BACKUP_ROOT_MISSING"
    }
    return @{
        path = $backupRoot
        mount_point = $mountPoint
        target_class = [string]$evidence.target_class
    }
}

function Write-Result {
    param([Parameter(Mandatory = $true)][hashtable]$Result)

    if ($AsJson) {
        $Result | ConvertTo-Json -Compress -Depth 5
        return
    }

    Write-Output "WP10 recovery rehearsal status: $($Result.status)"
    Write-Output "PostgreSQL version class: $($Result.postgres_version_class)"
    Write-Output "Bundle integrity: $($Result.bundle_integrity_pass)"
    Write-Output "Corruption rejection: $($Result.corruption_rejected)"
    Write-Output "Off-device copy: $($Result.offdevice_copy_pass)"
    Write-Output "Restore probe: $($Result.restore_probe_pass)"
    Write-Output "Off-device cleanup: $($Result.offdevice_cleanup_pass)"
    Write-Output "Real secrets used: NO"
    Write-Output "Private portfolio data used: NO"
}

$startedAt = [DateTime]::UtcNow
$ownerMode = [bool]$UsePreparedOffdeviceTarget
$result = @{
    schema_version = "1"
    work_package = "WP10"
    mode = $(
        if ($ownerMode) {
            "OWNER_OFFDEVICE_RECOVERY_REHEARSAL"
        }
        else {
            "SYNTHETIC_RECOVERY_REHEARSAL"
        }
    )
    status = "FAIL"
    reason_code = "REHEARSAL_NOT_COMPLETED"
    postgres_version_class = "UNKNOWN"
    bundle_integrity_pass = $false
    corruption_rejected = $false
    offdevice_copy_pass = $false
    restore_probe_pass = $false
    offdevice_cleanup_pass = $false
    source_restore_separate = $true
    temporary_state_cleaned = $false
    owner_target_used = $ownerMode
    real_secret_values_used = $false
    private_portfolio_data_used = $false
    account_identifiers_used = $false
    production_database_accessed = $false
    offdevice_mode = $(
        if ($ownerMode) { "OWNER_ENCRYPTED_TARGET" } else { "SYNTHETIC_TEMP_ONLY" }
    )
    duration_ms = 0
}

$root = $null
$dataDir = $null
$clusterStartTriggered = $false
$postgresProcess = $null
$pgCtl = $null
$destinationArchive = $null
$destinationManifest = $null
$ownerTarget = $null

try {
    Write-RecoveryPhase -Name "RESOLVE_POSTGRES_TOOLS"
    $initDb = Resolve-PostgresTool -Name "initdb"
    $postgres = Resolve-PostgresTool -Name "postgres"
    $pgCtl = Resolve-PostgresTool -Name "pg_ctl"
    $pgIsReady = Resolve-PostgresTool -Name "pg_isready"
    $psql = Resolve-PostgresTool -Name "psql"
    $createdb = Resolve-PostgresTool -Name "createdb"
    $pgDump = Resolve-PostgresTool -Name "pg_dump"
    $pgRestore = Resolve-PostgresTool -Name "pg_restore"

    $versionOutput = Invoke-NativeChecked -FilePath $psql -Arguments @("--version") `
        -CaptureOutput
    $versionText = ($versionOutput | Out-String).Trim()
    if ($versionText -notmatch "([0-9]+\.[0-9]+)") {
        throw "POSTGRES_VERSION_UNKNOWN"
    }
    $versionClass = $Matches[1]
    if (-not $versionClass.StartsWith("18.")) {
        throw "POSTGRES_MAJOR_MISMATCH"
    }
    $result.postgres_version_class = $versionClass

    $tempBase = $env:RUNNER_TEMP
    if ([string]::IsNullOrWhiteSpace($tempBase)) {
        $tempBase = [System.IO.Path]::GetTempPath()
    }
    $root = Join-Path $tempBase (
        "wp10-rehearsal-" + [Guid]::NewGuid().ToString("N")
    )
    $dataDir = Join-Path $root "pgdata"
    $bundleDir = Join-Path $root "bundle"
    $syntheticOffdevice = Join-Path $root "synthetic-offdevice"
    $corruptDir = Join-Path $root "corrupt"
    $serverLog = Join-Path $root "postgres-server.log"
    $serverErrorLog = Join-Path $root "postgres-server-error.log"
    New-Item -ItemType Directory -Path $root, $bundleDir, $corruptDir -Force |
        Out-Null

    if ($ownerMode) {
        Write-RecoveryPhase -Name "VALIDATE_OWNER_OFFDEVICE_TARGET"
        $ownerTarget = Get-PreparedOffdeviceDirectory
        $offdeviceDirectory = [string]$ownerTarget.path
    }
    else {
        New-Item -ItemType Directory -Path $syntheticOffdevice -Force | Out-Null
        $offdeviceDirectory = $syntheticOffdevice
    }

    Write-RecoveryPhase -Name "INITIALIZE_TEMP_CLUSTER"
    Invoke-NativeChecked -FilePath $initDb -Arguments @(
        "--pgdata=$dataDir",
        "--username=wp10_owner",
        "--auth=trust",
        "--encoding=UTF8",
        "--no-sync",
        "--no-instructions"
    )

    Write-RecoveryPhase -Name "START_TEMP_CLUSTER"
    $port = Get-FreeLoopbackPort
    if ($ownerMode) {
        # postgres.exe refuses to run directly from an elevated Windows token.
        # pg_ctl is the PostgreSQL-supported Windows launcher for this case and
        # drops the dangerous administrative privileges before starting the
        # server. -l prevents the detached server from inheriting PowerShell's
        # redirected native-command handles.
        $clusterStartTriggered = $true
        try {
            Invoke-NativeChecked -FilePath $pgCtl -Arguments @(
                "start",
                "-D", $dataDir,
                "-l", $serverLog,
                "-w",
                "-t", "$PostgresWaitSeconds",
                "-o", "-h 127.0.0.1 -p $port"
            )
        }
        catch {
            throw "POSTGRES_PG_CTL_START_FAILED"
        }
    }
    else {
        # PowerShell 5.1 native-command pipelines can remain open when a
        # spawned background server inherits redirected handles. The normal
        # non-admin CI path therefore launches postgres asynchronously with
        # dedicated ephemeral log files.
        $postgresProcess = Start-Process -FilePath $postgres -ArgumentList @(
            "-D", $dataDir,
            "-h", "127.0.0.1",
            "-p", "$port"
        ) -RedirectStandardOutput $serverLog -RedirectStandardError $serverErrorLog `
            -WindowStyle Hidden -PassThru
        if ($null -eq $postgresProcess) {
            throw "POSTGRES_START_PROCESS_MISSING"
        }
        $clusterStartTriggered = $true
    }

    Write-RecoveryPhase -Name "WAIT_TEMP_CLUSTER_READY"
    $deadline = [DateTime]::UtcNow.AddSeconds($PostgresWaitSeconds)
    $ready = $false
    do {
        if ($null -ne $postgresProcess -and $postgresProcess.HasExited) {
            throw "POSTGRES_START_PROCESS_EXITED"
        }
        & $pgIsReady --host=127.0.0.1 --port=$port --username=wp10_owner `
            --dbname=postgres --timeout=1 --quiet *> $null
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            break
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    if (-not $ready) {
        throw "POSTGRES_START_READINESS_TIMEOUT"
    }

    $common = @(
        "--host=127.0.0.1",
        "--port=$port",
        "--username=wp10_owner",
        "--no-password"
    )

    Write-RecoveryPhase -Name "CREATE_SOURCE_DATABASE"
    Invoke-NativeChecked -FilePath $createdb -Arguments ($common + @("wp10_source"))

    Write-RecoveryPhase -Name "SEED_SOURCE_DATABASE"
    $seedSql = @"
CREATE TABLE recovery_probe (
    id integer PRIMARY KEY,
    payload text NOT NULL
);
INSERT INTO recovery_probe (id, payload) VALUES
    (1, 'alpha'),
    (2, 'beta'),
    (3, 'gamma');
"@
    Invoke-NativeChecked -FilePath $psql -Arguments (
        $common + @(
            "--dbname=wp10_source",
            "--set=ON_ERROR_STOP=1",
            "--command=$seedSql"
        )
    )

    Write-RecoveryPhase -Name "DUMP_SOURCE_DATABASE"
    $stagingArchive = Join-Path $root "postgres-staging.dump.partial"
    Invoke-NativeChecked -FilePath $pgDump -Arguments (
        $common + @(
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--file=$stagingArchive",
            "wp10_source"
        )
    )

    Write-RecoveryPhase -Name "FINALIZE_LOCAL_BUNDLE"
    Invoke-NativeChecked -FilePath "python" -Arguments @(
        "scripts/v10_wp10_backup_bundle.py",
        "create",
        "--staging-archive", $stagingArchive,
        "--output-dir", $bundleDir,
        "--backup-class", "POSTGRES_LOGICAL_RECOVERY_REHEARSAL",
        "--postgres-version-class", $versionClass
    )

    $archive = Get-SingleArchive -Directory $bundleDir
    $manifestPath = "$($archive.FullName).manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "BUNDLE_MANIFEST_NOT_FOUND"
    }

    Write-RecoveryPhase -Name "VERIFY_LOCAL_BUNDLE"
    Invoke-NativeChecked -FilePath "python" -Arguments @(
        "scripts/v10_wp10_backup_bundle.py",
        "verify",
        "--archive", $archive.FullName,
        "--manifest", $manifestPath
    )
    Invoke-NativeChecked -FilePath $pgRestore -Arguments @(
        "--list",
        $archive.FullName
    )
    $result.bundle_integrity_pass = $true

    Write-RecoveryPhase -Name "PROVE_CORRUPTION_REJECTION"
    $corruptArchive = Join-Path $corruptDir $archive.Name
    $corruptManifest = Join-Path $corruptDir (
        [System.IO.Path]::GetFileName($manifestPath)
    )
    Copy-Item -LiteralPath $archive.FullName -Destination $corruptArchive
    Copy-Item -LiteralPath $manifestPath -Destination $corruptManifest
    $bytes = [System.IO.File]::ReadAllBytes($corruptArchive)
    if ($bytes.Length -lt 1) {
        throw "ARCHIVE_EMPTY"
    }
    $offset = [int][Math]::Floor($bytes.Length / 2)
    $bytes[$offset] = $bytes[$offset] -bxor 0x01
    [System.IO.File]::WriteAllBytes($corruptArchive, $bytes)

    & python scripts/v10_wp10_backup_bundle.py verify `
        --archive $corruptArchive --manifest $corruptManifest *> $null
    if ($LASTEXITCODE -eq 0) {
        throw "CORRUPTION_NOT_REJECTED"
    }
    $result.corruption_rejected = $true

    Write-RecoveryPhase -Name "COPY_OFFDEVICE_BUNDLE"
    Invoke-NativeChecked -FilePath "python" -Arguments @(
        "scripts/v10_wp10_backup_bundle.py",
        "copy",
        "--archive", $archive.FullName,
        "--manifest", $manifestPath,
        "--target-dir", $offdeviceDirectory
    )
    $destinationArchive = Join-Path $offdeviceDirectory $archive.Name
    $destinationManifest = "$destinationArchive.manifest.json"
    if (
        -not (Test-Path -LiteralPath $destinationArchive -PathType Leaf) -or
        -not (Test-Path -LiteralPath $destinationManifest -PathType Leaf)
    ) {
        throw "OFFDEVICE_BUNDLE_NOT_FOUND"
    }

    Write-RecoveryPhase -Name "VERIFY_OFFDEVICE_BUNDLE"
    Invoke-NativeChecked -FilePath "python" -Arguments @(
        "scripts/v10_wp10_backup_bundle.py",
        "verify",
        "--archive", $destinationArchive,
        "--manifest", $destinationManifest
    )
    Invoke-NativeChecked -FilePath $pgRestore -Arguments @(
        "--list",
        $destinationArchive
    )
    $result.offdevice_copy_pass = $true

    Write-RecoveryPhase -Name "CREATE_RESTORE_DATABASE"
    Invoke-NativeChecked -FilePath $createdb -Arguments ($common + @("wp10_restore"))

    Write-RecoveryPhase -Name "RESTORE_OFFDEVICE_BUNDLE"
    Invoke-NativeChecked -FilePath $pgRestore -Arguments (
        $common + @(
            "--dbname=wp10_restore",
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            $destinationArchive
        )
    )

    Write-RecoveryPhase -Name "VERIFY_RESTORE_PROBE"
    $probeOutput = Invoke-NativeChecked -FilePath $psql -Arguments (
        $common + @(
            "--dbname=wp10_restore",
            "--tuples-only",
            "--no-align",
            "--set=ON_ERROR_STOP=1",
            "--command=SELECT id::text || ':' || payload FROM recovery_probe ORDER BY id;"
        )
    ) -CaptureOutput
    $probeLines = @(
        $probeOutput |
            ForEach-Object { $_.ToString().Trim() } |
            Where-Object { $_ -ne "" }
    )
    $expected = @("1:alpha", "2:beta", "3:gamma")
    if (($probeLines -join "|") -ne ($expected -join "|")) {
        throw "RESTORE_PROBE_MISMATCH"
    }
    $result.restore_probe_pass = $true

    if ($ownerMode) {
        Write-RecoveryPhase -Name "CLEAN_OFFDEVICE_SYNTHETIC"
        Remove-Item -LiteralPath $destinationManifest -Force
        Remove-Item -LiteralPath $destinationArchive -Force
        $destinationManifest = $null
        $destinationArchive = $null
    }
    $result.offdevice_cleanup_pass = $true
    $result.status = "PASS"
    $result.reason_code = "RECOVERY_REHEARSAL_PASS"
}
catch {
    if ($_.Exception.Message -match "^[A-Z0-9_:-]+$") {
        $result.reason_code = $_.Exception.Message
    }
    else {
        $result.reason_code = "RECOVERY_REHEARSAL_ERROR"
    }
}
finally {
    if ($clusterStartTriggered -and $null -ne $pgCtl -and $null -ne $dataDir) {
        try {
            Write-RecoveryPhase -Name "STOP_TEMP_CLUSTER"
            & $pgCtl --pgdata=$dataDir status *> $null
            if ($LASTEXITCODE -eq 0) {
                & $pgCtl --pgdata=$dataDir --mode=fast `
                    --timeout=$PostgresWaitSeconds --wait stop *> $null
                if ($LASTEXITCODE -ne 0) {
                    throw "TEMP_CLUSTER_STOP_FAILED"
                }
            }
            if ($null -ne $postgresProcess -and -not $postgresProcess.HasExited) {
                if (-not $postgresProcess.WaitForExit($PostgresWaitSeconds * 1000)) {
                    throw "TEMP_CLUSTER_PROCESS_EXIT_TIMEOUT"
                }
            }
        }
        catch {
            if ($null -ne $postgresProcess) {
                try {
                    if (-not $postgresProcess.HasExited) {
                        $postgresProcess.Kill()
                        $null = $postgresProcess.WaitForExit(5000)
                    }
                }
                catch {
                    # Result below remains fail-closed even if emergency cleanup fails.
                }
            }
            $result.status = "FAIL"
            $result.reason_code = "TEMP_CLUSTER_CLEANUP_FAILED"
        }
    }

    if ($ownerMode) {
        foreach ($path in @($destinationManifest, $destinationArchive)) {
            if ($null -ne $path -and (Test-Path -LiteralPath $path -PathType Leaf)) {
                try {
                    Remove-Item -LiteralPath $path -Force
                }
                catch {
                    $result.status = "FAIL"
                    $result.reason_code = "OFFDEVICE_SYNTHETIC_CLEANUP_FAILED"
                }
            }
        }
    }

    if ($null -ne $root -and (Test-Path -LiteralPath $root)) {
        try {
            Write-RecoveryPhase -Name "CLEAN_TEMP_STATE"
            Remove-Item -LiteralPath $root -Recurse -Force
            $result.temporary_state_cleaned = $true
        }
        catch {
            $result.status = "FAIL"
            $result.reason_code = "TEMP_STATE_CLEANUP_FAILED"
        }
    }
    else {
        $result.temporary_state_cleaned = $true
    }

    $result.duration_ms = [Math]::Round(
        ([DateTime]::UtcNow - $startedAt).TotalMilliseconds,
        0
    )
}

if ($ownerMode -and $result.status -eq "PASS") {
    try {
        $evidenceRoot = Split-Path -Parent $RehearsalEvidencePath
        if (-not (Test-Path -LiteralPath $evidenceRoot)) {
            New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
        }
        $safeEvidence = [ordered]@{
            schema_version = "1"
            work_package = "WP10"
            evidence_class = "OWNER_OFFDEVICE_RECOVERY_REHEARSAL"
            target_class = [string]$ownerTarget.target_class
            target_mount_point = [string]$ownerTarget.mount_point
            rehearsed_at_utc = [DateTime]::UtcNow.ToString("o")
            postgres_version_class = $result.postgres_version_class
            bundle_integrity_pass = $result.bundle_integrity_pass
            corruption_rejected = $result.corruption_rejected
            offdevice_copy_pass = $result.offdevice_copy_pass
            restore_probe_pass = $result.restore_probe_pass
            offdevice_cleanup_pass = $result.offdevice_cleanup_pass
            temporary_state_cleaned = $result.temporary_state_cleaned
            real_secret_values_used = $false
            private_portfolio_data_used = $false
            account_identifiers_used = $false
            production_database_accessed = $false
            recovery_key_value_used = $false
            duration_ms = $result.duration_ms
        }
        $safeEvidence | ConvertTo-Json -Depth 4 |
            Set-Content -LiteralPath $RehearsalEvidencePath -Encoding UTF8
    }
    catch {
        $result.status = "FAIL"
        $result.reason_code = "OWNER_REHEARSAL_EVIDENCE_WRITE_FAILED"
    }
}

Write-RecoveryPhase -Name "COMPLETE"
Write-Result -Result $result
if ($result.status -ne "PASS") {
    exit 1
}
exit 0
