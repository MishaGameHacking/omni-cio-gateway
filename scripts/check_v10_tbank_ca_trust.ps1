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
$contract = Get-Content -LiteralPath $contractPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop

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

$powershell = Get-Command powershell.exe -ErrorAction SilentlyContinue
$provisionerResult = $null
if ($null -ne $powershell) {
    $provisionerArguments = @(
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "infrastructure\windows\provision_v10_tbank_ca_trust.ps1",
        "-Verify",
        "-AsJson"
    )
    $captureParameters = @{
        FilePath = $powershell.Source
        ArgumentList = $provisionerArguments
        WorkingDirectory = $repoRoot
    }
    $provisionerResult = Invoke-CapturedProcess @captureParameters
}

$verify = $null
if (
    $null -ne $provisionerResult -and
    $provisionerResult.launched -and
    -not [string]::IsNullOrWhiteSpace($provisionerResult.stdout)
) {
    try {
        $verify = $provisionerResult.stdout | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        $verify = $null
    }
}

$verifyShapeValid = Test-ObjectShape -Value $verify -RequiredProperties @(
    "reason",
    "root_ca_present",
    "intermediate_ca_present",
    "mutations_attempted",
    "ready"
)

$verifierExitValid = (
    $null -ne $provisionerResult -and
    $provisionerResult.launched -and
    $provisionerResult.exit_code -in @(0, 71)
)
$verifierStateConsistent = (
    $verifyShapeValid -and
    -not [bool]$verify.mutations_attempted -and
    (
        (
            $provisionerResult.exit_code -eq 0 -and
            [bool]$verify.ready -and
            [bool]$verify.root_ca_present -and
            [bool]$verify.intermediate_ca_present
        ) -or
        (
            $provisionerResult.exit_code -eq 71 -and
            -not [bool]$verify.ready
        )
    )
)

$verifierHealthy = $verifierExitValid -and $verifierStateConsistent
$storeReady = (
    $verifierHealthy -and
    $provisionerResult.exit_code -eq 0 -and
    [bool]$verify.ready
)

$indexReady = $false
$indexProbeFailed = $false
if ($storeReady) {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -eq $python) {
        $indexProbeFailed = $true
    }
    else {
        $pipArguments = @(
            "-m",
            "pip",
            "--disable-pip-version-check",
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
        $pipCaptureParameters = @{
            FilePath = $python.Source
            ArgumentList = $pipArguments
            WorkingDirectory = $repoRoot
        }
        $indexProbe = Invoke-CapturedProcess @pipCaptureParameters
        if (-not $indexProbe.launched) {
            $indexProbeFailed = $true
        }
        else {
            $indexReady = $indexProbe.exit_code -eq 0
        }
    }
}

$reason = if (-not $verifierHealthy) {
    "TBANK_CA_TRUST_VERIFIER_FAILED"
}
elseif (-not $storeReady) {
    "TBANK_CA_TRUST_STORE_NOT_READY"
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
$verifierExitCode = if (
    $null -ne $provisionerResult -and
    $provisionerResult.launched
) {
    [int]$provisionerResult.exit_code
}
else {
    -1
}

$result = [ordered]@{
    schema_version = "1"
    reason = $reason
    verifier_exit_code = $verifierExitCode
    trust_store_ready = [bool]$storeReady
    package_index_tls_ready = [bool]$indexReady
    mutations_attempted = $false
    ready = [bool]$ready
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
if ($reason -eq "TBANK_CA_TRUST_VERIFIER_FAILED") {
    exit 73
}
exit 72
