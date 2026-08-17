[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$WorkRoot,
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") { throw "WP22A_PROVIDER_WORKDIR_REQUIRES_WINDOWS" }

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$sourceRoot = Join-Path $repoRoot "infrastructure\cloudflare\wp22a"
$sourceLockPath = Join-Path $sourceRoot ".terraform.lock.hcl"
$bootstrap = Join-Path $repoRoot "scripts\bootstrap_wp22a_terraform.ps1"
$providerBootstrap = Join-Path $repoRoot "scripts\bootstrap_wp22a_cloudflare_provider.ps1"
$providerAddress = "registry.terraform.io/cloudflare/cloudflare"
$root = [System.IO.Path]::GetFullPath($WorkRoot)
$toolRoot = Join-Path $root "tools"
$iacRoot = Join-Path $root "iac"
$mirrorRoot = Join-Path $root "provider-mirror"
$cliConfigPath = Join-Path $root "tofu.tfrc"

Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $iacRoot -Force | Out-Null
Copy-Item -Path (Join-Path $sourceRoot "*.tf") -Destination $iacRoot -Force
Copy-Item -LiteralPath $sourceLockPath -Destination $iacRoot -Force

$tofuOutput = @(& $bootstrap -DestinationRoot $toolRoot)
if ($LASTEXITCODE -ne 0 -or $tofuOutput.Count -ne 1) {
    throw "WP22A_PROVIDER_OPENTOFU_BOOTSTRAP_FAILED"
}
$tofuExe = ([string]$tofuOutput[0]).Trim()
if (-not (Test-Path -LiteralPath $tofuExe -PathType Leaf)) {
    throw "WP22A_PROVIDER_OPENTOFU_BINARY_MISSING"
}

$providerOutput = @(& $providerBootstrap -DestinationRoot $toolRoot)
if ($LASTEXITCODE -ne 0 -or $providerOutput.Count -ne 1) {
    throw "WP22A_PROVIDER_CLOUDFLARE_BOOTSTRAP_FAILED"
}
$providerArchive = ([string]$providerOutput[0]).Trim()
if (-not (Test-Path -LiteralPath $providerArchive -PathType Leaf)) {
    throw "WP22A_PROVIDER_CLOUDFLARE_ARCHIVE_MISSING"
}

$providerArchiveSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $providerArchive -ErrorAction Stop).Hash.ToLowerInvariant()
$sourceLockText = Get-Content -LiteralPath $sourceLockPath -Raw -ErrorAction Stop
if ($sourceLockText -notmatch [regex]::Escape("zh:$providerArchiveSha256")) {
    throw "WP22A_PROVIDER_TRUSTED_ZIP_LOCK_MISSING"
}

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

$chdirArg = "-chdir=$iacRoot"
$fsMirrorArg = "-fs-mirror=$mirrorConfigPath"
$platformArg = "-platform=windows_amd64"
$previousCliConfig = $env:TF_CLI_CONFIG_FILE
$env:TF_CLI_CONFIG_FILE = $cliConfigPath
try {
    & $tofuExe $chdirArg fmt -check -diff
    if ($LASTEXITCODE -ne 0) { throw "WP22A_PROVIDER_OPENTOFU_FMT_FAILED" }

    & $tofuExe $chdirArg providers lock $fsMirrorArg $platformArg $providerAddress
    if ($LASTEXITCODE -ne 0) {
        throw "WP22A_PROVIDER_CONTENT_LOCK_DERIVATION_FAILED"
    }

    & $tofuExe $chdirArg init -backend=false -input=false -no-color -lockfile=readonly
    if ($LASTEXITCODE -ne 0) { throw "WP22A_PROVIDER_OPENTOFU_INIT_FAILED" }
    & $tofuExe $chdirArg validate -no-color
    if ($LASTEXITCODE -ne 0) { throw "WP22A_PROVIDER_OPENTOFU_VALIDATE_FAILED" }
}
finally {
    if ($null -eq $previousCliConfig) {
        Remove-Item Env:TF_CLI_CONFIG_FILE -ErrorAction SilentlyContinue
    }
    else {
        $env:TF_CLI_CONFIG_FILE = $previousCliConfig
    }
}

$result = [ordered]@{
    tofu_exe = $tofuExe
    iac_root = $iacRoot
    cli_config_path = $cliConfigPath
}
if ($AsJson) {
    $result | ConvertTo-Json -Depth 4 -Compress
}
else {
    $result
}
