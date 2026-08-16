[CmdletBinding()]
param()

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") { throw "WP22A_TERRAFORM_VALIDATION_REQUIRES_WINDOWS" }
if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) { throw "WP22A_RUNNER_TEMP_REQUIRED" }

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$bootstrap = Join-Path $repoRoot "scripts\bootstrap_wp22a_terraform.ps1"
$sourceRoot = Join-Path $repoRoot "infrastructure\cloudflare\wp22a"
$toolRoot = Join-Path $env:RUNNER_TEMP "omni-cio-wp22a-tools"
$runSuffix = "$($env:GITHUB_RUN_ID)-$($env:GITHUB_RUN_ATTEMPT)".Trim("-")
if ([string]::IsNullOrWhiteSpace($runSuffix)) { $runSuffix = [guid]::NewGuid().ToString("N") }
$validateRoot = Join-Path $env:RUNNER_TEMP ("omni-cio-wp22a-tf-" + $runSuffix)

$terraform = @(& $bootstrap -DestinationRoot $toolRoot)
if ($LASTEXITCODE -ne 0 -or $terraform.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$terraform[0])) {
    throw "WP22A_TERRAFORM_BOOTSTRAP_FAILED"
}
$terraformExe = ([string]$terraform[0]).Trim()
if (-not (Test-Path -LiteralPath $terraformExe -PathType Leaf)) {
    throw "WP22A_TERRAFORM_BINARY_UNAVAILABLE"
}

Remove-Item -LiteralPath $validateRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $validateRoot -Force | Out-Null
Copy-Item -Path (Join-Path $sourceRoot "*.tf") -Destination $validateRoot -Force
Copy-Item -LiteralPath (Join-Path $sourceRoot ".terraform.lock.hcl") -Destination $validateRoot -Force

try {
    & $terraformExe -chdir=$validateRoot fmt -check -diff
    if ($LASTEXITCODE -ne 0) { throw "WP22A_TERRAFORM_FMT_FAILED" }

    & $terraformExe -chdir=$validateRoot init -backend=false -input=false -no-color -lockfile=readonly
    if ($LASTEXITCODE -ne 0) { throw "WP22A_TERRAFORM_INIT_FAILED" }

    & $terraformExe -chdir=$validateRoot validate -no-color
    if ($LASTEXITCODE -ne 0) { throw "WP22A_TERRAFORM_VALIDATE_FAILED" }

    $providers = @(& $terraformExe -chdir=$validateRoot providers 2>&1) -join "`n"
    if ($LASTEXITCODE -ne 0 -or $providers -notmatch 'registry\.terraform\.io/cloudflare/cloudflare') {
        throw "WP22A_TERRAFORM_PROVIDER_LOCK_INVALID"
    }

    Write-Host "WP22A Terraform validation contract passed."
}
finally {
    Remove-Item -LiteralPath $validateRoot -Recurse -Force -ErrorAction SilentlyContinue
}
