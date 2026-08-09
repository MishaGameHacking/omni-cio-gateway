[CmdletBinding()]
param(
    [switch]$AsJson
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

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
    Write-Output "Restore probe: $($Result.restore_probe_pass)"
    Write-Output "Real secrets used: NO"
    Write-Output "Private portfolio data used: NO"
}

$startedAt = [DateTime]::UtcNow
$result = @{
    schema_version = "1"
    work_package = "WP10"
    mode = "SYNTHETIC_RECOVERY_REHEARSAL"
    status = "FAIL"
    reason_code = "REHEARSAL_NOT_COMPLETED"
    postgres_version_class = "UNKNOWN"
    bundle_integrity_pass = $false
    corruption_rejected = $false
    restore_probe_pass = $false
    source_restore_separate = $true
    temporary_state_cleaned = $false
    real_secret_values_used = $false
    private_portfolio_data_used = $false
    account_identifiers_used = $false
    production_database_accessed = $false
    offdevice_mode = "SYNTHETIC_TEMP_ONLY"
    duration_ms = 0
}

$root = $null
$dataDir = $null
$clusterStarted = $false
$pgCtl = $null

try {
    $initDb = Resolve-PostgresTool -Name "initdb"
    $pgCtl = Resolve-PostgresTool -Name "pg_ctl"
    $psql = Resolve-PostgresTool -Name "psql"
    $createdb = Resolve-PostgresTool -Name "createdb"
    $pgDump = Resolve-PostgresTool -Name "pg_dump"
    $pgRestore = Resolve-PostgresTool -Name "pg_restore"

    $versionOutput = Invoke-NativeChecked -FilePath $psql -Arguments @("--version") -CaptureOutput
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
    $root = Join-Path $tempBase ("wp10-rehearsal-" + [Guid]::NewGuid().ToString("N"))
    $dataDir = Join-Path $root "pgdata"
    $bundleDir = Join-Path $root "bundle"
    $syntheticOffdevice = Join-Path $root "synthetic-offdevice"
    $corruptDir = Join-Path $root "corrupt"
    New-Item -ItemType Directory -Path $root, $bundleDir, $syntheticOffdevice, $corruptDir -Force | Out-Null

    Invoke-NativeChecked -FilePath $initDb -Arguments @(
        "--pgdata=$dataDir",
        "--username=wp10_owner",
        "--auth=trust",
        "--encoding=UTF8"
    )

    $port = Get-FreeLoopbackPort
    Invoke-NativeChecked -FilePath $pgCtl -Arguments @(
        "--pgdata=$dataDir",
        "--options=-h 127.0.0.1 -p $port",
        "--wait",
        "start"
    )
    $clusterStarted = $true

    $common = @("--host=127.0.0.1", "--port=$port", "--username=wp10_owner")
    Invoke-NativeChecked -FilePath $createdb -Arguments ($common + @("wp10_source"))

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
        $common + @("--dbname=wp10_source", "--set=ON_ERROR_STOP=1", "--command=$seedSql")
    )

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

    Invoke-NativeChecked -FilePath "python" -Arguments @(
        "scripts/v10_wp10_backup_bundle.py",
        "verify",
        "--archive", $archive.FullName,
        "--manifest", $manifestPath
    )
    Invoke-NativeChecked -FilePath $pgRestore -Arguments @("--list", $archive.FullName)
    $result.bundle_integrity_pass = $true

    $corruptArchive = Join-Path $corruptDir $archive.Name
    $corruptManifest = Join-Path $corruptDir ([System.IO.Path]::GetFileName($manifestPath))
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

    Invoke-NativeChecked -FilePath "python" -Arguments @(
        "scripts/v10_wp10_backup_bundle.py",
        "copy",
        "--archive", $archive.FullName,
        "--manifest", $manifestPath,
        "--target-dir", $syntheticOffdevice
    )
    $copiedArchive = Get-SingleArchive -Directory $syntheticOffdevice
    $copiedManifest = "$($copiedArchive.FullName).manifest.json"
    Invoke-NativeChecked -FilePath "python" -Arguments @(
        "scripts/v10_wp10_backup_bundle.py",
        "verify",
        "--archive", $copiedArchive.FullName,
        "--manifest", $copiedManifest
    )
    Invoke-NativeChecked -FilePath $pgRestore -Arguments @("--list", $copiedArchive.FullName)

    Invoke-NativeChecked -FilePath $createdb -Arguments ($common + @("wp10_restore"))
    Invoke-NativeChecked -FilePath $pgRestore -Arguments (
        $common + @(
            "--dbname=wp10_restore",
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            $copiedArchive.FullName
        )
    )

    $probeOutput = Invoke-NativeChecked -FilePath $psql -Arguments (
        $common + @(
            "--dbname=wp10_restore",
            "--tuples-only",
            "--no-align",
            "--set=ON_ERROR_STOP=1",
            "--command=SELECT id::text || ':' || payload FROM recovery_probe ORDER BY id;"
        )
    ) -CaptureOutput
    $probeLines = @($probeOutput | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ -ne "" })
    $expected = @("1:alpha", "2:beta", "3:gamma")
    if (($probeLines -join "|") -ne ($expected -join "|")) {
        throw "RESTORE_PROBE_MISMATCH"
    }
    $result.restore_probe_pass = $true

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
    if ($clusterStarted -and $null -ne $pgCtl -and $null -ne $dataDir) {
        try {
            & $pgCtl --pgdata=$dataDir --mode=fast --wait stop *> $null
        }
        catch {
            $result.status = "FAIL"
            $result.reason_code = "TEMP_CLUSTER_CLEANUP_FAILED"
        }
    }
    if ($null -ne $root -and (Test-Path -LiteralPath $root)) {
        try {
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

Write-Result -Result $result
if ($result.status -ne "PASS") {
    exit 1
}
exit 0
