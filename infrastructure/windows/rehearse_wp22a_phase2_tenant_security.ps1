[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PythonPath,
    [ValidateRange(30, 300)][int]$ProbeTimeoutSeconds = 120,
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PGCONNECT_TIMEOUT = "5"

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

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Reason
    )

    & $FilePath @Arguments *> $null
    if ($LASTEXITCODE -ne 0) {
        throw $Reason
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
    Invoke-NativeChecked -FilePath $initDb -Arguments @(
        "--pgdata=$dataDir",
        "--username=wp22a_owner",
        "--auth=trust",
        "--encoding=UTF8",
        "--no-sync",
        "--no-instructions"
    ) -Reason "WP22A_PHASE2_INITDB_FAILED"

    & $pgCtl start -D $dataDir -l $logPath -o "-h 127.0.0.1 -p $port" -w -s *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "WP22A_PHASE2_POSTGRES_START_FAILED"
    }
    $started = $true

    & $pgIsReady --host=127.0.0.1 --port=$port --username=wp22a_owner `
        --dbname=postgres --timeout=5 --quiet *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "WP22A_PHASE2_POSTGRES_NOT_READY"
    }

    Invoke-NativeChecked -FilePath $createdb -Arguments @(
        "--host=127.0.0.1",
        "--port=$port",
        "--username=wp22a_owner",
        "--no-password",
        "wp22a_phase2"
    ) -Reason "WP22A_PHASE2_DATABASE_CREATE_FAILED"

    $env:OMNI_CIO_WP22A_PHASE2_DSN = (
        "host=127.0.0.1 port=$port user=wp22a_owner " +
        "dbname=wp22a_phase2 connect_timeout=5"
    )
    if ([string]::IsNullOrWhiteSpace($oldPythonPath)) {
        $env:PYTHONPATH = $RepoRoot
    }
    else {
        $env:PYTHONPATH = "$RepoRoot;$oldPythonPath"
    }

    # The Python probe contains an intentional concurrent-registration race.
    # Keep the entire child process bounded as a second line of defence: a
    # future/database wait must fail this focused gate rather than occupying the
    # single authoritative Lenovo runner until the outer workflow timeout.
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
        try {
            $probeProcess.Kill()
        }
        catch {
            # Timeout is already authoritative; process cleanup remains best-effort.
        }
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
    if ($null -ne $probeProcess) {
        try {
            if (-not $probeProcess.HasExited) {
                $probeProcess.Kill()
            }
        }
        catch {
            # Cleanup is best-effort; the focused timeout remains authoritative.
        }
        finally {
            $probeProcess.Dispose()
        }
    }
    if ($started) {
        try {
            & $pgCtl stop -D $dataDir -m fast -w -s *> $null
        }
        catch {
            # Cleanup is best-effort; the CI workspace cleanup remains authoritative.
        }
    }
    if (Test-Path -LiteralPath $root) {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
}
