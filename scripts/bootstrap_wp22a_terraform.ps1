[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$DestinationRoot
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$version = "1.15.6"
$archiveName = "terraform_${version}_windows_amd64.zip"
$expectedSha256 = @(
    "56b4d3a1",
    "57e346f8",
    "fc1e9425",
    "4d0a944e",
    "6fec81f5",
    "8ddd43eb",
    "274b8e0e",
    "bb56e334"
) -join ""
$url = "https://releases.hashicorp.com/terraform/$version/$archiveName"

$root = [System.IO.Path]::GetFullPath($DestinationRoot)
$installRoot = Join-Path $root "terraform-$version-windows-amd64"
$terraform = Join-Path $installRoot "terraform.exe"

if (Test-Path -LiteralPath $terraform -PathType Leaf) {
    $existing = @(& $terraform version -json 2>$null)
    if ($LASTEXITCODE -eq 0 -and (($existing -join "`n") -match '"terraform_version"\s*:\s*"1\.15\.6"')) {
        Write-Output $terraform
        exit 0
    }
    Remove-Item -LiteralPath $installRoot -Recurse -Force -ErrorAction Stop
}

New-Item -ItemType Directory -Path $root -Force | Out-Null
$tempArchive = Join-Path $root ("terraform-" + [guid]::NewGuid().ToString("N") + ".zip")
$tempExtract = Join-Path $root ("terraform-" + [guid]::NewGuid().ToString("N"))
try {
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $tempArchive
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $tempArchive -ErrorAction Stop).Hash.ToLowerInvariant()
    if ($actual -ne $expectedSha256) { throw "WP22A_TERRAFORM_ARCHIVE_HASH_MISMATCH" }

    New-Item -ItemType Directory -Path $tempExtract -Force | Out-Null
    Expand-Archive -LiteralPath $tempArchive -DestinationPath $tempExtract -Force
    $extracted = Join-Path $tempExtract "terraform.exe"
    if (-not (Test-Path -LiteralPath $extracted -PathType Leaf)) { throw "WP22A_TERRAFORM_BINARY_MISSING" }

    New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
    Copy-Item -LiteralPath $extracted -Destination $terraform -Force
    $versionJson = @(& $terraform version -json 2>$null)
    if ($LASTEXITCODE -ne 0 -or (($versionJson -join "`n") -notmatch '"terraform_version"\s*:\s*"1\.15\.6"')) {
        throw "WP22A_TERRAFORM_VERSION_INVALID"
    }
}
finally {
    Remove-Item -LiteralPath $tempArchive -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Output $terraform