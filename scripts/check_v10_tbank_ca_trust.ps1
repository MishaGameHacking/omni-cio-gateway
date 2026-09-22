[CmdletBinding()]
param(
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "TBANK_CA_TRUST_WINDOWS_REQUIRED"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$contractPath = Join-Path $repoRoot "docs\architecture\V10_TBANK_CA_TRUST_CONTRACT.json"
$contract = Get-Content -LiteralPath $contractPath -Raw -ErrorAction Stop |
    ConvertFrom-Json -ErrorAction Stop
$expectedRootSha256 = ([string]$contract.certificates.root.sha256_der).ToUpperInvariant()

function Invoke-CapturedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    $stdoutPath = $null
    $stderrPath = $null
    try {
        try {
            $stdoutPath = [System.IO.Path]::GetTempFileName()
            $stderrPath = [System.IO.Path]::GetTempFileName()
            $startParameters = @{
                FilePath = $FilePath
                ArgumentList = $ArgumentList
                WorkingDirectory = $WorkingDirectory
                NoNewWindow = $true
                Wait = $true
                PassThru = $true
                RedirectStandardOutput = $stdoutPath
                RedirectStandardError = $stderrPath
                ErrorAction = "Stop"
            }
            $process = Start-Process @startParameters
        }
        catch {
            return [pscustomobject]@{
                launched = $false
                exit_code = $null
                stdout = ""
            }
        }

        $stdout = ""
        if (Test-Path -LiteralPath $stdoutPath -PathType Leaf) {
            $stdout = Get-Content -LiteralPath $stdoutPath -Raw -ErrorAction SilentlyContinue
            if ($null -eq $stdout) {
                $stdout = ""
            }
        }

        return [pscustomobject]@{
            launched = $true
            exit_code = [int]$process.ExitCode
            stdout = [string]$stdout
        }
    }
    finally {
        if (-not [string]::IsNullOrWhiteSpace($stdoutPath)) {
            Remove-Item -LiteralPath $stdoutPath -Force -ErrorAction SilentlyContinue
        }
        if (-not [string]::IsNullOrWhiteSpace($stderrPath)) {
            Remove-Item -LiteralPath $stderrPath -Force -ErrorAction SilentlyContinue
        }
    }
}

function Test-ObjectShape {
    param(
        [Parameter()][AllowNull()]$Value,
        [Parameter(Mandatory = $true)][string[]]$RequiredProperties
    )

    if ($null -eq $Value) {
        return $false
    }

    $names = @($Value.PSObject.Properties.Name)
    foreach ($property in $RequiredProperties) {
        if ($property -notin $names) {
            return $false
        }
    }
    return $true
}

$python = Get-Command python.exe -ErrorAction SilentlyContinue
$bundleResult = $null
$bundlePath = $null
$envPublishRequired = -not [string]::IsNullOrWhiteSpace($env:GITHUB_ENV)

if ($null -ne $python) {
    $tempRoot = if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) {
        [System.IO.Path]::GetTempPath()
    }
    else {
        [string]$env:RUNNER_TEMP
    }
    $bundlePath = Join-Path $tempRoot (
        "omni-cio-tbank-pip-ca-{0}.pem" -f [guid]::NewGuid().ToString("N")
    )
    $bundleArguments = @(
        "scripts\prepare_v10_tbank_pip_ca_bundle.py",
        "--output",
        $bundlePath
    )
    if ($envPublishRequired) {
        $bundleArguments += @("--github-env", [string]$env:GITHUB_ENV)
    }

    $bundleCapture = @{
        FilePath = $python.Source
        ArgumentList = $bundleArguments
        WorkingDirectory = $repoRoot
    }
    $bundleResult = Invoke-CapturedProcess @bundleCapture
}

$bundleState = $null
if (
    $null -ne $bundleResult -and
    $bundleResult.launched -and
    -not [string]::IsNullOrWhiteSpace($bundleResult.stdout)
) {
    try {
        $bundleState = $bundleResult.stdout | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        $bundleState = $null
    }
}

$bundleShapeValid = Test-ObjectShape -Value $bundleState -RequiredProperties @(
    "reason",
    "root_sha256",
    "base_certificate_count",
    "bundle_certificate_count",
    "env_published",
    "ready"
)
$bundleReady = (
    $bundleShapeValid -and
    $bundleResult.exit_code -eq 0 -and
    [bool]$bundleState.ready -and
    [string]$bundleState.reason -eq "TBANK_PIP_CA_BUNDLE_READY" -and
    [string]$bundleState.root_sha256 -eq $expectedRootSha256 -and
    [int]$bundleState.base_certificate_count -gt 0 -and
    [int]$bundleState.bundle_certificate_count -ge
        [int]$bundleState.base_certificate_count -and
    (
        -not $envPublishRequired -or
        [bool]$bundleState.env_published
    ) -and
    -not [string]::IsNullOrWhiteSpace($bundlePath) -and
    (Test-Path -LiteralPath $bundlePath -PathType Leaf)
)

$indexReady = $false
$indexProbeFailed = $false
if ($bundleReady) {
    $pipArguments = @(
        "-m",
        "pip",
        "--disable-pip-version-check",
        "--cert",
        $bundlePath,
        "index",
        "versions",
        "t-tech-investments",
        "--index-url",
        [string]$contract.package_index,
        "--retries",
        "0",
        "--timeout",
        "10"
    )
    $pipCapture = @{
        FilePath = $python.Source
        ArgumentList = $pipArguments
        WorkingDirectory = $repoRoot
    }
    $indexProbe = Invoke-CapturedProcess @pipCapture
    if (-not $indexProbe.launched) {
        $indexProbeFailed = $true
    }
    else {
        $indexReady = $indexProbe.exit_code -eq 0
    }
}

$reason = if (-not $bundleReady) {
    "TBANK_PIP_CA_BUNDLE_FAILED"
}
elseif ($indexProbeFailed) {
    "TBANK_PACKAGE_INDEX_PROBE_FAILED"
}
elseif (-not $indexReady) {
    "TBANK_PACKAGE_INDEX_TLS_NOT_READY"
}
else {
    "TBANK_PACKAGE_INDEX_TLS_READY"
}

$ready = $reason -eq "TBANK_PACKAGE_INDEX_TLS_READY"
$bundleExitCode = if (
    $null -ne $bundleResult -and
    $bundleResult.launched
) {
    [int]$bundleResult.exit_code
}
else {
    -1
}

$result = [ordered]@{
    schema_version = "2"
    reason = $reason
    bundle_preparer_exit_code = $bundleExitCode
    root_pin_verified = [bool]$bundleReady
    pip_ca_bundle_ready = [bool]$bundleReady
    package_index_tls_ready = [bool]$indexReady
    machine_trust_store_required = $false
    mutations_attempted = $false
    ready = [bool]$ready
}

if (-not $envPublishRequired -and -not [string]::IsNullOrWhiteSpace($bundlePath)) {
    Remove-Item -LiteralPath $bundlePath -Force -ErrorAction SilentlyContinue
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 4
}
else {
    $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value }
}

if ($ready) {
    exit 0
}
if ($reason -eq "TBANK_PIP_CA_BUNDLE_FAILED") {
    exit 73
}
exit 72
