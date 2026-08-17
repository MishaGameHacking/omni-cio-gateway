[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedImplementationSha,
    [switch]$Install,
    [switch]$Cleanup,
    [switch]$ValidateOnly,
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$modeCount = @(@($Install, $Cleanup, $ValidateOnly) | Where-Object { $_ }).Count
if ($modeCount -ne 1) { throw "Choose exactly one of -Install, -Cleanup, or -ValidateOnly." }
if ($env:OS -ne "Windows_NT") { throw "WP22A_PROVIDER_CONTROLLER_WINDOWS_REQUIRED" }

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$sourceController = Join-Path $repoRoot "infrastructure\windows\run_wp22a_provider_controller.ps1"
$activationWorkflow = Join-Path $repoRoot ".github\workflows\v10-wp22a-provider-activation.yml"
$protectedRoot = "C:\ProgramData\OmniCIO\private\wp22a-provider-controller"
$installedController = Join-Path $protectedRoot "run_wp22a_provider_controller.ps1"
$configPath = Join-Path $protectedRoot "controller.json"
$replayRoot = Join-Path $protectedRoot "replay"
$requestRoot = "C:\ProgramData\OmniCIO\runtime\wp22a-provider-requests"
$resultRoot = "C:\ProgramData\OmniCIO\runtime\wp22a-provider-results"
$taskName = "OmniCIO.V10.WP22A.ProviderController"
$expectedRepository = "MishaGameHacking/omni-cio-gateway"
$expectedRepositoryId = "1312247309"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-ReviewedHead {
    param([switch]$RequireMain)
    $expected = $ExpectedImplementationSha.Trim().ToLowerInvariant()
    if ($expected -notmatch '^[0-9a-f]{40}$') { throw "WP22A_PROVIDER_EXPECTED_SHA_INVALID" }
    $head = @(& git -C $repoRoot rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1) { throw "WP22A_PROVIDER_GIT_HEAD_UNAVAILABLE" }
    $actual = ([string]$head[0]).Trim().ToLowerInvariant()
    if ($actual -ne $expected) { throw "WP22A_PROVIDER_GIT_HEAD_MISMATCH" }
    if ($RequireMain) {
        $branch = @(& git -C $repoRoot branch --show-current 2>$null)
        if ($LASTEXITCODE -ne 0 -or $branch.Count -ne 1 -or ([string]$branch[0]).Trim() -cne "main") {
            throw "WP22A_PROVIDER_MAIN_BRANCH_REQUIRED"
        }
        $dirty = @(& git -C $repoRoot status --porcelain 2>$null)
        if ($LASTEXITCODE -ne 0) { throw "WP22A_PROVIDER_GIT_STATUS_UNAVAILABLE" }
        if ($dirty.Count -ne 0) { throw "WP22A_PROVIDER_WORKTREE_NOT_CLEAN" }
    }
    return $actual
}

function Resolve-AccountSid {
    param([Parameter(Mandatory = $true)][string]$AccountName)
    $normalized = $AccountName.Trim().ToUpperInvariant()
    if ($normalized -in @("LOCALSYSTEM", ".\LOCALSYSTEM", "NT AUTHORITY\SYSTEM")) { return "S-1-5-18" }
    if ($normalized -eq "NT AUTHORITY\NETWORKSERVICE") { return "S-1-5-20" }
    if ($normalized -eq "NT AUTHORITY\LOCALSERVICE") { return "S-1-5-19" }
    try {
        return [System.Security.Principal.NTAccount]::new($AccountName).Translate(
            [System.Security.Principal.SecurityIdentifier]
        ).Value
    }
    catch { throw "WP22A_PROVIDER_RUNNER_SID_UNAVAILABLE" }
}

function Get-RunnerSidValue {
    $services = @(
        Get-CimInstance Win32_Service -ErrorAction Stop |
            Where-Object { $_.Name -like "actions.runner.*" }
    )
    if ($services.Count -ne 1) { throw "WP22A_PROVIDER_RUNNER_SERVICE_AMBIGUOUS" }
    $startName = ([string]$services[0].StartName).Trim()
    if ($startName.ToUpperInvariant() -in @("LOCALSYSTEM", ".\LOCALSYSTEM", "NT AUTHORITY\SYSTEM")) {
        throw "WP22A_PROVIDER_RUNNER_LOCAL_SYSTEM_FORBIDDEN"
    }
    return Resolve-AccountSid -AccountName $startName
}

function New-AclRule {
    param(
        [Parameter(Mandatory = $true)][string]$SidValue,
        [Parameter(Mandatory = $true)][System.Security.AccessControl.FileSystemRights]$Rights
    )
    $sid = [System.Security.Principal.SecurityIdentifier]::new($SidValue)
    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    return [System.Security.AccessControl.FileSystemAccessRule]::new(
        $sid,
        $Rights,
        $inherit,
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
}

function Set-DirectoryAcl {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][hashtable]$AdditionalGrants
    )
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-AclRule -SidValue "S-1-5-18" -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl)))
    $acl.AddAccessRule((New-AclRule -SidValue "S-1-5-32-544" -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl)))
    foreach ($entry in $AdditionalGrants.GetEnumerator()) {
        $acl.AddAccessRule((New-AclRule -SidValue ([string]$entry.Key) -Rights ([System.Security.AccessControl.FileSystemRights]$entry.Value)))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl -ErrorAction Stop
}

function Test-PathAclExcludesSid {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$SidValue
    )
    $acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
    foreach ($rule in $acl.Access) {
        try { $sid = $rule.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value }
        catch { continue }
        if ($sid -eq $SidValue -and $rule.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow) {
            return $false
        }
    }
    return $true
}

function Test-SourceBoundary {
    if (-not (Test-Path -LiteralPath $sourceController -PathType Leaf)) { throw "WP22A_PROVIDER_CONTROLLER_SOURCE_MISSING" }
    if (-not (Test-Path -LiteralPath $activationWorkflow -PathType Leaf)) { throw "WP22A_PROVIDER_ACTIVATION_WORKFLOW_MISSING" }
    $controller = Get-Content -LiteralPath $sourceController -Raw -ErrorAction Stop
    $workflow = Get-Content -LiteralPath $activationWorkflow -Raw -ErrorAction Stop

    foreach ($marker in @(
        "omni-cio-wp22a-provider-controller",
        "https://token.actions.githubusercontent.com",
        "1312247309",
        "actor_id",
        "WP22A_PROVIDER_OIDC_OWNER_ACTOR_MISMATCH",
        "workflow_sha",
        "workflow_ref",
        "resultRetentionHours = 24",
        "Remove-StaleResultFiles",
        "WP22A_PROVIDER_BOUNDARY_READY_NO_MUTATION",
        "mutation_performed = `$false"
    )) {
        if ($controller.IndexOf($marker, [System.StringComparison]::Ordinal) -lt 0) {
            throw "WP22A_PROVIDER_CONTROLLER_CONTRACT_INCOMPLETE"
        }
    }
    foreach ($forbidden in @("api.cloudflare.com", "tofu apply", "terraform apply", "cloudflared tunnel run")) {
        if ($controller.IndexOf($forbidden, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            throw "WP22A_PROVIDER_PHASE_B1_MUTATION_SURFACE_FORBIDDEN"
        }
    }
    foreach ($marker in @(
        "workflow_dispatch:",
        "id-token: write",
        "refs/heads/main",
        "github.actor_id",
        "github.triggering_actor",
        "WP22A_PROVIDER_OWNER_ACTOR_REQUIRED",
        "WP22A_PROVIDER_RERUN_BY_DIFFERENT_ACTOR_FORBIDDEN",
        "ACTIONS_ID_TOKEN_REQUEST_URL"
    )) {
        if ($workflow.IndexOf($marker, [System.StringComparison]::Ordinal) -lt 0) {
            throw "WP22A_PROVIDER_WORKFLOW_CONTRACT_INCOMPLETE"
        }
    }
    if ($workflow.IndexOf("secrets.", [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
        throw "WP22A_PROVIDER_WORKFLOW_SECRET_REFERENCE_FORBIDDEN"
    }
}

function Remove-ControllerBoundary {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $protectedRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $requestRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $resultRoot -Recurse -Force -ErrorAction SilentlyContinue
}

$reviewedHead = Get-ReviewedHead -RequireMain:($Install -or $Cleanup)
Test-SourceBoundary

if ($ValidateOnly) {
    $result = [ordered]@{
        gate = "WP22A_PROVIDER_CONTROLLER_INSTALLER_SOURCE_VALIDATION"
        passed = $true
        implementation_sha = $reviewedHead
        mutation_performed = $false
        reason = "WP22A_PROVIDER_CONTROLLER_INSTALLER_SOURCE_READY_NO_MUTATION"
    }
    if ($AsJson) { $result | ConvertTo-Json -Compress } else { $result }
    exit 0
}

if (-not (Test-Administrator)) { throw "WP22A_PROVIDER_ADMINISTRATOR_REQUIRED" }

if ($Cleanup) {
    if ($PSCmdlet.ShouldProcess($protectedRoot, "Remove WP22A Phase-B1 provider controller boundary")) {
        Remove-ControllerBoundary
    }
    $result = [ordered]@{
        gate = "WP22A_PROVIDER_CONTROLLER_CLEANUP"
        passed = $true
        implementation_sha = $reviewedHead
        mutation_performed = $false
        reason = "WP22A_PROVIDER_CONTROLLER_BOUNDARY_REMOVED"
    }
    if ($AsJson) { $result | ConvertTo-Json -Compress } else { $result }
    exit 0
}

$runnerSid = Get-RunnerSidValue
if ($PSCmdlet.ShouldProcess($protectedRoot, "Install WP22A Phase-B1 provider request controller")) {
    New-Item -ItemType Directory -Path $protectedRoot, $replayRoot, $requestRoot, $resultRoot -Force | Out-Null
    Set-DirectoryAcl -Path $protectedRoot -AdditionalGrants @{}
    Set-DirectoryAcl -Path $replayRoot -AdditionalGrants @{}
    Set-DirectoryAcl -Path $requestRoot -AdditionalGrants @{
        $runnerSid = [System.Security.AccessControl.FileSystemRights]::Modify
    }
    Set-DirectoryAcl -Path $resultRoot -AdditionalGrants @{
        $runnerSid = [System.Security.AccessControl.FileSystemRights]::ReadAndExecute
    }

    Copy-Item -LiteralPath $sourceController -Destination $installedController -Force
    $config = [ordered]@{
        schema_version = 1
        implementation_sha = $reviewedHead
        repository = $expectedRepository
        repository_id = $expectedRepositoryId
    }
    [System.IO.File]::WriteAllText($configPath, ($config | ConvertTo-Json -Compress), [System.Text.UTF8Encoding]::new($false))

    if (-not (Test-PathAclExcludesSid -Path $protectedRoot -SidValue $runnerSid)) {
        throw "WP22A_PROVIDER_RUNNER_PROTECTED_ROOT_ACCESS_FORBIDDEN"
    }

    $actionArguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$installedController`" -ProcessQueue -AsJson"
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $actionArguments -WorkingDirectory $protectedRoot
    $bootTrigger = New-ScheduledTaskTrigger -AtStartup
    $pollTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 3650)
    $principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($bootTrigger, $pollTrigger) -Principal $principal -Settings $settings -Description "Omni-CIO V10 WP22A protected OIDC provider request controller; Phase-B1 no provider mutation" -Force | Out-Null
    Start-ScheduledTask -TaskName $taskName
}

$task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
$actionText = [string](@($task.Actions | Select-Object -First 1).Arguments)
$ready = [string]$task.Principal.UserId -eq "SYSTEM" -or [string]$task.Principal.UserId -eq "NT AUTHORITY\SYSTEM"
$ready = $ready -and $actionText.IndexOf($installedController, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
$ready = $ready -and (Test-Path -LiteralPath $installedController -PathType Leaf)
$ready = $ready -and (Test-Path -LiteralPath $configPath -PathType Leaf)
$ready = $ready -and (Test-PathAclExcludesSid -Path $protectedRoot -SidValue $runnerSid)
if (-not $ready) { throw "WP22A_PROVIDER_CONTROLLER_INSTALL_VERIFY_FAILED" }

$result = [ordered]@{
    gate = "WP22A_PROVIDER_CONTROLLER_INSTALL"
    passed = $true
    implementation_sha = $reviewedHead
    mutation_performed = $false
    reason = "WP22A_PROVIDER_CONTROLLER_BOUNDARY_INSTALLED_NO_MUTATION"
}
if ($AsJson) { $result | ConvertTo-Json -Compress } else { $result }