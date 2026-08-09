[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Verify,
    [switch]$RunRehearsals,
    [switch]$ArmReboot,
    [switch]$RestartComputer,
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

if ($Apply -and $Verify) {
    throw "Choose -Apply or -Verify, not both."
}
if (($RunRehearsals -or $ArmReboot -or $RestartComputer) -and -not $Apply) {
    throw "Rehearsal/reboot switches are valid only with -Apply."
}
if ($RestartComputer -and (-not $ArmReboot -or -not $RunRehearsals)) {
    throw "-RestartComputer requires -Apply -RunRehearsals -ArmReboot."
}
if ($Apply -and $env:OS -ne "Windows_NT") {
    throw "WP9 supervision mutation requires Windows."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$contractSource = Join-Path $repoRoot "docs\architecture\V10_WP9_SUPERVISION_CONTRACT.json"
$wp7Verifier = Join-Path $repoRoot "infrastructure\windows\bootstrap-v10.ps1"
$wp8Verifier = Join-Path $repoRoot "infrastructure\windows\provision_wp8_secret_store.ps1"
$healthSource = Join-Path $repoRoot "infrastructure\windows\wp9_health_supervisor.ps1"
$guardSource = Join-Path $repoRoot "infrastructure\windows\wp9_component_guard.ps1"
$workerSource = Join-Path $repoRoot "infrastructure\windows\wp9_rehearsal_worker.ps1"

$contract = Get-Content -LiteralPath $contractSource -Raw -ErrorAction Stop |
    ConvertFrom-Json -ErrorAction Stop
if ([string]$contract.schema_version -ne "1" -or [string]$contract.work_package -ne "WP9") {
    throw "Unsupported WP9 supervision contract."
}

$wp9Root = [string]$contract.paths.wp9_root
$deployedRoot = [string]$contract.paths.deployed_root
$evidenceRoot = [string]$contract.paths.evidence_root
$statusPath = [string]$contract.paths.status_file
$provisionStatePath = [string]$contract.paths.provision_state
$restartEvidencePath = [string]$contract.paths.restart_rehearsal
$dependencyEvidencePath = [string]$contract.paths.dependency_rehearsal
$rebootEvidencePath = [string]$contract.paths.reboot_rehearsal
$taskPath = [string]$contract.task_folder
$ownershipMarker = "OMNI-CIO-V10-WP9-OWNED-v1"
$ownershipMarkerName = ".omni-cio-wp9-owned"
$taskDescription = "OMNI-CIO-V10-WP9-OWNED-v1"
$rehearsalDescription = "OMNI-CIO-V10-WP9-REHEARSAL-v1"
$localServiceSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-19")
$systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
$adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
$powershellExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$deployedContract = Join-Path $deployedRoot "V10_WP9_SUPERVISION_CONTRACT.json"
$deployedHealth = Join-Path $deployedRoot "wp9_health_supervisor.ps1"
$deployedGuard = Join-Path $deployedRoot "wp9_component_guard.ps1"
$deployedWorker = Join-Path $deployedRoot "wp9_rehearsal_worker.ps1"
$temporaryEvidenceRoot = Join-Path $evidenceRoot "temporary-rehearsal"

function Test-Administrator {
    if ($env:OS -ne "Windows_NT") { return $false }
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-RunnerServiceSid {
    $services = @(
        Get-CimInstance Win32_Service -ErrorAction Stop |
            Where-Object {
                $_.Name -match '^actions\.runner\.' -and
                -not [string]::IsNullOrWhiteSpace([string]$_.PathName) -and
                ([string]$_.PathName).IndexOf(
                    "C:\actions-runner",
                    [System.StringComparison]::OrdinalIgnoreCase
                ) -ge 0
            }
    )
    if ($services.Count -ne 1) {
        throw "WP9_RUNNER_SERVICE_IDENTITY_UNAVAILABLE"
    }
    try {
        $account = [System.Security.Principal.NTAccount]::new([string]$services[0].StartName)
        return $account.Translate([System.Security.Principal.SecurityIdentifier])
    }
    catch {
        throw "WP9_RUNNER_SERVICE_IDENTITY_UNAVAILABLE"
    }
}

function Invoke-JsonPowerShell {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    $raw = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
        -File $FilePath @Arguments 2>$null | Out-String
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    try {
        return $raw.Trim() | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        return $null
    }
}

function Get-InheritedBoundaryState {
    if ($env:OS -ne "Windows_NT") {
        return [ordered]@{ wp7 = $false; wp8 = $false }
    }
    $wp7 = Invoke-JsonPowerShell -FilePath $wp7Verifier -Arguments @("-Verify", "-AsJson")
    $wp8 = Invoke-JsonPowerShell -FilePath $wp8Verifier -Arguments @("-Verify", "-AsJson")
    return [ordered]@{
        wp7 = ($null -ne $wp7 -and [string]$wp7.status -eq "PASS")
        wp8 = ($null -ne $wp8 -and [string]$wp8.status -eq "PASS")
    }
}

function New-AllowRule {
    param(
        [System.Security.Principal.IdentityReference]$Identity,
        [System.Security.AccessControl.FileSystemRights]$Rights,
        [System.Security.AccessControl.InheritanceFlags]$Inheritance
    )
    return [System.Security.AccessControl.FileSystemAccessRule]::new(
        $Identity,
        $Rights,
        $Inheritance,
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
}

function Set-Wp9DirectoryAcl {
    param(
        [string]$Path,
        [ValidateSet("DEPLOYED", "EVIDENCE")]
        [string]$Class,
        [System.Security.Principal.SecurityIdentifier]$RunnerSid
    )

    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor `
        [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-AllowRule -Identity $systemSid -Rights FullControl -Inheritance $inherit))
    $acl.AddAccessRule((New-AllowRule -Identity $adminsSid -Rights FullControl -Inheritance $inherit))
    if ($Class -eq "DEPLOYED") {
        $acl.AddAccessRule((New-AllowRule -Identity $localServiceSid -Rights ReadAndExecute -Inheritance $inherit))
        $acl.AddAccessRule((New-AllowRule -Identity $RunnerSid -Rights ReadAndExecute -Inheritance $inherit))
    }
    else {
        $acl.AddAccessRule((New-AllowRule -Identity $localServiceSid -Rights Modify -Inheritance $inherit))
        $acl.AddAccessRule((New-AllowRule -Identity $RunnerSid -Rights Read -Inheritance $inherit))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Ensure-Wp9Layout {
    param([System.Security.Principal.SecurityIdentifier]$RunnerSid)

    $changes = 0
    if (Test-Path -LiteralPath $wp9Root) {
        if (-not (Test-Path -LiteralPath $wp9Root -PathType Container)) {
            throw "WP9_ROOT_NOT_DIRECTORY"
        }
        $marker = Join-Path $wp9Root $ownershipMarkerName
        if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
            throw "WP9_REFUSES_UNMARKED_EXISTING_ROOT"
        }
        if ((Get-Content -LiteralPath $marker -Raw -ErrorAction Stop).Trim() -ne $ownershipMarker) {
            throw "WP9_ROOT_MARKER_MISMATCH"
        }
    }
    else {
        New-Item -ItemType Directory -Path $wp9Root -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $wp9Root $ownershipMarkerName) `
            -Value $ownershipMarker -Encoding ASCII -NoNewline
        $changes += 1
    }

    foreach ($path in @($deployedRoot, $evidenceRoot, $temporaryEvidenceRoot)) {
        if (-not (Test-Path -LiteralPath $path -PathType Container)) {
            New-Item -ItemType Directory -Path $path -Force | Out-Null
            $changes += 1
        }
    }

    Set-Wp9DirectoryAcl -Path $wp9Root -Class DEPLOYED -RunnerSid $RunnerSid
    Set-Wp9DirectoryAcl -Path $deployedRoot -Class DEPLOYED -RunnerSid $RunnerSid
    Set-Wp9DirectoryAcl -Path $evidenceRoot -Class EVIDENCE -RunnerSid $RunnerSid
    Set-Wp9DirectoryAcl -Path $temporaryEvidenceRoot -Class EVIDENCE -RunnerSid $RunnerSid
    return $changes
}

function Ensure-DeployedFile {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "WP9_SOURCE_FILE_MISSING"
    }
    $sourceBytes = [System.IO.File]::ReadAllBytes($Source)
    if (Test-Path -LiteralPath $Destination -PathType Leaf) {
        $existingBytes = [System.IO.File]::ReadAllBytes($Destination)
        if ($sourceBytes.Length -eq $existingBytes.Length) {
            $same = $true
            for ($index = 0; $index -lt $sourceBytes.Length; $index += 1) {
                if ($sourceBytes[$index] -ne $existingBytes[$index]) {
                    $same = $false
                    break
                }
            }
            if ($same) { return $false }
        }
    }
    [System.IO.File]::WriteAllBytes($Destination, $sourceBytes)
    return $true
}

function Ensure-DeployedPayload {
    $changes = 0
    foreach ($pair in @(
        @($contractSource, $deployedContract),
        @($healthSource, $deployedHealth),
        @($guardSource, $deployedGuard),
        @($workerSource, $deployedWorker)
    )) {
        if (Ensure-DeployedFile -Source $pair[0] -Destination $pair[1]) {
            $changes += 1
        }
    }
    return $changes
}

function Ensure-TaskFolder {
    $service = New-Object -ComObject "Schedule.Service"
    $service.Connect()
    $root = $service.GetFolder("\")
    try {
        [void]$service.GetFolder("\OmniCIO")
    }
    catch {
        [void]$root.CreateFolder("OmniCIO")
    }
    $omni = $service.GetFolder("\OmniCIO")
    try {
        [void]$service.GetFolder("\OmniCIO\V10")
    }
    catch {
        [void]$omni.CreateFolder("V10")
    }
}

function Ensure-SchedulerObjectReadAccess {
    param(
        [object]$SchedulerObject,
        [System.Security.Principal.SecurityIdentifier]$RunnerSid
    )

    $daclSecurityInformation = 4
    $fileGenericRead = 0x00120089
    $sddl = [string]$SchedulerObject.GetSecurityDescriptor($daclSecurityInformation)
    if ([string]::IsNullOrWhiteSpace($sddl)) {
        throw "WP9_SCHEDULER_SECURITY_DESCRIPTOR_UNAVAILABLE"
    }
    $descriptor = [System.Security.AccessControl.RawSecurityDescriptor]::new($sddl)
    if ($null -eq $descriptor.DiscretionaryAcl) {
        throw "WP9_SCHEDULER_DACL_UNAVAILABLE"
    }

    foreach ($ace in @($descriptor.DiscretionaryAcl)) {
        if (
            $ace -is [System.Security.AccessControl.CommonAce] -and
            $ace.AceQualifier -eq [System.Security.AccessControl.AceQualifier]::AccessAllowed -and
            $null -ne $ace.SecurityIdentifier -and
            $ace.SecurityIdentifier.Value -eq $RunnerSid.Value -and
            (($ace.AccessMask -band $fileGenericRead) -eq $fileGenericRead)
        ) {
            return
        }
    }

    $readAce = [System.Security.AccessControl.CommonAce]::new(
        [System.Security.AccessControl.AceFlags]::None,
        [System.Security.AccessControl.AceQualifier]::AccessAllowed,
        $fileGenericRead,
        $RunnerSid,
        $false,
        $null
    )
    $descriptor.DiscretionaryAcl.InsertAce($descriptor.DiscretionaryAcl.Count, $readAce)
    $newSddl = $descriptor.GetSddlForm([System.Security.AccessControl.AccessControlSections]::Access)
    $SchedulerObject.SetSecurityDescriptor($newSddl, 0)
}

function Ensure-Wp9SchedulerReadBoundary {
    param([System.Security.Principal.SecurityIdentifier]$RunnerSid)

    $service = New-Object -ComObject "Schedule.Service"
    $service.Connect()
    $omniFolder = $service.GetFolder("\OmniCIO")
    $v10Folder = $service.GetFolder("\OmniCIO\V10")
    Ensure-SchedulerObjectReadAccess -SchedulerObject $omniFolder -RunnerSid $RunnerSid
    Ensure-SchedulerObjectReadAccess -SchedulerObject $v10Folder -RunnerSid $RunnerSid

    foreach ($taskName in @(
        [string]$contract.tasks.health_supervisor,
        [string]$contract.tasks.core_api,
        [string]$contract.tasks.web,
        [string]$contract.tasks.telegram,
        [string]$contract.tasks.watchtower,
        [string]$contract.tasks.ai_worker
    )) {
        $task = $v10Folder.GetTask($taskName)
        Ensure-SchedulerObjectReadAccess -SchedulerObject $task -RunnerSid $RunnerSid
    }
}

function Convert-PrincipalToSid {
    param([string]$UserId)
    try {
        if ($UserId -match '^S-1-') {
            return [System.Security.Principal.SecurityIdentifier]::new($UserId)
        }
        $account = [System.Security.Principal.NTAccount]::new($UserId)
        return $account.Translate([System.Security.Principal.SecurityIdentifier])
    }
    catch {
        return $null
    }
}

function Test-OwnedTaskDefinition {
    param(
        [string]$TaskName,
        [string]$ExpectedArguments,
        [bool]$ExpectedEnabled,
        [bool]$HealthTask
    )

    try {
        $task = Get-ScheduledTask -TaskPath $taskPath -TaskName $TaskName -ErrorAction Stop
    }
    catch {
        return $false
    }
    if ([string]$task.Description -ne $taskDescription) {
        throw "WP9_REFUSES_UNOWNED_TASK:$TaskName"
    }
    $principalSid = Convert-PrincipalToSid -UserId ([string]$task.Principal.UserId)
    if ($null -eq $principalSid -or $principalSid.Value -ne $localServiceSid.Value) {
        return $false
    }
    $actions = @($task.Actions)
    if ($actions.Count -ne 1) { return $false }
    if (-not ([string]$actions[0].Execute).Equals($powershellExe, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }
    if ([string]$actions[0].Arguments -ne $ExpectedArguments) { return $false }
    $enabled = [bool]$task.Settings.Enabled
    if ($enabled -ne $ExpectedEnabled) { return $false }
    if ([int]$task.Settings.RestartCount -ne [int]$contract.supervision.component_restart_count) {
        return $false
    }
    if ([string]$task.Settings.MultipleInstances -ne [string]$contract.supervision.multiple_instances) {
        return $false
    }
    if ($HealthTask) {
        $triggers = @($task.Triggers)
        $bootCount = @($triggers | Where-Object { $_.CimClass.CimClassName -eq "MSFT_TaskBootTrigger" }).Count
        $dailyCount = @($triggers | Where-Object { $_.CimClass.CimClassName -eq "MSFT_TaskDailyTrigger" }).Count
        if ($bootCount -ne 1 -or $dailyCount -ne 1 -or $triggers.Count -ne 2) {
            return $false
        }
    }
    # For disabled sealed slots, Windows' ScheduledTasks CIM provider may round-trip
    # inert trigger metadata even when New-ScheduledTask was created without -Trigger.
    # Disabled state is the safety boundary, so idempotence must not depend on that
    # provider-specific serialization detail.
    return $true
}

function New-Wp9Settings {
    return New-ScheduledTaskSettingsSet `
        -RestartCount ([int]$contract.supervision.component_restart_count) `
        -RestartInterval (New-TimeSpan -Seconds ([int]$contract.supervision.component_restart_interval_seconds)) `
        -ExecutionTimeLimit (New-TimeSpan -Minutes ([int]$contract.supervision.component_execution_limit_minutes)) `
        -MultipleInstances ([string]$contract.supervision.multiple_instances) `
        -StartWhenAvailable
}

function Register-OwnedTask {
    param(
        [string]$TaskName,
        [string]$Arguments,
        [bool]$Enabled,
        [bool]$HealthTask
    )

    $existing = Get-ScheduledTask -TaskPath $taskPath -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -ne $existing -and [string]$existing.Description -ne $taskDescription) {
        throw "WP9_REFUSES_UNOWNED_TASK:$TaskName"
    }
    if (Test-OwnedTaskDefinition `
        -TaskName $TaskName `
        -ExpectedArguments $Arguments `
        -ExpectedEnabled $Enabled `
        -HealthTask $HealthTask
    ) {
        return $false
    }
    if ($null -ne $existing) {
        Unregister-ScheduledTask -TaskPath $taskPath -TaskName $TaskName -Confirm:$false
    }

    $action = New-ScheduledTaskAction -Execute $powershellExe -Argument $Arguments
    $principal = New-ScheduledTaskPrincipal `
        -UserId "NT AUTHORITY\LOCAL SERVICE" `
        -LogonType ServiceAccount `
        -RunLevel Limited
    $settings = New-Wp9Settings
    if ($HealthTask) {
        $bootTrigger = New-ScheduledTaskTrigger -AtStartup
        $dailyTrigger = New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddMinutes(5))
        $definition = New-ScheduledTask `
            -Action $action `
            -Principal $principal `
            -Settings $settings `
            -Trigger @($bootTrigger, $dailyTrigger) `
            -Description $taskDescription
    }
    else {
        $definition = New-ScheduledTask `
            -Action $action `
            -Principal $principal `
            -Settings $settings `
            -Description $taskDescription
    }
    Register-ScheduledTask `
        -TaskName $TaskName `
        -TaskPath $taskPath `
        -InputObject $definition `
        -Force | Out-Null
    if (-not $Enabled) {
        Disable-ScheduledTask -TaskPath $taskPath -TaskName $TaskName | Out-Null
    }
    return $true
}

function Ensure-Wp9Tasks {
    Ensure-TaskFolder
    $changes = 0
    $healthArgs = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -ContractPath "{1}"' -f `
        $deployedHealth, $deployedContract
    $healthArgs = $healthArgs.Replace('\"', '"')
    if (Register-OwnedTask `
        -TaskName ([string]$contract.tasks.health_supervisor) `
        -Arguments $healthArgs `
        -Enabled $true `
        -HealthTask $true
    ) { $changes += 1 }

    foreach ($id in @("core_api", "web", "telegram", "watchtower", "ai_worker")) {
        $taskName = [string]$contract.tasks.$id
        $guardArgs = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -ComponentId {1}' -f `
            $deployedGuard, $id
        $guardArgs = $guardArgs.Replace('\"', '"')
        if (Register-OwnedTask `
            -TaskName $taskName `
            -Arguments $guardArgs `
            -Enabled $false `
            -HealthTask $false
        ) { $changes += 1 }
    }
    return $changes
}

function Remove-OwnedRehearsalTask {
    param([string]$TaskName)
    $task = Get-ScheduledTask -TaskPath $taskPath -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $task) { return }
    if ([string]$task.Description -ne $rehearsalDescription) {
        throw "WP9_REFUSES_UNOWNED_REHEARSAL_TASK:$TaskName"
    }
    Unregister-ScheduledTask -TaskPath $taskPath -TaskName $TaskName -Confirm:$false
}

function Read-RehearsalState {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    try {
        return Get-Content -LiteralPath $Path -Raw -ErrorAction Stop |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        return $null
    }
}

function Wait-RehearsalState {
    param(
        [string]$Path,
        [scriptblock]$Predicate,
        [int]$TimeoutSeconds
    )
    $deadline = [datetime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $state = Read-RehearsalState -Path $Path
        if ($null -ne $state -and (& $Predicate $state)) {
            return $state
        }
        Start-Sleep -Milliseconds 500
    } while ([datetime]::UtcNow -lt $deadline)
    return $null
}

function New-RehearsalTaskDefinition {
    param(
        [string]$Arguments,
        [bool]$WithRestart
    )
    $action = New-ScheduledTaskAction -Execute $powershellExe -Argument $Arguments
    $principal = New-ScheduledTaskPrincipal `
        -UserId "NT AUTHORITY\LOCAL SERVICE" `
        -LogonType ServiceAccount `
        -RunLevel Limited
    if ($WithRestart) {
        $settings = New-Wp9Settings
    }
    else {
        $settings = New-ScheduledTaskSettingsSet `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
            -MultipleInstances IgnoreNew
    }
    return New-ScheduledTask `
        -Action $action `
        -Principal $principal `
        -Settings $settings `
        -Description $rehearsalDescription
}

function Invoke-RestartRehearsal {
    $results = @()
    foreach ($id in @($contract.restart_rehearsal.slots | ForEach-Object { [string]$_ })) {
        $taskName = "OmniCIO.V10.Rehearsal.Restart.$id"
        $statePath = Join-Path $temporaryEvidenceRoot ("restart-{0}.json" -f $id)
        Remove-OwnedRehearsalTask -TaskName $taskName
        Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
        try {
            $arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -StatePath "{1}" -HoldSeconds 120' -f `
                $deployedWorker, $statePath
            $arguments = $arguments.Replace('\"', '"')
            $definition = New-RehearsalTaskDefinition -Arguments $arguments -WithRestart $true
            Register-ScheduledTask `
                -TaskName $taskName `
                -TaskPath $taskPath `
                -InputObject $definition `
                -Force | Out-Null
            Start-ScheduledTask -TaskPath $taskPath -TaskName $taskName
            $first = Wait-RehearsalState `
                -Path $statePath `
                -TimeoutSeconds 30 `
                -Predicate { param($state) [int]$state.run_count -eq 1 -and [string]$state.state -eq "RUNNING_FIRST_ATTEMPT" }
            if ($null -eq $first) { throw "WP9_RESTART_REHEARSAL_FIRST_ATTEMPT_TIMEOUT:$id" }
            $processId = [int]$first.process_id
            $process = Get-Process -Id $processId -ErrorAction Stop
            if ([string]$process.ProcessName -notmatch '^powershell$') {
                throw "WP9_RESTART_REHEARSAL_PROCESS_MISMATCH:$id"
            }
            Stop-Process -Id $processId -Force -ErrorAction Stop
            $recovered = Wait-RehearsalState `
                -Path $statePath `
                -TimeoutSeconds 120 `
                -Predicate { param($state) [int]$state.run_count -ge 2 -and [string]$state.state -eq "RECOVERED" }
            if ($null -eq $recovered) { throw "WP9_RESTART_REHEARSAL_RECOVERY_TIMEOUT:$id" }
            $results += [ordered]@{ component = $id; passed = $true; attempts = [int]$recovered.run_count }
        }
        finally {
            Remove-OwnedRehearsalTask -TaskName $taskName
            Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath "$statePath.tmp" -Force -ErrorAction SilentlyContinue
        }
    }
    $evidence = [ordered]@{
        schema_version = "1"
        rehearsal = "SYNTHETIC_BOUNDED_RESTART"
        observed_at_utc = [datetime]::UtcNow.ToString("o")
        passed = (@($results | Where-Object { $_.passed -ne $true }).Count -eq 0 -and $results.Count -gt 0)
        results = $results
        real_product_runtime_used = $false
        real_money_authority_changed = $false
    }
    $evidence | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $restartEvidencePath -Encoding UTF8
    return [bool]$evidence.passed
}

function Invoke-DependencyRehearsal {
    $taskName = "OmniCIO.V10.Rehearsal.Dependency"
    $statePath = Join-Path $temporaryEvidenceRoot "dependency-worker.json"
    $dependencyPath = Join-Path $temporaryEvidenceRoot "synthetic-dependency.ready"
    Remove-OwnedRehearsalTask -TaskName $taskName
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $dependencyPath -Force -ErrorAction SilentlyContinue
    try {
        $arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -StatePath "{1}" -DependencyPath "{2}"' -f `
            $deployedWorker, $statePath, $dependencyPath
        $arguments = $arguments.Replace('\"', '"')
        $definition = New-RehearsalTaskDefinition -Arguments $arguments -WithRestart $false
        Register-ScheduledTask `
            -TaskName $taskName `
            -TaskPath $taskPath `
            -InputObject $definition `
            -Force | Out-Null
        Start-ScheduledTask -TaskPath $taskPath -TaskName $taskName
        $blocked = Wait-RehearsalState `
            -Path $statePath `
            -TimeoutSeconds 30 `
            -Predicate { param($state) [string]$state.state -eq "BLOCKED" }
        if ($null -eq $blocked) { throw "WP9_DEPENDENCY_REHEARSAL_BLOCK_TIMEOUT" }
        Set-Content -LiteralPath $dependencyPath -Value "WP9-SYNTHETIC-DEPENDENCY-READY" -Encoding ASCII
        Start-ScheduledTask -TaskPath $taskPath -TaskName $taskName
        $recovered = Wait-RehearsalState `
            -Path $statePath `
            -TimeoutSeconds 30 `
            -Predicate { param($state) [string]$state.state -eq "RECOVERED" -and [int]$state.run_count -ge 2 }
        if ($null -eq $recovered) { throw "WP9_DEPENDENCY_REHEARSAL_RECOVERY_TIMEOUT" }
        $passed = $true
    }
    finally {
        Remove-OwnedRehearsalTask -TaskName $taskName
        Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath "$statePath.tmp" -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $dependencyPath -Force -ErrorAction SilentlyContinue
    }
    $evidence = [ordered]@{
        schema_version = "1"
        rehearsal = "SYNTHETIC_DEPENDENCY_FAILURE"
        observed_at_utc = [datetime]::UtcNow.ToString("o")
        blocked_when_dependency_missing = $true
        recovered_after_dependency_restore = [bool]$passed
        production_database_stopped = $false
        real_product_runtime_used = $false
        real_money_authority_changed = $false
        passed = [bool]$passed
    }
    $evidence | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $dependencyEvidencePath -Encoding UTF8
    return [bool]$passed
}

function Get-BootTimeUtc {
    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    return ([datetime]$os.LastBootUpTime).ToUniversalTime()
}

function Arm-RebootEvidence {
    $boot = Get-BootTimeUtc
    $evidence = [ordered]@{
        schema_version = "1"
        armed = $true
        armed_at_utc = [datetime]::UtcNow.ToString("o")
        pre_reboot_boot_time_utc = $boot.ToString("o")
        post_boot_observed = $false
        observed_boot_time_utc = $null
        supervisor_observed_at_utc = $null
        supervisor_status = $null
    }
    $evidence | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $rebootEvidencePath -Encoding UTF8
}

function Get-EvidencePass {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    try {
        $evidence = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop |
            ConvertFrom-Json -ErrorAction Stop
        return ($evidence.passed -eq $true)
    }
    catch { return $false }
}

function Invoke-HealthNow {
    $raw = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
        -File $deployedHealth -ContractPath $deployedContract -AsJson 2>$null | Out-String
    if ($LASTEXITCODE -ne 0) { throw "WP9_HEALTH_SUPERVISOR_FAILED" }
    try {
        return $raw.Trim() | ConvertFrom-Json -ErrorAction Stop
    }
    catch { throw "WP9_HEALTH_SUPERVISOR_OUTPUT_INVALID" }
}

function Get-LocalProfile {
    param(
        [string]$Mode,
        [int]$FirstChanges,
        [int]$SecondChanges,
        [bool]$RestartPass,
        [bool]$DependencyPass
    )

    $boundaries = Get-InheritedBoundaryState
    $health = $null
    if (Test-Path -LiteralPath $statusPath -PathType Leaf) {
        try {
            $health = Get-Content -LiteralPath $statusPath -Raw -ErrorAction Stop |
                ConvertFrom-Json -ErrorAction Stop
        }
        catch { $health = $null }
    }
    $rebootArmed = $false
    $postBoot = $false
    if (Test-Path -LiteralPath $rebootEvidencePath -PathType Leaf) {
        try {
            $reboot = Get-Content -LiteralPath $rebootEvidencePath -Raw -ErrorAction Stop |
                ConvertFrom-Json -ErrorAction Stop
            $rebootArmed = ($reboot.armed -eq $true)
            $postBoot = ($reboot.post_boot_observed -eq $true)
        }
        catch { }
    }
    $status = if (
        $boundaries.wp7 -and $boundaries.wp8 -and
        $SecondChanges -eq 0 -and $RestartPass -and $DependencyPass -and
        $null -ne $health -and [string]$health.status -in @("HEALTHY", "DEGRADED")
    ) {
        if ($postBoot) { "PASS" } else { "OWNER_REBOOT_REQUIRED" }
    }
    elseif ($Mode -eq "PREVIEW") { "OWNER_ACTION_REQUIRED" }
    else { "FAIL" }

    return [ordered]@{
        schema_version = "1"
        mode = $Mode
        status = $status
        inherited_boundaries = $boundaries
        structural_changes = [ordered]@{ first_pass = $FirstChanges; second_pass = $SecondChanges }
        idempotence_verified = ($SecondChanges -eq 0)
        restart_rehearsal_pass = $RestartPass
        dependency_rehearsal_pass = $DependencyPass
        reboot_armed = $rebootArmed
        post_boot_observed = $postBoot
        health_status = if ($null -ne $health) { [string]$health.status } else { "UNAVAILABLE" }
        real_secret_values_used = $false
        real_money_authority_changed = $false
    }
}

$mode = if ($Apply) { "APPLY" } elseif ($Verify) { "VERIFY" } else { "PREVIEW" }
$boundariesBefore = Get-InheritedBoundaryState

if (-not $Apply) {
    $restartPass = Get-EvidencePass -Path $restartEvidencePath
    $dependencyPass = Get-EvidencePass -Path $dependencyEvidencePath
    $profile = Get-LocalProfile `
        -Mode $mode `
        -FirstChanges 0 `
        -SecondChanges 0 `
        -RestartPass $restartPass `
        -DependencyPass $dependencyPass
    if ($AsJson) { $profile | ConvertTo-Json -Depth 8 -Compress }
    else {
        Write-Output ("WP9 supervision mode: {0}" -f $mode)
        Write-Output ("WP9 supervision status: {0}" -f $profile.status)
        Write-Output ("Inherited WP7 boundary: {0}" -f $profile.inherited_boundaries.wp7)
        Write-Output ("Inherited WP8 boundary: {0}" -f $profile.inherited_boundaries.wp8)
        Write-Output "Real secret values used: NO"
    }
    if ($Verify -and $profile.status -notin @("PASS", "OWNER_REBOOT_REQUIRED")) { exit 1 }
    exit 0
}

if (-not (Test-Administrator)) {
    throw "WP9_APPLY_REQUIRES_OWNER_ADMINISTRATOR"
}
if (-not $boundariesBefore.wp7 -or -not $boundariesBefore.wp8) {
    throw "WP9_INHERITED_BOUNDARY_NOT_READY"
}

$runnerSid = Get-RunnerServiceSid
$firstChanges = 0
$firstChanges += Ensure-Wp9Layout -RunnerSid $runnerSid
$firstChanges += Ensure-DeployedPayload
$firstChanges += Ensure-Wp9Tasks
Ensure-Wp9SchedulerReadBoundary -RunnerSid $runnerSid
Set-Wp9DirectoryAcl -Path $wp9Root -Class DEPLOYED -RunnerSid $runnerSid
Set-Wp9DirectoryAcl -Path $deployedRoot -Class DEPLOYED -RunnerSid $runnerSid
Set-Wp9DirectoryAcl -Path $evidenceRoot -Class EVIDENCE -RunnerSid $runnerSid
Set-Wp9DirectoryAcl -Path $temporaryEvidenceRoot -Class EVIDENCE -RunnerSid $runnerSid

$secondChanges = 0
$secondChanges += Ensure-Wp9Layout -RunnerSid $runnerSid
$secondChanges += Ensure-DeployedPayload
$secondChanges += Ensure-Wp9Tasks
Ensure-Wp9SchedulerReadBoundary -RunnerSid $runnerSid
if ($secondChanges -ne 0) {
    throw "WP9_IDEMPOTENCE_NOT_PROVEN"
}

$healthNow = Invoke-HealthNow
if ([string]$healthNow.status -notin @("HEALTHY", "DEGRADED")) {
    throw "WP9_HEALTH_NOT_SAFE_AFTER_APPLY"
}

$restartPass = Get-EvidencePass -Path $restartEvidencePath
$dependencyPass = Get-EvidencePass -Path $dependencyEvidencePath
if ($RunRehearsals) {
    $restartPass = Invoke-RestartRehearsal
    $dependencyPass = Invoke-DependencyRehearsal
}
if ($ArmReboot) {
    if (-not $restartPass -or -not $dependencyPass) {
        throw "WP9_REBOOT_NOT_ARMED_UNTIL_REHEARSALS_PASS"
    }
    Arm-RebootEvidence
}

$provisionState = [ordered]@{
    schema_version = "1"
    ownership = $ownershipMarker
    applied = $true
    idempotence_verified = ($secondChanges -eq 0)
    restart_rehearsal_pass = [bool]$restartPass
    dependency_rehearsal_pass = [bool]$dependencyPass
    future_product_slots_sealed = $true
    execution_task_created = $false
    real_secret_values_used = $false
    real_money_authority_changed = $false
}
$provisionState | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $provisionStatePath -Encoding UTF8
Set-Wp9DirectoryAcl -Path $evidenceRoot -Class EVIDENCE -RunnerSid $runnerSid

$profile = Get-LocalProfile `
    -Mode $mode `
    -FirstChanges $firstChanges `
    -SecondChanges $secondChanges `
    -RestartPass $restartPass `
    -DependencyPass $dependencyPass

if ($AsJson) { $profile | ConvertTo-Json -Depth 8 -Compress }
else {
    Write-Output "WP9 supervision mode: APPLY"
    Write-Output ("WP9 supervision status: {0}" -f $profile.status)
    Write-Output ("WP9 first-pass structural changes: {0}" -f $firstChanges)
    Write-Output ("WP9 second-pass structural changes: {0}" -f $secondChanges)
    Write-Output ("WP9 current health: {0}" -f $profile.health_status)
    Write-Output ("Restart rehearsal: {0}" -f $restartPass)
    Write-Output ("Dependency rehearsal: {0}" -f $dependencyPass)
    Write-Output ("Reboot armed: {0}" -f $profile.reboot_armed)
    Write-Output "Future product slots sealed: True"
    Write-Output "Execution task created: False"
    Write-Output "Real secret values used: NO"
    Write-Output "Real-money authority changed: NO"
}

if ($RestartComputer) {
    if ($profile.status -ne "OWNER_REBOOT_REQUIRED" -or -not $profile.reboot_armed) {
        throw "WP9_REBOOT_REFUSED_PRECONDITIONS_NOT_MET"
    }
    Write-Output "WP9 reviewed reboot scheduled in 10 seconds. Do not manually start application terminals after boot."
    & shutdown.exe /r /t 10 /c "Omni-CIO V10 WP9 reviewed reboot rehearsal"
    if ($LASTEXITCODE -ne 0) {
        throw "WP9_REBOOT_COMMAND_FAILED"
    }
}

exit 0
