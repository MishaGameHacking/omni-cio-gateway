[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$toolchainPath = Join-Path $repoRoot "docs\architecture\V10_TOOLCHAIN_BASELINE.json"
$rehearsalPath = Join-Path $PSScriptRoot "rehearse_wp10_recovery.ps1"

if (-not (Test-Path -LiteralPath $toolchainPath -PathType Leaf)) {
    throw "WP10_TOOLCHAIN_BASELINE_MISSING"
}
if (-not (Test-Path -LiteralPath $rehearsalPath -PathType Leaf)) {
    throw "WP10_REHEARSAL_SCRIPT_MISSING"
}

$toolchain = Get-Content -LiteralPath $toolchainPath -Raw -ErrorAction Stop |
    ConvertFrom-Json -ErrorAction Stop
$expectedPython = [string]$toolchain.backend.python
if ($expectedPython -ne "3.14.6") {
    throw "WP10_PYTHON_BASELINE_MISMATCH"
}

function Resolve-Wp10Python {
    $preferred = "C:\Program Files\Python314\python.exe"
    $candidate = $null

    if (Test-Path -LiteralPath $preferred -PathType Leaf) {
        $candidate = $preferred
    }
    else {
        $launcher = Get-Command "py.exe" -ErrorAction SilentlyContinue
        if ($null -eq $launcher) {
            throw "WP10_PYTHON_NOT_FOUND"
        }
        $resolved = & $launcher.Source -3.14 -c "import sys; print(sys.executable)" 2>$null |
            Out-String
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($resolved)) {
            throw "WP10_PYTHON_NOT_FOUND"
        }
        $candidate = $resolved.Trim()
    }

    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw "WP10_PYTHON_NOT_FOUND"
    }

    $version = & $candidate -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null |
        Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "WP10_PYTHON_VERSION_CHECK_FAILED"
    }
    $version = $version.Trim()
    if (-not [string]::Equals(
        $version,
        $expectedPython,
        [System.StringComparison]::Ordinal
    )) {
        throw "WP10_PYTHON_VERSION_MISMATCH"
    }

    return $candidate
}

$pythonPath = Resolve-Wp10Python
$pythonDirectory = Split-Path -Parent $pythonPath
$env:PATH = "$pythonDirectory;$env:PATH"
[Console]::Error.WriteLine("WP10_OWNER_PYTHON_RESOLVED=$expectedPython")

& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
    -File $rehearsalPath `
    -UsePreparedOffdeviceTarget `
    -AsJson
$exitCode = $LASTEXITCODE
exit $exitCode
