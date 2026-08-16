[CmdletBinding()]
param(
    [int]$DeadlineSeconds = 150,
    [int]$RequestTimeoutSeconds = 75,
    [int]$RetryDelaySeconds = 5
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if ($DeadlineSeconds -lt 1 -or $RequestTimeoutSeconds -lt 1 -or $RetryDelaySeconds -lt 1) {
    Write-Error "Live gateway wake probe timing values must be positive integers."
    exit 40
}

$rawBaseUrl = [string]$env:OMNI_LIVE_BASE_URL
if ([string]::IsNullOrWhiteSpace($rawBaseUrl)) {
    Write-Error "OMNI_LIVE_BASE_URL is required."
    exit 40
}

try {
    $baseUri = [Uri]$rawBaseUrl
}
catch {
    Write-Error "OMNI_LIVE_BASE_URL is invalid."
    exit 40
}

if ($baseUri.Scheme -ne "https" -or $baseUri.Host -ne "omni-cio-gateway.onrender.com") {
    Write-Error "Live gateway wake probe rejected an unapproved endpoint."
    exit 40
}

$healthUrl = [Uri]::new($baseUri, "/health").AbsoluteUri
$deadline = [DateTimeOffset]::UtcNow.AddSeconds($DeadlineSeconds)
$attempt = 0

while ([DateTimeOffset]::UtcNow -lt $deadline) {
    $attempt += 1
    try {
        $response = Invoke-WebRequest `
            -Uri $healthUrl `
            -Method Get `
            -UseBasicParsing `
            -TimeoutSec $RequestTimeoutSeconds
        $contentType = [string]$response.Headers["Content-Type"]
        if ($response.StatusCode -eq 200 -and $contentType -match "^application/json") {
            $payload = $response.Content | ConvertFrom-Json
            if ($payload.status -eq "ok") {
                Write-Host "Protected V9 gateway wake probe ready after $attempt attempt(s)."
                exit 0
            }
        }
    }
    catch {
        # The strict Python authority validator owns final evidence. Do not emit
        # provider/network exception details from this bounded readiness stage.
    }
    Start-Sleep -Seconds $RetryDelaySeconds
}

Write-Error "Protected V9 gateway did not reach JSON health within bounded cold-start window."
exit 41
