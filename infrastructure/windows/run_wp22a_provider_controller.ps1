[CmdletBinding()]
param(
    [switch]$ProcessQueue,
    [switch]$ValidateOnly,
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$modeCount = @(@($ProcessQueue, $ValidateOnly) | Where-Object { $_ }).Count
if ($modeCount -ne 1) { throw "Choose exactly one of -ProcessQueue or -ValidateOnly." }
if ($env:OS -ne "Windows_NT") { throw "WP22A_PROVIDER_CONTROLLER_WINDOWS_REQUIRED" }

$protectedRoot = "C:\ProgramData\OmniCIO\private\wp22a-provider-controller"
$configPath = Join-Path $protectedRoot "controller.json"
$replayRoot = Join-Path $protectedRoot "replay"
$requestRoot = "C:\ProgramData\OmniCIO\runtime\wp22a-provider-requests"
$resultRoot = "C:\ProgramData\OmniCIO\runtime\wp22a-provider-results"
$expectedRepository = "MishaGameHacking/omni-cio-gateway"
$expectedRepositoryId = "1312247309"
$expectedOwnerActorId = "201947041"
$expectedAudience = "omni-cio-wp22a-provider-controller"
$expectedIssuer = "https://token.actions.githubusercontent.com"
$expectedWorkflowRef = "MishaGameHacking/omni-cio-gateway/.github/workflows/v10-wp22a-provider-activation.yml@refs/heads/main"
$oidcConfigurationUri = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
$clockSkewSeconds = 120
$maxTokenAgeSeconds = 900
$replayRetentionHours = 24

function ConvertFrom-Base64Url {
    param([Parameter(Mandatory = $true)][string]$Value)
    $normalized = $Value.Replace('-', '+').Replace('_', '/')
    switch ($normalized.Length % 4) {
        0 { }
        2 { $normalized += "==" }
        3 { $normalized += "=" }
        default { throw "WP22A_PROVIDER_OIDC_BASE64_INVALID" }
    }
    try { return [Convert]::FromBase64String($normalized) }
    catch { throw "WP22A_PROVIDER_OIDC_BASE64_INVALID" }
}

function ConvertFrom-JwtJsonPart {
    param([Parameter(Mandatory = $true)][string]$Value)
    try {
        $bytes = ConvertFrom-Base64Url -Value $Value
        $json = [System.Text.Encoding]::UTF8.GetString($bytes)
        return $json | ConvertFrom-Json -ErrorAction Stop
    }
    catch { throw "WP22A_PROVIDER_OIDC_JSON_INVALID" }
}

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Value)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Value))
        return -join ($digest | ForEach-Object { $_.ToString("x2") })
    }
    finally { $sha.Dispose() }
}

function Test-ExactStringClaim {
    param(
        [Parameter(Mandatory = $true)]$Payload,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Expected,
        [Parameter(Mandatory = $true)][string]$Reason
    )
    $property = $Payload.PSObject.Properties[$Name]
    if ($null -eq $property -or [string]$property.Value -cne $Expected) { throw $Reason }
}

function Test-OidcTimeClaims {
    param([Parameter(Mandatory = $true)]$Payload)
    foreach ($name in @("exp", "nbf", "iat")) {
        if ($null -eq $Payload.PSObject.Properties[$name]) { throw "WP22A_PROVIDER_OIDC_TIME_CLAIM_MISSING" }
    }
    try {
        $exp = [Convert]::ToInt64($Payload.exp)
        $nbf = [Convert]::ToInt64($Payload.nbf)
        $iat = [Convert]::ToInt64($Payload.iat)
    }
    catch { throw "WP22A_PROVIDER_OIDC_TIME_CLAIM_INVALID" }

    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    if ($now -gt ($exp + $clockSkewSeconds)) { throw "WP22A_PROVIDER_OIDC_EXPIRED" }
    if ($now -lt ($nbf - $clockSkewSeconds)) { throw "WP22A_PROVIDER_OIDC_NOT_YET_VALID" }
    if ($iat -gt ($now + $clockSkewSeconds)) { throw "WP22A_PROVIDER_OIDC_IAT_IN_FUTURE" }
    if (($now - $iat) -gt $maxTokenAgeSeconds) { throw "WP22A_PROVIDER_OIDC_TOO_OLD" }
    if ($exp -le $iat) { throw "WP22A_PROVIDER_OIDC_TIME_WINDOW_INVALID" }
}

function Test-OidcSignatureAndClaims {
    param(
        [Parameter(Mandatory = $true)][string]$Jwt,
        [Parameter(Mandatory = $true)][string]$ImplementationSha,
        [Parameter(Mandatory = $true)][string]$RunId
    )

    $parts = $Jwt.Split('.')
    if ($parts.Count -ne 3) { throw "WP22A_PROVIDER_OIDC_COMPACT_INVALID" }
    $header = ConvertFrom-JwtJsonPart -Value $parts[0]
    $payload = ConvertFrom-JwtJsonPart -Value $parts[1]
    if ([string]$header.alg -cne "RS256") { throw "WP22A_PROVIDER_OIDC_ALG_FORBIDDEN" }
    if ([string]::IsNullOrWhiteSpace([string]$header.kid)) { throw "WP22A_PROVIDER_OIDC_KID_MISSING" }

    $metadata = Invoke-RestMethod -Method Get -Uri $oidcConfigurationUri -UseBasicParsing
    if ([string]$metadata.issuer -cne $expectedIssuer) { throw "WP22A_PROVIDER_OIDC_METADATA_ISSUER_MISMATCH" }
    $jwksUri = [string]$metadata.jwks_uri
    if ([string]::IsNullOrWhiteSpace($jwksUri) -or -not $jwksUri.StartsWith("https://", [System.StringComparison]::Ordinal)) {
        throw "WP22A_PROVIDER_OIDC_JWKS_URI_INVALID"
    }
    $jwks = Invoke-RestMethod -Method Get -Uri $jwksUri -UseBasicParsing
    $keys = @($jwks.keys | Where-Object { [string]$_.kid -ceq [string]$header.kid })
    if ($keys.Count -ne 1) { throw "WP22A_PROVIDER_OIDC_JWK_NOT_UNIQUE" }
    $key = $keys[0]
    if ([string]$key.kty -cne "RSA") { throw "WP22A_PROVIDER_OIDC_JWK_TYPE_INVALID" }

    $rsaParameters = [System.Security.Cryptography.RSAParameters]::new()
    $rsaParameters.Modulus = ConvertFrom-Base64Url -Value ([string]$key.n)
    $rsaParameters.Exponent = ConvertFrom-Base64Url -Value ([string]$key.e)
    $rsa = [System.Security.Cryptography.RSA]::Create()
    try {
        $rsa.ImportParameters($rsaParameters)
        $signedBytes = [System.Text.Encoding]::ASCII.GetBytes($parts[0] + "." + $parts[1])
        $signature = ConvertFrom-Base64Url -Value $parts[2]
        $validSignature = $rsa.VerifyData(
            $signedBytes,
            $signature,
            [System.Security.Cryptography.HashAlgorithmName]::SHA256,
            [System.Security.Cryptography.RSASignaturePadding]::Pkcs1
        )
    }
    finally { $rsa.Dispose() }
    if (-not $validSignature) { throw "WP22A_PROVIDER_OIDC_SIGNATURE_INVALID" }

    Test-ExactStringClaim -Payload $payload -Name "iss" -Expected $expectedIssuer -Reason "WP22A_PROVIDER_OIDC_ISSUER_MISMATCH"
    $audiences = @($payload.aud | ForEach-Object { [string]$_ })
    if ($audiences.Count -ne 1 -or $audiences[0] -cne $expectedAudience) { throw "WP22A_PROVIDER_OIDC_AUDIENCE_MISMATCH" }
    Test-ExactStringClaim -Payload $payload -Name "repository" -Expected $expectedRepository -Reason "WP22A_PROVIDER_OIDC_REPOSITORY_MISMATCH"
    Test-ExactStringClaim -Payload $payload -Name "repository_id" -Expected $expectedRepositoryId -Reason "WP22A_PROVIDER_OIDC_REPOSITORY_ID_MISMATCH"
    Test-ExactStringClaim -Payload $payload -Name "actor_id" -Expected $expectedOwnerActorId -Reason "WP22A_PROVIDER_OIDC_OWNER_ACTOR_MISMATCH"
    Test-ExactStringClaim -Payload $payload -Name "ref" -Expected "refs/heads/main" -Reason "WP22A_PROVIDER_OIDC_REF_MISMATCH"
    Test-ExactStringClaim -Payload $payload -Name "event_name" -Expected "workflow_dispatch" -Reason "WP22A_PROVIDER_OIDC_EVENT_MISMATCH"
    Test-ExactStringClaim -Payload $payload -Name "workflow_ref" -Expected $expectedWorkflowRef -Reason "WP22A_PROVIDER_OIDC_WORKFLOW_REF_MISMATCH"
    Test-ExactStringClaim -Payload $payload -Name "workflow_sha" -Expected $ImplementationSha -Reason "WP22A_PROVIDER_OIDC_WORKFLOW_SHA_MISMATCH"
    Test-ExactStringClaim -Payload $payload -Name "runner_environment" -Expected "self-hosted" -Reason "WP22A_PROVIDER_OIDC_RUNNER_ENVIRONMENT_MISMATCH"
    Test-ExactStringClaim -Payload $payload -Name "run_id" -Expected $RunId -Reason "WP22A_PROVIDER_OIDC_RUN_ID_MISMATCH"
    Test-OidcTimeClaims -Payload $payload

    $jti = [string]$payload.jti
    if ([string]::IsNullOrWhiteSpace($jti) -or $jti.Length -gt 512) { throw "WP22A_PROVIDER_OIDC_JTI_INVALID" }
    return [ordered]@{
        jti = $jti
        run_id = [string]$payload.run_id
        workflow_sha = [string]$payload.workflow_sha
    }
}

function Get-ControllerConfig {
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) { throw "WP22A_PROVIDER_CONTROLLER_CONFIG_MISSING" }
    try { $config = Get-Content -LiteralPath $configPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop }
    catch { throw "WP22A_PROVIDER_CONTROLLER_CONFIG_INVALID" }
    $sha = ([string]$config.implementation_sha).Trim().ToLowerInvariant()
    if ($sha -notmatch '^[0-9a-f]{40}$') { throw "WP22A_PROVIDER_CONTROLLER_SHA_INVALID" }
    if ([string]$config.repository -cne $expectedRepository) { throw "WP22A_PROVIDER_CONTROLLER_REPOSITORY_MISMATCH" }
    if ([string]$config.repository_id -cne $expectedRepositoryId) { throw "WP22A_PROVIDER_CONTROLLER_REPOSITORY_ID_MISMATCH" }
    return [ordered]@{ implementation_sha = $sha }
}

function Test-ReplayAndConsume {
    param([Parameter(Mandatory = $true)][string]$Jti)
    New-Item -ItemType Directory -Path $replayRoot -Force | Out-Null
    $cutoff = [DateTime]::UtcNow.AddHours(-1 * $replayRetentionHours)
    Get-ChildItem -LiteralPath $replayRoot -Filter "*.used" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTimeUtc -lt $cutoff } |
        Remove-Item -Force -ErrorAction SilentlyContinue

    $replayPath = Join-Path $replayRoot ((Get-Sha256Hex -Value $Jti) + ".used")
    if (Test-Path -LiteralPath $replayPath -PathType Leaf) { throw "WP22A_PROVIDER_OIDC_REPLAY_REJECTED" }
    [System.IO.File]::WriteAllText($replayPath, [DateTimeOffset]::UtcNow.ToString("o"), [System.Text.UTF8Encoding]::new($false))
}

function Write-SanitizedResult {
    param(
        [Parameter(Mandatory = $true)][string]$RequestId,
        [Parameter(Mandatory = $true)][string]$ImplementationSha,
        [Parameter(Mandatory = $true)][string]$RunId,
        [Parameter(Mandatory = $true)][bool]$Accepted,
        [Parameter(Mandatory = $true)][string]$Reason
    )
    $result = [ordered]@{
        schema_version = 1
        request_id = $RequestId
        implementation_sha = $ImplementationSha
        run_id = $RunId
        accepted = $Accepted
        mutation_performed = $false
        reason = $Reason
    }
    $resultPath = Join-Path $resultRoot ($RequestId + ".json")
    $tempPath = Join-Path $resultRoot ($RequestId + ".tmp")
    [System.IO.File]::WriteAllText($tempPath, ($result | ConvertTo-Json -Compress), [System.Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $tempPath -Destination $resultPath -Force
}

function Invoke-RequestFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ImplementationSha
    )
    $requestId = ""
    $requestSha = ""
    $runId = ""
    try {
        $request = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $requestId = [string]$request.request_id
        $requestSha = ([string]$request.implementation_sha).Trim().ToLowerInvariant()
        $runId = [string]$request.run_id
        if ($requestId -notmatch '^[0-9a-f]{32}$') { throw "WP22A_PROVIDER_REQUEST_ID_INVALID" }
        if ([System.IO.Path]::GetFileName($Path) -cne ($requestId + ".json")) { throw "WP22A_PROVIDER_REQUEST_FILENAME_MISMATCH" }
        if ($requestSha -cne $ImplementationSha) { throw "WP22A_PROVIDER_REQUEST_SHA_MISMATCH" }
        if ($runId -notmatch '^[0-9]+$') { throw "WP22A_PROVIDER_REQUEST_RUN_ID_INVALID" }
        $jwt = [string]$request.oidc_token
        if ([string]::IsNullOrWhiteSpace($jwt) -or $jwt.Length -gt 16384) { throw "WP22A_PROVIDER_REQUEST_OIDC_INVALID" }

        $validated = Test-OidcSignatureAndClaims -Jwt $jwt -ImplementationSha $ImplementationSha -RunId $runId
        $jwt = $null
        Test-ReplayAndConsume -Jti ([string]$validated.jti)
        Write-SanitizedResult -RequestId $requestId -ImplementationSha $ImplementationSha -RunId $runId -Accepted $true -Reason "WP22A_PROVIDER_BOUNDARY_READY_NO_MUTATION"
    }
    catch {
        $message = [string]$_.Exception.Message
        $reason = if ($message.StartsWith("WP22A_", [System.StringComparison]::Ordinal)) { $message } else { "WP22A_PROVIDER_OIDC_VALIDATION_FAILED" }
        if ($requestId -match '^[0-9a-f]{32}$' -and $requestSha -match '^[0-9a-f]{40}$' -and $runId -match '^[0-9]+$') {
            Write-SanitizedResult -RequestId $requestId -ImplementationSha $requestSha -RunId $runId -Accepted $false -Reason $reason
        }
    }
    finally {
        Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    }
}

if ($ValidateOnly) {
    $validation = [ordered]@{
        gate = "WP22A_PROVIDER_CONTROLLER_SOURCE_VALIDATION"
        passed = $true
        mutation_performed = $false
        repository = $expectedRepository
        repository_id = $expectedRepositoryId
        audience = $expectedAudience
        issuer = $expectedIssuer
        workflow_ref = $expectedWorkflowRef
        reason = "WP22A_PROVIDER_CONTROLLER_SOURCE_READY_NO_MUTATION"
    }
    if ($AsJson) { $validation | ConvertTo-Json -Compress } else { $validation }
    exit 0
}

$currentPath = [System.IO.Path]::GetFullPath($PSCommandPath)
$expectedPrefix = [System.IO.Path]::GetFullPath($protectedRoot + "\")
if (-not $currentPath.StartsWith($expectedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "WP22A_PROVIDER_CONTROLLER_PROTECTED_PATH_REQUIRED"
}
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
if ($identity.User.Value -ne "S-1-5-18") { throw "WP22A_PROVIDER_CONTROLLER_SYSTEM_REQUIRED" }
$config = Get-ControllerConfig
if (-not (Test-Path -LiteralPath $requestRoot -PathType Container)) { throw "WP22A_PROVIDER_REQUEST_ROOT_MISSING" }
if (-not (Test-Path -LiteralPath $resultRoot -PathType Container)) { throw "WP22A_PROVIDER_RESULT_ROOT_MISSING" }

Get-ChildItem -LiteralPath $requestRoot -Filter "*.json" -File -ErrorAction Stop |
    Sort-Object Name |
    ForEach-Object { Invoke-RequestFile -Path $_.FullName -ImplementationSha ([string]$config.implementation_sha) }

$result = [ordered]@{
    gate = "WP22A_PROVIDER_CONTROLLER_QUEUE_PASS"
    passed = $true
    mutation_performed = $false
    reason = "WP22A_PROVIDER_QUEUE_PROCESSED_NO_MUTATION"
}
if ($AsJson) { $result | ConvertTo-Json -Compress } else { $result }