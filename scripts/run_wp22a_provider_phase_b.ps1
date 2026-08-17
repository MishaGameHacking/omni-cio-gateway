[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("preflight", "plan", "apply", "verify", "verify-live", "destroy-plan", "destroy")]
    [string]$Operation,

    [Parameter(Mandatory = $true)][string]$ExpectedMainSha,
    [Parameter(Mandatory = $true)][string]$Confirmation
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") { throw "WP22A_PROVIDER_PHASE_B_REQUIRES_WINDOWS" }
if ($env:GITHUB_REF -ne "refs/heads/main") { throw "WP22A_PROVIDER_PHASE_B_MAIN_ONLY" }
if ($ExpectedMainSha -notmatch '^[0-9a-f]{40}$') { throw "WP22A_PROVIDER_EXPECTED_MAIN_SHA_INVALID" }
if ($env:GITHUB_SHA -ne $ExpectedMainSha) { throw "WP22A_PROVIDER_EVENT_SHA_MISMATCH" }

$requiredProviderVariables = @(
    "CLOUDFLARE_API_TOKEN",
    "WP22A_CLOUDFLARE_ACCOUNT_ID",
    "WP22A_CLOUDFLARE_ZONE_ID",
    "WP22A_EXTERNAL_HOST",
    "WP22A_CLOUDFLARE_TEAM_NAME"
)
foreach ($name in $requiredProviderVariables) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ([string]::IsNullOrWhiteSpace($value)) { throw "WP22A_PROVIDER_PROTECTED_INPUT_MISSING" }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$head = @(& git -C $repoRoot rev-parse HEAD 2>$null)
if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1 -or ([string]$head[0]).Trim() -ne $ExpectedMainSha) {
    throw "WP22A_PROVIDER_CHECKOUT_SHA_MISMATCH"
}
$dirty = @(& git -C $repoRoot status --porcelain 2>$null)
if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) { throw "WP22A_PROVIDER_CHECKOUT_NOT_CLEAN" }

$python = "python"
$liveGuard = Join-Path $repoRoot "scripts\wp22a_cloudflare_live.py"
$stateGuard = Join-Path $repoRoot "scripts\wp22a_provider_state_guard.py"
$bindingGuard = Join-Path $repoRoot "scripts\check_wp22a_provider_state_binding.py"
$prepare = Join-Path $repoRoot "scripts\prepare_wp22a_provider_workdir.ps1"

if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) { throw "WP22A_PROVIDER_RUNNER_TEMP_REQUIRED" }
if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) { throw "WP22A_PROVIDER_LOCALAPPDATA_REQUIRED" }
$workRoot = Join-Path $env:RUNNER_TEMP ("omni-cio-wp22a-provider-" + $env:GITHUB_RUN_ID + "-" + $env:GITHUB_RUN_ATTEMPT)
$stateRoot = Join-Path $env:LOCALAPPDATA "OmniCIO\wp22a-provider-state"
$statePath = Join-Path $stateRoot "terraform.tfstate"
$stateBackupPath = Join-Path $stateRoot "terraform.tfstate.backup"
$planPath = Join-Path $workRoot "wp22a.tfplan"
$planJson = Join-Path $workRoot "wp22a-plan.json"
$stateJson = Join-Path $workRoot "wp22a-state.json"
$tofuLog = Join-Path $workRoot "tofu.log"

function Invoke-SanitizedPython {
    param(
        [Parameter(Mandatory = $true)][string]$Script,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    $output = @(& $python $Script @Arguments 2>$null)
    if ($LASTEXITCODE -ne 0) {
        if ($output.Count -gt 0) { $output | Select-Object -Last 1 | Write-Output }
        throw "WP22A_PROVIDER_GUARD_FAILED"
    }
    if ($output.Count -gt 0) { $output | Select-Object -Last 1 | Write-Output }
}

function Invoke-TofuQuiet {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    & $script:tofuExe @Arguments *> $tofuLog
    if ($LASTEXITCODE -ne 0) { throw "WP22A_PROVIDER_OPENTOFU_OPERATION_FAILED" }
}

function Export-StateJson {
    if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
        throw "WP22A_PROVIDER_STATE_MISSING"
    }
    Remove-Item -LiteralPath $stateJson -Force -ErrorAction SilentlyContinue
    & $script:tofuExe $script:chdirArg show "-state=$statePath" "-json-into=$stateJson" *> $tofuLog
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $stateJson -PathType Leaf)) {
        throw "WP22A_PROVIDER_STATE_EXPORT_FAILED"
    }
}

function Assert-StateTrustedAndBound {
    Export-StateJson
    Invoke-SanitizedPython -Script $stateGuard -Arguments @("state", $stateJson)
    Invoke-SanitizedPython -Script $bindingGuard -Arguments @($stateJson)
}

$previousTfVars = @{
    TF_VAR_cloudflare_account_id = $env:TF_VAR_cloudflare_account_id
    TF_VAR_cloudflare_zone_id = $env:TF_VAR_cloudflare_zone_id
    TF_VAR_hostname = $env:TF_VAR_hostname
    TF_VAR_team_name = $env:TF_VAR_team_name
    TF_CLI_CONFIG_FILE = $env:TF_CLI_CONFIG_FILE
}

try {
    $env:TF_VAR_cloudflare_account_id = $env:WP22A_CLOUDFLARE_ACCOUNT_ID
    $env:TF_VAR_cloudflare_zone_id = $env:WP22A_CLOUDFLARE_ZONE_ID
    $env:TF_VAR_hostname = $env:WP22A_EXTERNAL_HOST
    $env:TF_VAR_team_name = $env:WP22A_CLOUDFLARE_TEAM_NAME

    Invoke-SanitizedPython -Script $liveGuard -Arguments @("preflight")
    if ($Operation -eq "preflight") {
        Write-Output '{"status":"PASS","reason":"WP22A_PROVIDER_PHASE_B_PREFLIGHT_COMPLETE"}'
        exit 0
    }

    $preparedRaw = @(& $prepare -WorkRoot $workRoot -AsJson 2>$null)
    if ($LASTEXITCODE -ne 0 -or $preparedRaw.Count -ne 1) {
        throw "WP22A_PROVIDER_WORKDIR_PREPARE_FAILED"
    }
    try { $prepared = ([string]$preparedRaw[0]) | ConvertFrom-Json -ErrorAction Stop }
    catch { throw "WP22A_PROVIDER_WORKDIR_OUTPUT_INVALID" }
    $script:tofuExe = ([string]$prepared.tofu_exe).Trim()
    $iacRoot = ([string]$prepared.iac_root).Trim()
    $env:TF_CLI_CONFIG_FILE = ([string]$prepared.cli_config_path).Trim()
    if (-not (Test-Path -LiteralPath $script:tofuExe -PathType Leaf)) { throw "WP22A_PROVIDER_OPENTOFU_MISSING" }
    if (-not (Test-Path -LiteralPath $iacRoot -PathType Container)) { throw "WP22A_PROVIDER_IAC_ROOT_MISSING" }
    $script:chdirArg = "-chdir=$iacRoot"

    $stateExists = Test-Path -LiteralPath $statePath -PathType Leaf
    if ($stateExists) {
        Assert-StateTrustedAndBound
    }
    elseif ($Operation -in @("verify", "verify-live", "destroy-plan", "destroy")) {
        throw "WP22A_PROVIDER_STATE_REQUIRED"
    }
    else {
        Invoke-SanitizedPython -Script $liveGuard -Arguments @("assert-empty")
    }

    if ($Operation -in @("verify", "verify-live")) {
        Invoke-SanitizedPython -Script $liveGuard -Arguments @($Operation)
        Write-Output '{"status":"PASS","reason":"WP22A_PROVIDER_PHASE_B_VERIFY_COMPLETE"}'
        exit 0
    }

    New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
    Remove-Item -LiteralPath $planPath, $planJson, $tofuLog -Force -ErrorAction SilentlyContinue

    $isDestroy = $Operation -in @("destroy-plan", "destroy")
    $planArguments = @(
        $script:chdirArg,
        "plan",
        "-input=false",
        "-no-color",
        "-lock-timeout=30s",
        "-state=$statePath",
        "-out=$planPath"
    )
    if ($isDestroy) { $planArguments += "-destroy" }
    Invoke-TofuQuiet -Arguments $planArguments

    & $script:tofuExe $script:chdirArg show "-plan=$planPath" "-json-into=$planJson" *> $tofuLog
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $planJson -PathType Leaf)) {
        throw "WP22A_PROVIDER_PLAN_EXPORT_FAILED"
    }
    $guardArguments = @("plan", $planJson)
    if ($isDestroy) { $guardArguments += "--destroy" }
    Invoke-SanitizedPython -Script $stateGuard -Arguments $guardArguments

    if ($Operation -in @("plan", "destroy-plan")) {
        Write-Output '{"status":"PASS","reason":"WP22A_PROVIDER_PHASE_B_PLAN_GUARDED"}'
        exit 0
    }

    if ($Operation -eq "apply" -and $Confirmation -ne "APPLY_WP22A_PROVIDER") {
        throw "WP22A_PROVIDER_APPLY_CONFIRMATION_REQUIRED"
    }
    if ($Operation -eq "destroy" -and $Confirmation -ne "DESTROY_WP22A_PROVIDER") {
        throw "WP22A_PROVIDER_DESTROY_CONFIRMATION_REQUIRED"
    }

    Invoke-TofuQuiet -Arguments @(
        $script:chdirArg,
        "apply",
        "-input=false",
        "-no-color",
        "-lock-timeout=30s",
        "-state=$statePath",
        "-state-out=$statePath",
        "-backup=$stateBackupPath",
        $planPath
    )

    if ($Operation -eq "apply") {
        Assert-StateTrustedAndBound
        Invoke-SanitizedPython -Script $liveGuard -Arguments @("verify")
        Write-Output '{"status":"PASS","reason":"WP22A_PROVIDER_PHASE_B_APPLY_COMPLETE"}'
        exit 0
    }

    Invoke-SanitizedPython -Script $liveGuard -Arguments @("assert-empty")
    Remove-Item -LiteralPath $statePath, $stateBackupPath -Force -ErrorAction SilentlyContinue
    Write-Output '{"status":"PASS","reason":"WP22A_PROVIDER_PHASE_B_DESTROY_COMPLETE"}'
}
finally {
    Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue
    foreach ($entry in $previousTfVars.GetEnumerator()) {
        if ($null -eq $entry.Value) {
            Remove-Item ("Env:" + [string]$entry.Key) -ErrorAction SilentlyContinue
        }
        else {
            [Environment]::SetEnvironmentVariable([string]$entry.Key, [string]$entry.Value)
        }
    }
}
