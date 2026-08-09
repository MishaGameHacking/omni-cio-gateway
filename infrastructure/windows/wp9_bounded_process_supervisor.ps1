[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ChildScriptPath,
    [Parameter(Mandatory = $true)]
    [string]$StatePath,
    [ValidateRange(5, 600)]
    [int]$HoldSeconds = 120,
    [ValidateRange(1, 10)]
    [int]$MaxAttempts = 3,
    [ValidateRange(1, 600)]
    [int]$BackoffSeconds = 60
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ChildScriptPath -PathType Leaf)) {
    throw "WP9_SUPERVISOR_CHILD_SCRIPT_MISSING"
}

$powershellExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$attempt = 0

while ($attempt -lt $MaxAttempts) {
    $attempt += 1
    $childArguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -StatePath "{1}" -HoldSeconds {2}' -f `
        $ChildScriptPath, $StatePath, $HoldSeconds
    $child = Start-Process `
        -FilePath $powershellExe `
        -ArgumentList $childArguments `
        -PassThru `
        -WindowStyle Hidden

    Wait-Process -Id $child.Id -ErrorAction Stop
    $child.Refresh()
    $exitCode = [int]$child.ExitCode
    if ($exitCode -eq 0) {
        exit 0
    }

    if ($attempt -ge $MaxAttempts) {
        exit 1
    }

    Start-Sleep -Seconds $BackoffSeconds
}

exit 1
