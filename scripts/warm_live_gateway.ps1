[CmdletBinding()]
param(
    [int]$DeadlineSeconds = 150,
    [int]$RequestTimeoutSeconds = 75,
    [int]$RetryDelaySeconds = 5
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Stop-WithCode {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message,
        [Parameter(Mandatory = $true)]
        [int]$Code
    )

    [Console]::Error.WriteLine($Message)
    exit $Code
}

if ($DeadlineSeconds -lt 1 -or $RequestTimeoutSeconds -lt 1 -or $RetryDelaySeconds -lt 1) {
    Stop-WithCode -Message "LIVE_WAKE_CONFIGURATION_INVALID" -Code 40
}

$rawBaseUrl = [string]$env:OMNI_LIVE_BASE_URL
if ([string]::IsNullOrWhiteSpace($rawBaseUrl)) {
    Stop-WithCode -Message "LIVE_WAKE_BASE_URL_REQUIRED" -Code 40
}

try {
    $baseUri = [Uri]$rawBaseUrl
}
catch {
    Stop-WithCode -Message "LIVE_WAKE_BASE_URL_INVALID" -Code 40
}

if ($baseUri.Scheme -ne "https" -or $baseUri.Host -ne "omni-cio-gateway.onrender.com") {
    Stop-WithCode -Message "LIVE_WAKE_ENDPOINT_REJECTED" -Code 40
}

$dnsState = "UNKNOWN"
try {
    [System.Net.Dns]::GetHostAddresses($baseUri.DnsSafeHost) | Out-Null
    $dnsState = "OK"
}
catch {
    $dnsState = "FAIL"
}

$tcpState = "NOT_TESTED"
if ($dnsState -eq "OK") {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $connect = $client.BeginConnect($baseUri.DnsSafeHost, 443, $null, $null)
        if ($connect.AsyncWaitHandle.WaitOne(5000, $false)) {
            $client.EndConnect($connect)
            $tcpState = "OK"
        }
        else {
            $tcpState = "TIMEOUT"
        }
    }
    catch {
        $tcpState = "FAIL"
    }
    finally {
        $client.Close()
    }
}

$healthUrl = [Uri]::new($baseUri, "/health").AbsoluteUri
$deadline = [DateTimeOffset]::UtcNow.AddSeconds($DeadlineSeconds)
$attempt = 0
$lastHttpState = "NOT_ATTEMPTED"

while ([DateTimeOffset]::UtcNow -lt $deadline) {
    $attempt += 1
    try {
        $response = Invoke-WebRequest `
            -Uri $healthUrl `
            -Method Get `
            -UseBasicParsing `
            -TimeoutSec $RequestTimeoutSeconds
        $contentType = [string]$response.Headers["Content-Type"]
        if ($response.StatusCode -ne 200) {
            $lastHttpState = "HTTP_$($response.StatusCode)"
        }
        elseif ($contentType -notmatch "^application/json") {
            $lastHttpState = "NON_JSON"
        }
        else {
            try {
                $payload = $response.Content | ConvertFrom-Json
            }
            catch {
                $lastHttpState = "INVALID_JSON"
                $payload = $null
            }
            if ($null -ne $payload -and $payload.status -eq "ok") {
                Write-Host "Protected V9 gateway wake probe ready after $attempt attempt(s)."
                exit 0
            }
            if ($null -ne $payload -and $payload.status -ne "ok") {
                $lastHttpState = "HEALTH_NOT_OK"
            }
        }
    }
    catch [System.Net.WebException] {
        $webException = $_.Exception
        if ($null -ne $webException.Response) {
            try {
                $statusCode = [int]$webException.Response.StatusCode
                $lastHttpState = "HTTP_$statusCode"
            }
            catch {
                $lastHttpState = "WEB_RESPONSE_ERROR"
            }
        }
        else {
            $lastHttpState = "WEB_$($webException.Status)"
        }
    }
    catch {
        $lastHttpState = "REQUEST_FAILED"
    }
    Start-Sleep -Seconds $RetryDelaySeconds
}

Stop-WithCode `
    -Message "LIVE_WAKE_FAILED dns=$dnsState tcp443=$tcpState http=$lastHttpState attempts=$attempt" `
    -Code 41
