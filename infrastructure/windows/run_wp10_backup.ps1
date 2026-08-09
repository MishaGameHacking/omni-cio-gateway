[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$DatabaseName,
    [Parameter(Mandatory = $true)][string]$DatabaseUser,
    [string]$DatabaseHost = "127.0.0.1",
    [ValidateRange(1, 65535)][int]$DatabasePort = 5432,
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [ValidateSet("POSTGRES_LOGICAL_PRIVATE_STATE", "POSTGRES_LOGICAL_RECOVERY_REHEARSAL")]
    [string]$BackupClass = "POSTGRES_LOGICAL_PRIVATE_STATE",
    [string]$PgDumpPath,
    [string]$PsqlPath,
    [string]$PythonPath,
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PGCONNECT_TIMEOUT = "5"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$BundleTool = Join-Path $RepoRoot "scripts\v10_wp10_backup_bundle.py"
$ContractPath = Join-Path $RepoRoot "docs\architecture\V10_WP10_RECOVERY_CONTRACT.json"

function Resolve-Tool {
    param(
        [string]$ExplicitPath,
        [string]$PreferredPath,
        [string]$CommandName,
        [string]$Reason
    )

    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        if (-not (Test-Path -LiteralPath $ExplicitPath -PathType Leaf)) {
            throw $Reason
        }
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }
    if (Test-Path -LiteralPath $PreferredPath -PathType Leaf) {
        return (Resolve-Path -LiteralPath $PreferredPath).Path
    }
    $command = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw $Reason
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
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($candidate)) {
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                return (Resolve-Path -LiteralPath $candidate).Path
            }
        }
    }
    catch {
        # Fall through to the ordinary PATH lookup.
    }

    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw "PYTHON_NOT_FOUND"
    }
    return [string]$command.Source
}

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$Reason = "NATIVE_COMMAND_FAILED"
    )

    & $FilePath @Arguments *> $null
    if ($LASTEXITCODE -ne 0) {
        throw $Reason
    }
}

function Write-Result {
    param([hashtable]$Result)

    if ($AsJson) {
        $Result | ConvertTo-Json -Compress -Depth 4
        return
    }
    Write-Output "WP10 backup status: $($Result.status)"
    Write-Output "Reason: $($Result.reason_code)"
    Write-Output "PostgreSQL version class: $($Result.postgres_version_class)"
    Write-Output "Duration ms: $($Result.duration_ms)"
    Write-Output "Private payload emitted: NO"
    Write-Output "Secret value emitted: NO"
}

$startedAt = [DateTime]::UtcNow
$result = @{
    schema_version = "1"
    work_package = "WP10"
    status = "FAIL"
    reason_code = "BACKUP_NOT_COMPLETED"
    postgres_version_class = "UNKNOWN"
    bundle_created = $false
    private_payload_emitted = $false
    secret_value_emitted = $false
    duration_ms = 0
}
$stagingPath = $null

try {
    if (-not (Test-Path -LiteralPath $ContractPath -PathType Leaf)) {
        throw "WP10_CONTRACT_MISSING"
    }
    if (-not (Test-Path -LiteralPath $BundleTool -PathType Leaf)) {
        throw "WP10_BUNDLE_TOOL_MISSING"
    }

    $contract = Get-Content -LiteralPath $ContractPath -Raw | ConvertFrom-Json
    if ([string]$contract.schema_version -ne "2" -or [string]$contract.work_package -ne "WP10") {
        throw "WP10_CONTRACT_INVALID"
    }
    if ([int]$contract.automation.target_cadence_minutes -gt [int]$contract.recovery_objectives.rpo_minutes) {
        throw "WP10_SCHEDULE_EXCEEDS_RPO"
    }
    if ([bool]$contract.authority.trading_methods -or [bool]$contract.authority.real_trading_enabled) {
        throw "WP10_AUTHORITY_BOUNDARY_INVALID"
    }

    $pgDump = Resolve-Tool `
        -ExplicitPath $PgDumpPath `
        -PreferredPath "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" `
        -CommandName "pg_dump.exe" `
        -Reason "PG_DUMP_NOT_FOUND"
    $psql = Resolve-Tool `
        -ExplicitPath $PsqlPath `
        -PreferredPath "C:\Program Files\PostgreSQL\18\bin\psql.exe" `
        -CommandName "psql.exe" `
        -Reason "PSQL_NOT_FOUND"
    $python = Resolve-Python -ExplicitPath $PythonPath

    $versionOutput = & $psql --version 2>$null | Out-String
    if ($LASTEXITCODE -ne 0 -or $versionOutput -notmatch "([0-9]+\.[0-9]+)") {
        throw "POSTGRES_VERSION_UNKNOWN"
    }
    $versionClass = $Matches[1]
    if (-not $versionClass.StartsWith("18.")) {
        throw "POSTGRES_MAJOR_MISMATCH"
    }
    $result.postgres_version_class = $versionClass

    New-Item -ItemType Directory -Path $WorkingDirectory -Force | Out-Null
    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
    $working = (Resolve-Path -LiteralPath $WorkingDirectory).Path
    $output = (Resolve-Path -LiteralPath $OutputDirectory).Path
    if ([string]::Equals($working, $output, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "WORKING_AND_OUTPUT_DIRECTORY_MUST_DIFFER"
    }

    $stagingPath = Join-Path $working (
        "wp10-pgdump-" + [Guid]::NewGuid().ToString("N") + ".dump.partial"
    )

    # Authentication is deliberately external to the command line. For a
    # future bound product database, a reviewed least-privilege process may
    # receive PGPASSFILE/other libpq environment from the separately restored
    # secret store. WP10 never accepts a password/token parameter.
    $dumpArguments = @(
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--host=$DatabaseHost",
        "--port=$DatabasePort",
        "--username=$DatabaseUser",
        "--no-password",
        "--file=$stagingPath",
        $DatabaseName
    )
    Invoke-NativeChecked -FilePath $pgDump -Arguments $dumpArguments -Reason "PG_DUMP_FAILED"
    if (-not (Test-Path -LiteralPath $stagingPath -PathType Leaf)) {
        throw "PG_DUMP_OUTPUT_MISSING"
    }
    if ((Get-Item -LiteralPath $stagingPath).Length -le 0) {
        throw "PG_DUMP_OUTPUT_EMPTY"
    }

    $before = @(
        Get-ChildItem -LiteralPath $output -File -Filter "wp10-*.dump" -ErrorAction Stop |
            ForEach-Object { $_.Name }
    )
    & $python $BundleTool create `
        --staging-archive $stagingPath `
        --output-dir $output `
        --backup-class $BackupClass `
        --postgres-version-class $versionClass *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "BUNDLE_FINALIZE_FAILED"
    }

    $after = @(
        Get-ChildItem -LiteralPath $output -File -Filter "wp10-*.dump" -ErrorAction Stop |
            ForEach-Object { $_.Name }
    )
    $created = @($after | Where-Object { $before -notcontains $_ })
    if ($created.Count -ne 1) {
        throw "BUNDLE_OUTPUT_COUNT_INVALID"
    }

    $archivePath = Join-Path $output $created[0]
    $manifestPath = "$archivePath.manifest.json"
    & $python $BundleTool verify --archive $archivePath --manifest $manifestPath *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "BUNDLE_VERIFY_FAILED"
    }

    $result.bundle_created = $true
    $result.status = "PASS"
    $result.reason_code = "BACKUP_CREATED_AND_VERIFIED"
}
catch {
    $message = [string]$_.Exception.Message
    if ([string]::IsNullOrWhiteSpace($message)) {
        $message = "BACKUP_ERROR"
    }
    if ($message -notmatch '^[A-Z0-9_:\-]+$') {
        $message = "BACKUP_ERROR"
    }
    $result.status = "FAIL"
    $result.reason_code = $message
}
finally {
    if ($null -ne $stagingPath -and (Test-Path -LiteralPath $stagingPath)) {
        Remove-Item -LiteralPath $stagingPath -Force -ErrorAction SilentlyContinue
    }
    $result.duration_ms = [int64]([DateTime]::UtcNow - $startedAt).TotalMilliseconds
}

Write-Result -Result $result
if ($result.status -ne "PASS") {
    exit 1
}
