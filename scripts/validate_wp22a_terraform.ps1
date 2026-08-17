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
$sourceLockPath = Join-Path $sourceRoot ".terraform.lock.hcl"
$providerAddress = "registry.terraform.io/cloudflare/cloudflare"
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

# The provider bootstrap already authenticates the exact publisher ZIP against its
# reviewed SHA-256. Derive the lock comparison from that authenticated archive so the
# validator does not duplicate a high-entropy trust literal that secret scanning can
# legitimately classify as a potential credential.
$providerArchiveSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $providerArchive -ErrorAction Stop).Hash.ToLowerInvariant()
$sourceLockText = Get-Content -LiteralPath $sourceLockPath -Raw -ErrorAction Stop
if ($sourceLockText -notmatch [regex]::Escape("zh:$providerArchiveSha256")) {
    throw "WP22A_TRUSTED_PROVIDER_ZIP_LOCK_MISSING"
}
$sourceLockShaBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourceLockPath -ErrorAction Stop).Hash

Remove-Item -LiteralPath $validateRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $mirrorRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $cliConfigPath -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $validateRoot -Force | Out-Null
Copy-Item -Path (Join-Path $sourceRoot "*.tf") -Destination $validateRoot -Force
Copy-Item -LiteralPath $sourceLockPath -Destination $validateRoot -Force
$validateLockPath = Join-Path $validateRoot ".terraform.lock.hcl"

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
$fsMirrorArg = "-fs-mirror=$mirrorConfigPath"
$platformArg = "-platform=windows_amd64"
$previousCliConfig = $env:TF_CLI_CONFIG_FILE
$env:TF_CLI_CONFIG_FILE = $cliConfigPath

try {
    & $tofuExe $chdirArg fmt -check -diff
    if ($LASTEXITCODE -ne 0) { throw "WP22A_OPENTOFU_FMT_FAILED" }

    # OpenTofu 1.12 prefers h1 content hashes for installed/unpacked provider packages.
    # The committed lock remains the reviewed publisher-ZIP trust anchor (zh), while
    # this isolated lock copy derives the matching h1 from the already SHA-256-verified
    # Windows package in our exact filesystem mirror. No registry fallback is allowed.
    & $tofuExe $chdirArg providers lock $fsMirrorArg $platformArg $providerAddress
    if ($LASTEXITCODE -ne 0) { throw "WP22A_OPENTOFU_PROVIDER_LOCK_DERIVATION_FAILED" }

    $sourceLockShaAfter = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourceLockPath -ErrorAction Stop).Hash
    if ($sourceLockShaAfter -ne $sourceLockShaBefore) {
        throw "WP22A_SOURCE_PROVIDER_LOCK_MUTATED"
    }
    $derivedLockText = Get-Content -LiteralPath $validateLockPath -Raw -ErrorAction Stop
    if ($derivedLockText -notmatch '"h1:[A-Za-z0-9+/]+={0,2}"') {
        throw "WP22A_PROVIDER_CONTENT_LOCK_MISSING"
    }

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