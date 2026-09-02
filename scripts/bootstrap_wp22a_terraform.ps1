[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$DestinationRoot
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

# Historical filename retained to avoid a needless contract-path migration. WP22A now
# uses the OpenTofu CLI because the reviewed HashiCorp binary distribution is not
# reachable from the protected Lenovo execution region. The GitHub release asset is
# pinned by exact version and SHA-256 before extraction.
$version = "1.12.5"
$archiveName = "tofu_${version}_windows_amd64.zip"
$expectedSha256 = @(
    "465adc4b",
    "df4aa80c",
    "650387b7",
    "ada2cf75",
    "0f7908bf",
    "1fae7f35",
    "b05402c3",
    "84e79928"
) -join ""
$url = "https://github.com/opentofu/opentofu/releases/download/v$version/$archiveName"
$maxDownloadAttempts = 3

$root = [System.IO.Path]::GetFullPath($DestinationRoot)
$installRoot = Join-Path $root "opentofu-$version-windows-amd64"
$tofu = Join-Path $installRoot "tofu.exe"

if (Test-Path -LiteralPath $tofu -PathType Leaf) {
    $existing = @(& $tofu version -json 2>$null)
    if ($LASTEXITCODE -eq 0 -and (($existing -join "`n") -match '"terraform_version"\s*:\s*"1\.12\.5"')) {
        Write-Output $tofu
        exit 0
    }
    Remove-Item -LiteralPath $installRoot -Recurse -Force -ErrorAction Stop
}

New-Item -ItemType Directory -Path $root -Force | Out-Null
$tempArchive = Join-Path $root ("opentofu-" + [guid]::NewGuid().ToString("N") + ".zip")
$tempExtract = Join-Path $root ("opentofu-" + [guid]::NewGuid().ToString("N"))
try {
    $downloaded = $false
    for ($attempt = 1; $attempt -le $maxDownloadAttempts; $attempt++) {
        Remove-Item -LiteralPath $tempArchive -Force -ErrorAction SilentlyContinue
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $tempArchive -TimeoutSec 90
            $downloaded = $true
            break
        }
        catch {
            if ($attempt -eq $maxDownloadAttempts) {
                throw "WP22A_OPENTOFU_DOWNLOAD_FAILED_AFTER_RETRIES"
            }
            Start-Sleep -Seconds ($attempt * 2)
        }
    }
    if (-not $downloaded) { throw "WP22A_OPENTOFU_DOWNLOAD_FAILED_AFTER_RETRIES" }

    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $tempArchive -ErrorAction Stop).Hash.ToLowerInvariant()
    if ($actual -ne $expectedSha256) { throw "WP22A_OPENTOFU_ARCHIVE_HASH_MISMATCH" }

    New-Item -ItemType Directory -Path $tempExtract -Force | Out-Null
    Expand-Archive -LiteralPath $tempArchive -DestinationPath $tempExtract -Force
    $extracted = Join-Path $tempExtract "tofu.exe"
    if (-not (Test-Path -LiteralPath $extracted -PathType Leaf)) { throw "WP22A_OPENTOFU_BINARY_MISSING" }

    New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
    Copy-Item -LiteralPath $extracted -Destination $tofu -Force
    $versionJson = @(& $tofu version -json 2>$null)
    if ($LASTEXITCODE -ne 0 -or (($versionJson -join "`n") -notmatch '"terraform_version"\s*:\s*"1\.12\.5"')) {
        throw "WP22A_OPENTOFU_VERSION_INVALID"
    }
}
finally {
    Remove-Item -LiteralPath $tempArchive -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Output $tofu
