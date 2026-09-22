[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Verify,
    [string]$RootCertificatePath,
    [string]$SubCertificatePath,
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

if ($Apply -and $Verify) {
    throw "Choose -Apply or -Verify, not both."
}
if ($env:OS -ne "Windows_NT") {
    throw "TBANK_CA_TRUST_WINDOWS_REQUIRED"
}

$rootCommonName = "Russian Trusted Root CA"
$subCommonName = "Russian Trusted Sub CA"
$rootStore = "Cert:\LocalMachine\Root"
$subStore = "Cert:\LocalMachine\CA"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-CertificateCurrent {
    param([Parameter(Mandatory = $true)][System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate)
    $now = [DateTime]::UtcNow
    return (
        $Certificate.NotBefore.ToUniversalTime() -le $now -and
        $Certificate.NotAfter.ToUniversalTime() -ge $now
    )
}

function Test-CertificateAuthority {
    param([Parameter(Mandatory = $true)][System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate)
    foreach ($extension in $Certificate.Extensions) {
        if ($extension.Oid.Value -eq "2.5.29.19") {
            $basic = [System.Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]$extension
            return [bool]$basic.CertificateAuthority
        }
    }
    return $false
}

function Get-SimpleName {
    param(
        [Parameter(Mandatory = $true)][System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate,
        [switch]$Issuer
    )
    return $Certificate.GetNameInfo(
        [System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName,
        [bool]$Issuer
    )
}

function Get-TrustedCandidates {
    param(
        [Parameter(Mandatory = $true)][string]$StorePath,
        [Parameter(Mandatory = $true)][string]$CommonName,
        [string]$IssuerCommonName = ""
    )
    return @(
        Get-ChildItem -Path $StorePath -ErrorAction Stop |
            Where-Object {
                (Get-SimpleName -Certificate $_) -eq $CommonName -and
                (Test-CertificateCurrent -Certificate $_) -and
                (Test-CertificateAuthority -Certificate $_) -and
                (
                    [string]::IsNullOrWhiteSpace($IssuerCommonName) -or
                    (Get-SimpleName -Certificate $_ -Issuer) -eq $IssuerCommonName
                )
            }
    )
}

function Read-Certificate {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedCommonName,
        [string]$ExpectedIssuerCommonName = "",
        [switch]$SelfIssued
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "TBANK_CA_TRUST_CERTIFICATE_FILE_MISSING"
    }
    $certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new(
        (Resolve-Path -LiteralPath $Path).Path
    )
    if ((Get-SimpleName -Certificate $certificate) -ne $ExpectedCommonName) {
        throw "TBANK_CA_TRUST_CERTIFICATE_SUBJECT_INVALID"
    }
    if (-not (Test-CertificateCurrent -Certificate $certificate)) {
        throw "TBANK_CA_TRUST_CERTIFICATE_EXPIRED_OR_NOT_YET_VALID"
    }
    if (-not (Test-CertificateAuthority -Certificate $certificate)) {
        throw "TBANK_CA_TRUST_CERTIFICATE_NOT_CA"
    }
    $issuer = Get-SimpleName -Certificate $certificate -Issuer
    if ($SelfIssued -and $issuer -ne $ExpectedCommonName) {
        throw "TBANK_CA_TRUST_ROOT_NOT_SELF_ISSUED"
    }
    if (
        -not [string]::IsNullOrWhiteSpace($ExpectedIssuerCommonName) -and
        $issuer -ne $ExpectedIssuerCommonName
    ) {
        throw "TBANK_CA_TRUST_INTERMEDIATE_ISSUER_INVALID"
    }
    return $certificate
}

function Test-ThumbprintPresent {
    param(
        [Parameter(Mandatory = $true)][string]$StorePath,
        [Parameter(Mandatory = $true)][string]$Thumbprint
    )
    return [bool](
        Get-ChildItem -Path $StorePath -ErrorAction Stop |
            Where-Object { $_.Thumbprint -eq $Thumbprint } |
            Select-Object -First 1
    )
}

function Import-IfMissing {
    param(
        [Parameter(Mandatory = $true)][System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate,
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$StorePath
    )
    if (Test-ThumbprintPresent -StorePath $StorePath -Thumbprint $Certificate.Thumbprint) {
        return $false
    }
    Import-Certificate -FilePath $SourcePath -CertStoreLocation $StorePath -ErrorAction Stop | Out-Null
    if (-not (Test-ThumbprintPresent -StorePath $StorePath -Thumbprint $Certificate.Thumbprint)) {
        throw "TBANK_CA_TRUST_IMPORT_POSTCONDITION_FAILED"
    }
    return $true
}

$mutationsAttempted = $false
$rootImported = $false
$subImported = $false

if ($Apply) {
    if (-not (Test-Administrator)) {
        throw "TBANK_CA_TRUST_ADMIN_REQUIRED"
    }
    if ([string]::IsNullOrWhiteSpace($RootCertificatePath) -or [string]::IsNullOrWhiteSpace($SubCertificatePath)) {
        throw "TBANK_CA_TRUST_CERTIFICATE_PATHS_REQUIRED"
    }

    $rootCertificate = Read-Certificate -Path $RootCertificatePath -ExpectedCommonName $rootCommonName -SelfIssued
    $subCertificate = Read-Certificate -Path $SubCertificatePath -ExpectedCommonName $subCommonName -ExpectedIssuerCommonName $rootCommonName

    $mutationsAttempted = $true
    $rootImported = Import-IfMissing -Certificate $rootCertificate -SourcePath $RootCertificatePath -StorePath $rootStore
    $subImported = Import-IfMissing -Certificate $subCertificate -SourcePath $SubCertificatePath -StorePath $subStore
}

$roots = Get-TrustedCandidates -StorePath $rootStore -CommonName $rootCommonName
$subs = Get-TrustedCandidates -StorePath $subStore -CommonName $subCommonName -IssuerCommonName $rootCommonName
$ready = $roots.Count -gt 0 -and $subs.Count -gt 0
$reason = if ($ready) { "TBANK_CA_TRUST_STORE_READY" } else { "TBANK_CA_TRUST_STORE_NOT_READY" }

$result = [ordered]@{
    schema_version = "1"
    reason = $reason
    root_ca_present = [bool]($roots.Count -gt 0)
    intermediate_ca_present = [bool]($subs.Count -gt 0)
    mutations_attempted = [bool]$mutationsAttempted
    root_imported = [bool]$rootImported
    intermediate_imported = [bool]$subImported
    administrator = [bool](Test-Administrator)
    ready = [bool]$ready
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 4
}
else {
    $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value }
}

if (-not $ready) {
    exit 71
}
