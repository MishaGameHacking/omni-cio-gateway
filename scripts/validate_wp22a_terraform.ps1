[CmdletBinding()]
param()

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") { throw "WP22A_IAC_VALIDATION_REQUIRES_WINDOWS" }
if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) { throw "WP22A_RUNNER_TEMP_REQUIRED" }

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
# Historical path retained as a stable repository contract; the bootstrap now returns
# the pinned OpenTofu executable rather than a HashiCorp Terraform executable.
$bootstrap = Join-Path $repoRoot "scripts\bootstrap_wp22a_terraform.ps1"
$providerBootstrap = Join-Path $repoRoot "scripts\bootstrap_wp22a_cloudflare_provider.ps1"
$sourceRoot = Join-Path $repoRoot "infrastructure\cloudflare\wp22a"
$toolRoot = Join-Path $env:RUNNER_TEMP "omni-cio-wp22a-tools"
$runSuffix = "$($env:GITHUB_RUN_ID)-$($env:GITHUB_RUN_ATTEMPT)".Trim("-")
if ([string]::IsNullOrWhiteSpace($runSuffix)) { $runSuffix = [guid]::NewGuid().ToString("N") }
$validateRoot = Join-Path $env:RUNNER_TEMP ("omni-cio-wp22a-iac-" + $runSuffix)
$mirrorRoot = Join-Path $env:RUNNER_TEMP ("omni-cio-wp22a-provider-mirror-" + $runSuffix)
$cliConfigPath = Join-Path $env:RUNNER_TEMP ("omni-cio-wp22a-tofu-" + $runSuffix + ".tfrc")

$tofu = @(& $bootstrap -DestinationRoot $toolRoot)
if ($LASTEXITCODE -ne 0 -or $tofu.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$tofu[0])) {
    throw "WP22A_OPENTOFU_BOOTSTRAP_FAILED"
}
$tofuExe = ([string]$tofu[0]).Trim()
if (-not (Test-Path -LiteralPath $tofuExe -PathType Leaf)) {
    throw "WP22A_OPENTOFU_BINARY_UNAVAILABLE"
}

$providerArchiveOutput = @(& $providerBootstrap -DestinationRoot $toolRoot)
if ($LASTEXITCODE -ne 0 -or $providerArchiveOutput.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$providerArchiveOutput[0])) {
    throw "WP22A_CLOUDFLARE_PROVIDER_BOOTSTRAP_FAILED"
}
$providerArchive = ([string]$providerArchiveOutput[0]).Trim()
if (-not (Test-Path -LiteralPath $providerArchive -PathType Leaf)) {
    throw "WP22A_CLOUDFLARE_PROVIDER_ARCHIVE_UNAVAILABLE"
}

Remove-Item -LiteralPath $validateRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $mirrorRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $cliConfigPath -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $validateRoot -Force | Out-Null
Copy-Item -Path (Join-Path $sourceRoot "*.tf") -Destination $validateRoot -Force
Copy-Item -LiteralPath (Join-Path $sourceRoot ".terraform.lock.hcl") -Destination $validateRoot -Force

$providerMirrorDir = Join-Path $mirrorRoot "registry.terraform.io\cloudflare\cloudflare"
New-Item -ItemType Directory -Path $providerMirrorDir -Force | Out-Null
Copy-Item -LiteralPath $providerArchive -Destination $providerMirrorDir -Force
$mirrorConfigPath = ([System.IO.Path]::GetFullPath($mirrorRoot)).Replace('\', '/')
$cliConfig = @"
provider_installation {
  filesystem_mirror {
    path    = "$mirrorConfigPath"
    include = ["registry.terraform.io/cloudflare/cloudflare"]
  }
  direct {
    exclude = ["registry.terraform.io/cloudflare/cloudflare"]
  }
}
"@
Set-Content -LiteralPath $cliConfigPath -Value $cliConfig -Encoding Ascii

$chdirArg = "-chdir=$validateRoot"
$previousCliConfig = $env:TF_CLI_CONFIG_FILE
$env:TF_CLI_CONFIG_FILE = $cliConfigPath

try {
    & $tofuExe $chdirArg fmt -check -diff
    if ($LASTEXITCODE -ne 0) { throw "WP22A_OPENTOFU_FMT_FAILED" }

    & $tofuExe $chdirArg init -backend=false -input=false -no-color -lockfile=readonly
    if ($LASTEXITCODE -ne 0) { throw "WP22A_OPENTOFU_INIT_FAILED" }

    & $tofuExe $chdirArg validate -no-color
    if ($LASTEXITCODE -ne 0) { throw "WP22A_OPENTOFU_VALIDATE_FAILED" }

    $providers = @(& $tofuExe $chdirArg providers 2>&1) -join "`n"
    if ($LASTEXITCODE -ne 0 -or $providers -notmatch 'registry\.terraform\.io/cloudflare/cloudflare') {
        throw "WP22A_OPENTOFU_PROVIDER_LOCK_INVALID"
    }

    Write-Host "WP22A OpenTofu Cloudflare IaC validation contract passed."
}
finally {
    if ($null -eq $previousCliConfig) {
        Remove-Item Env:TF_CLI_CONFIG_FILE -ErrorAction SilentlyContinue
    }
    else {
        $env:TF_CLI_CONFIG_FILE = $previousCliConfig
    }
    Remove-Item -LiteralPath $validateRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $mirrorRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $cliConfigPath -Force -ErrorAction SilentlyContinue
}
