[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$DestinationRoot
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$version = "5.22.0"
$archiveName = "terraform-provider-cloudflare_${version}_windows_amd64.zip"
$expectedSha256 = @(
    "ca4bf167",
    "42a7e593",
    "19a482f0",
    "03d32f6f",
    "6abbc5fb",
    "f862916c",
    "e1a13627",
    "8e6d420d"
) -join ""
$url = "https://github.com/cloudflare/terraform-provider-cloudflare/releases/download/v$version/$archiveName"
$maxDownloadAttempts = 3

$root = [System.IO.Path]::GetFullPath($DestinationRoot)
$cacheRoot = Join-Path $root "cloudflare-provider-$version-windows-amd64"
$archivePath = Join-Path $cacheRoot $archiveName

if (Test-Path -LiteralPath $archivePath -PathType Leaf) {
    $existingSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath -ErrorAction Stop).Hash.ToLowerInvariant()
    if ($existingSha -eq $expectedSha256) {
        Write-Output $archivePath
        exit 0
    }
    Remove-Item -LiteralPath $cacheRoot -Recurse -Force -ErrorAction Stop
}

New-Item -ItemType Directory -Path $root -Force | Out-Null
$tempArchive = Join-Path $root ("cloudflare-provider-" + [guid]::NewGuid().ToString("N") + ".zip")
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
                throw "WP22A_CLOUDFLARE_PROVIDER_DOWNLOAD_FAILED_AFTER_RETRIES"
            }
            Start-Sleep -Seconds ($attempt * 2)
        }
    }
    if (-not $downloaded) { throw "WP22A_CLOUDFLARE_PROVIDER_DOWNLOAD_FAILED_AFTER_RETRIES" }

    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $tempArchive -ErrorAction Stop).Hash.ToLowerInvariant()
    if ($actual -ne $expectedSha256) { throw "WP22A_CLOUDFLARE_PROVIDER_ARCHIVE_HASH_MISMATCH" }

    New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null
    Move-Item -LiteralPath $tempArchive -Destination $archivePath -Force
}
finally {
    Remove-Item -LiteralPath $tempArchive -Force -ErrorAction SilentlyContinue
}

Write-Output $archivePath
