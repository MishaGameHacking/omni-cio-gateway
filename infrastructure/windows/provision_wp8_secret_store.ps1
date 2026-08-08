[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Verify,
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

if ($Apply -and $Verify) {
    throw "Choose -Apply or -Verify, not both."
}
if ($Apply -and $env:OS -ne "Windows_NT") {
    throw "WP8 secret-store mutation requires Windows."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$contractPath = Join-Path $repoRoot "docs\architecture\V10_WP8_SECRET_STORE_CONTRACT.json"
$wp6ContractPath = Join-Path $repoRoot "docs\architecture\V10_WP6_IDENTITY_PRIVILEGE_CONTRACT.json"
$contract = Get-Content -LiteralPath $contractPath -Raw -ErrorAction Stop |
    ConvertFrom-Json -ErrorAction Stop
$wp6Contract = Get-Content -LiteralPath $wp6ContractPath -Raw -ErrorAction Stop |
    ConvertFrom-Json -ErrorAction Stop

if ([string]$contract.schema_version -ne "1") {
    throw "Unsupported WP8 secret-store contract schema."
}
if ([string]$wp6Contract.schema_version -ne "1") {
    throw "Unsupported WP6 identity contract schema."
}

$secretRoot = [string]$contract.paths.secret_root
$evidenceRoot = [string]$contract.paths.evidence_root
$wp6Sentinel = [string]$contract.paths.wp6_execution_sentinel
$statePath = Join-Path $evidenceRoot "wp8-secret-store-state.json"
$evidenceMarkerPath = Join-Path $evidenceRoot ".omni-cio-wp8-owned"
$ownershipMarkerName = ".omni-cio-wp8-owned"
$ownershipMarkerValue = "OMNI-CIO-V10-WP8-NON-SECRET-OWNED-v1"
$runtimeName = [string]$contract.identities.runtime_role
$executionName = [string]$contract.identities.execution_role
$runnerRoot = "C:\actions-runner"

if ($secretRoot -ne [string]$wp6Contract.paths.secret_root) {
    throw "WP8 secret root must reuse the accepted WP6 secret root."
}
if ($wp6Sentinel -ne [string]$wp6Contract.paths.execution_secret_sentinel) {
    throw "WP8 must preserve the exact accepted WP6 execution sentinel."
}
if ($runtimeName -ne [string]$wp6Contract.roles.runtime.account_name) {
    throw "WP8 runtime role does not match accepted WP6 identity contract."
}
if ($executionName -ne [string]$wp6Contract.roles.execution.account_name) {
    throw "WP8 execution role does not match accepted WP6 identity contract."
}
if ([string]$contract.provider.scope -ne "LOCAL_MACHINE") {
    throw "WP8 requires the reviewed LOCAL_MACHINE DPAPI scope."
}
if ([bool]$contract.provider.local_machine_scope_is_not_principal_authorization -ne $true) {
    throw "WP8 contract must acknowledge the LocalMachine DPAPI authorization caveat."
}

Add-Type -AssemblyName System.Security

function Test-Administrator {
    if ($env:OS -ne "Windows_NT") {
        return $false
    }
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole(
        [System.Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function Get-LocalRoleState {
    param([Parameter(Mandatory = $true)][string]$Name)

    if ($env:OS -ne "Windows_NT") {
        return [ordered]@{
            present = $false
            enabled = $null
            administrator = $null
            sid = $null
        }
    }
    try {
        $role = Get-LocalUser -Name $Name -ErrorAction Stop
    }
    catch {
        return [ordered]@{
            present = $false
            enabled = $null
            administrator = $null
            sid = $null
        }
    }

    $isAdmin = $null
    try {
        $adminSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
        $adminGroup = Get-LocalGroup -SID $adminSid -ErrorAction Stop
        $members = @(Get-LocalGroupMember -Group $adminGroup -ErrorAction Stop)
        $isAdmin = [bool]($members | Where-Object { $_.SID.Value -eq $role.SID.Value })
    }
    catch {
        $isAdmin = $null
    }

    return [ordered]@{
        present = $true
        enabled = [bool]$role.Enabled
        administrator = $isAdmin
        sid = $role.SID
    }
}

function Get-RunnerServiceSid {
    if ($env:OS -ne "Windows_NT") {
        throw "RUNNER_SERVICE_IDENTITY_UNAVAILABLE"
    }
    $serviceNamePattern = '^actions\.runner\.'
    $services = @(
        Get-CimInstance Win32_Service -ErrorAction Stop |
            Where-Object {
                $pathName = [string]$_.PathName
                $_.Name -match $serviceNamePattern -and
                -not [string]::IsNullOrWhiteSpace($pathName) -and
                $pathName.IndexOf(
                    $runnerRoot,
                    [System.StringComparison]::OrdinalIgnoreCase
                ) -ge 0
            }
    )
    if ($services.Count -ne 1) {
        throw "RUNNER_SERVICE_IDENTITY_UNAVAILABLE"
    }
    try {
        $account = [System.Security.Principal.NTAccount]::new([string]$services[0].StartName)
        return $account.Translate([System.Security.Principal.SecurityIdentifier])
    }
    catch {
        throw "RUNNER_SERVICE_IDENTITY_UNAVAILABLE"
    }
}

function New-FileSystemRule {
    param(
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$Sid,
        [Parameter(Mandatory = $true)]
        [System.Security.AccessControl.FileSystemRights]$Rights,
        [System.Security.AccessControl.InheritanceFlags]$Inheritance = [System.Security.AccessControl.InheritanceFlags]::None,
        [System.Security.AccessControl.PropagationFlags]$Propagation = [System.Security.AccessControl.PropagationFlags]::None
    )

    return [System.Security.AccessControl.FileSystemAccessRule]::new(
        $Sid,
        $Rights,
        $Inheritance,
        $Propagation,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
}

function Set-ProtectedDirectoryAcl {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [System.Security.Principal.SecurityIdentifier]$ConsumerSid,
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$RunnerSid
    )

    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-FileSystemRule -Sid $systemSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl)))
    $acl.AddAccessRule((New-FileSystemRule -Sid $adminsSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl)))
    if ($null -ne $ConsumerSid) {
        $acl.AddAccessRule((New-FileSystemRule -Sid $ConsumerSid -Rights ([System.Security.AccessControl.FileSystemRights]::ReadAndExecute)))
    }
    $runnerRights = (
        [System.Security.AccessControl.FileSystemRights]::ReadPermissions -bor
        [System.Security.AccessControl.FileSystemRights]::ReadAttributes -bor
        [System.Security.AccessControl.FileSystemRights]::Traverse
    )
    $acl.AddAccessRule((New-FileSystemRule -Sid $RunnerSid -Rights $runnerRights))
    Set-Acl -LiteralPath $Path -AclObject $acl -ErrorAction Stop
}

function Set-ProtectedFileAcl {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [System.Security.Principal.SecurityIdentifier]$ConsumerSid,
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$RunnerSid
    )

    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $acl = [System.Security.AccessControl.FileSecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-FileSystemRule -Sid $systemSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl)))
    $acl.AddAccessRule((New-FileSystemRule -Sid $adminsSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl)))
    if ($null -ne $ConsumerSid) {
        $acl.AddAccessRule((New-FileSystemRule -Sid $ConsumerSid -Rights ([System.Security.AccessControl.FileSystemRights]::Read)))
    }
    $runnerRights = (
        [System.Security.AccessControl.FileSystemRights]::ReadPermissions -bor
        [System.Security.AccessControl.FileSystemRights]::ReadAttributes
    )
    $acl.AddAccessRule((New-FileSystemRule -Sid $RunnerSid -Rights $runnerRights))
    Set-Acl -LiteralPath $Path -AclObject $acl -ErrorAction Stop
}

function Set-EvidenceAcl {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$RunnerSid,
        [switch]$File
    )

    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    if ($File) {
        $acl = [System.Security.AccessControl.FileSecurity]::new()
    }
    else {
        $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    }
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-FileSystemRule -Sid $systemSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl)))
    $acl.AddAccessRule((New-FileSystemRule -Sid $adminsSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl)))
    if ($File) {
        $acl.AddAccessRule((New-FileSystemRule -Sid $RunnerSid -Rights ([System.Security.AccessControl.FileSystemRights]::Read)))
    }
    else {
        $acl.AddAccessRule((New-FileSystemRule -Sid $RunnerSid -Rights ([System.Security.AccessControl.FileSystemRights]::ReadAndExecute)))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl -ErrorAction Stop
}

function Get-ConsumerSid {
    param(
        [Parameter(Mandatory = $true)]$Spec,
        [Parameter(Mandatory = $true)]$RuntimeState,
        [Parameter(Mandatory = $true)]$ExecutionState
    )

    $consumer = [string]$Spec.consumer_role
    if ($consumer -eq $runtimeName) {
        return $RuntimeState.sid
    }
    if ($consumer -eq $executionName) {
        return $ExecutionState.sid
    }
    return $null
}

function Protect-Wp8Bytes {
    param([Parameter(Mandatory = $true)][byte[]]$PlainBytes)

    return [System.Security.Cryptography.ProtectedData]::Protect(
        $PlainBytes,
        $null,
        [System.Security.Cryptography.DataProtectionScope]::LocalMachine
    )
}

function Unprotect-Wp8Bytes {
    param([Parameter(Mandatory = $true)][byte[]]$ProtectedBytes)

    return [System.Security.Cryptography.ProtectedData]::Unprotect(
        $ProtectedBytes,
        $null,
        [System.Security.Cryptography.DataProtectionScope]::LocalMachine
    )
}

function Test-ByteArraysEqual {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Left,
        [Parameter(Mandatory = $true)][byte[]]$Right
    )

    if ($Left.Length -ne $Right.Length) {
        return $false
    }
    for ($index = 0; $index -lt $Left.Length; $index++) {
        if ($Left[$index] -ne $Right[$index]) {
            return $false
        }
    }
    return $true
}

function New-RandomSentinelBytes {
    param([int]$Length = 32)

    $bytes = New-Object byte[] $Length
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }
    return $bytes
}

function Invoke-RotationRehearsal {
    $first = $null
    $second = $null
    $firstProtected = $null
    $secondProtected = $null
    $firstRecovered = $null
    $secondRecovered = $null
    try {
        $first = New-RandomSentinelBytes
        $firstProtected = Protect-Wp8Bytes -PlainBytes $first
        $firstRecovered = Unprotect-Wp8Bytes -ProtectedBytes $firstProtected
        if (-not (Test-ByteArraysEqual -Left $first -Right $firstRecovered)) {
            return $false
        }

        $second = New-RandomSentinelBytes
        $secondProtected = Protect-Wp8Bytes -PlainBytes $second
        $secondRecovered = Unprotect-Wp8Bytes -ProtectedBytes $secondProtected
        if (-not (Test-ByteArraysEqual -Left $second -Right $secondRecovered)) {
            return $false
        }
        if (Test-ByteArraysEqual -Left $firstProtected -Right $secondProtected) {
            return $false
        }
        return $true
    }
    finally {
        foreach ($buffer in @(
            $first,
            $second,
            $firstRecovered,
            $secondRecovered
        )) {
            if ($null -ne $buffer) {
                [Array]::Clear($buffer, 0, $buffer.Length)
            }
        }
    }
}

function Ensure-OwnedClassDirectory {
    param(
        [Parameter(Mandatory = $true)]$Spec,
        [Parameter(Mandatory = $true)]$ConsumerSid,
        [Parameter(Mandatory = $true)]$RunnerSid
    )

    $path = [string]$Spec.directory
    $markerPath = Join-Path $path $ownershipMarkerName
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
    elseif (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
        throw "WP8 refuses to adopt an unmarked existing class directory."
    }

    if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
        Set-Content -LiteralPath $markerPath -Value $ownershipMarkerValue -Encoding ASCII -NoNewline
    }
    else {
        $marker = Get-Content -LiteralPath $markerPath -Raw -ErrorAction Stop
        if ($marker -ne $ownershipMarkerValue) {
            throw "WP8 class ownership marker mismatch."
        }
    }

    Set-ProtectedDirectoryAcl -Path $path -ConsumerSid $ConsumerSid -RunnerSid $RunnerSid
    Set-ProtectedFileAcl -Path $markerPath -ConsumerSid $ConsumerSid -RunnerSid $RunnerSid
}

function Ensure-SentinelBlob {
    param(
        [Parameter(Mandatory = $true)]$Spec,
        [Parameter(Mandatory = $true)]$ConsumerSid,
        [Parameter(Mandatory = $true)]$RunnerSid
    )

    $path = Join-Path ([string]$Spec.directory) ([string]$Spec.sentinel_blob)
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        $plain = $null
        $protected = $null
        try {
            $plain = New-RandomSentinelBytes
            $protected = Protect-Wp8Bytes -PlainBytes $plain
            [System.IO.File]::WriteAllBytes($path, $protected)
        }
        finally {
            if ($null -ne $plain) {
                [Array]::Clear($plain, 0, $plain.Length)
            }
        }
    }
    Set-ProtectedFileAcl -Path $path -ConsumerSid $ConsumerSid -RunnerSid $RunnerSid

    $protectedExisting = $null
    $recovered = $null
    try {
        $protectedExisting = [System.IO.File]::ReadAllBytes($path)
        $recovered = Unprotect-Wp8Bytes -ProtectedBytes $protectedExisting
        if ($recovered.Length -lt 16) {
            throw "WP8 non-secret sentinel validation failed."
        }
    }
    finally {
        if ($null -ne $recovered) {
            [Array]::Clear($recovered, 0, $recovered.Length)
        }
    }
}

function Get-ExistingLifecycleMap {
    if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
        return @{}
    }
    try {
        $state = Get-Content -LiteralPath $statePath -Raw -ErrorAction Stop |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "Existing WP8 sanitized state is invalid."
    }
    if ([string]$state.schema_version -ne "1") {
        throw "Existing WP8 sanitized state schema mismatch."
    }
    $map = @{}
    foreach ($entry in @($state.classes)) {
        $map[[string]$entry.secret_class] = $entry
    }
    return $map
}

function Write-SanitizedState {
    param(
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$RunnerSid,
        [Parameter(Mandatory = $true)][bool]$ReadRotationPassed,
        [Parameter(Mandatory = $true)][bool]$TelegramRotationPassed
    )

    if (-not (Test-Path -LiteralPath $evidenceRoot -PathType Container)) {
        New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
    }
    if (-not (Test-Path -LiteralPath $evidenceMarkerPath -PathType Leaf)) {
        Set-Content -LiteralPath $evidenceMarkerPath -Value $ownershipMarkerValue -Encoding ASCII -NoNewline
    }
    else {
        $marker = Get-Content -LiteralPath $evidenceMarkerPath -Raw -ErrorAction Stop
        if ($marker -ne $ownershipMarkerValue) {
            throw "Existing WP8 evidence ownership marker mismatch."
        }
    }

    $existing = Get-ExistingLifecycleMap
    $classes = @(
        foreach ($spec in @($contract.secret_classes)) {
            $id = [string]$spec.id
            $state = "UNPROVISIONED"
            $version = 0
            $compromised = $false
            $provisioned = $false
            if ($existing.ContainsKey($id)) {
                $old = $existing[$id]
                $state = [string]$old.state
                $version = [int]$old.version
                $compromised = [bool]$old.compromised
                $provisioned = [bool]$old.provisioned
            }
            [ordered]@{
                schema_version = "1"
                secret_class = $id
                owner = "OWNER_ADMIN"
                purpose = [string]$spec.purpose
                scope = [string]$spec.scope
                consumer_role = [string]$spec.consumer_role
                state = $state
                version = $version
                rotation_procedure = "WP8_LOCAL_SECURE_PROMPT_ROTATE_V1"
                revocation_procedure = "WP8_LOCAL_REMOVE_AND_ISSUER_REVOKE_V1"
                compromised = $compromised
                provisioned = $provisioned
            }
        }
    )
    $stateObject = [ordered]@{
        schema_version = "1"
        owner_marker = $ownershipMarkerValue
        provider = "WINDOWS_DPAPI_LOCAL_MACHINE_PLUS_PROTECTED_DACL"
        rotation_rehearsal = [ordered]@{
            broker_read = $ReadRotationPassed
            telegram_bot = $TelegramRotationPassed
        }
        classes = $classes
        real_secret_values_used_for_wp8_acceptance = $false
        privacy = [ordered]@{
            raw_usernames_collected = $false
            sids_emitted = $false
            hostnames_collected = $false
            addresses_collected = $false
            secret_values_collected = $false
            secret_hashes_collected = $false
            ciphertext_collected = $false
            account_ids_collected = $false
            private_data_collected = $false
            process_dumps_collected = $false
        }
    }
    $json = $stateObject | ConvertTo-Json -Depth 8
    Set-Content -LiteralPath $statePath -Value $json -Encoding UTF8
    Set-EvidenceAcl -Path $evidenceRoot -RunnerSid $RunnerSid
    Set-EvidenceAcl -Path $evidenceMarkerPath -RunnerSid $RunnerSid -File
    Set-EvidenceAcl -Path $statePath -RunnerSid $RunnerSid -File
}

function Get-AccessRulesBySid {
    param([Parameter(Mandatory = $true)][string]$Path)

    $acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
    return @($acl.GetAccessRules(
        $true,
        $true,
        [System.Security.Principal.SecurityIdentifier]
    ))
}

function Test-AllowRight {
    param(
        [Parameter(Mandatory = $true)]$Rules,
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$Sid,
        [Parameter(Mandatory = $true)]
        [System.Security.AccessControl.FileSystemRights]$Right
    )

    foreach ($rule in @($Rules)) {
        if (
            $rule.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow -and
            $rule.IdentityReference.Value -eq $Sid.Value -and
            (($rule.FileSystemRights -band $Right) -eq $Right)
        ) {
            return $true
        }
    }
    return $false
}

function Test-AnyAllowMask {
    param(
        [Parameter(Mandatory = $true)]$Rules,
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$Sid,
        [Parameter(Mandatory = $true)]
        [System.Security.AccessControl.FileSystemRights]$Mask
    )

    foreach ($rule in @($Rules)) {
        if (
            $rule.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow -and
            $rule.IdentityReference.Value -eq $Sid.Value -and
            (($rule.FileSystemRights -band $Mask) -ne 0)
        ) {
            return $true
        }
    }
    return $false
}

function Test-BroadReadExposure {
    param([Parameter(Mandatory = $true)]$Rules)

    $broadSids = @(
        "S-1-1-0",
        "S-1-5-11",
        "S-1-5-32-545"
    )
    foreach ($rule in @($Rules)) {
        if (
            $rule.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow -and
            $rule.IdentityReference.Value -in $broadSids -and
            (($rule.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::ReadData) -ne 0)
        ) {
            return $true
        }
    }
    return $false
}

function Test-CurrentProcessIsRunner {
    param(
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$RunnerSid
    )

    try {
        $current = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
        return $current.Value -eq $RunnerSid.Value
    }
    catch {
        return $false
    }
}

function Test-DataReadAttempt {
    param([Parameter(Mandatory = $true)][string]$Path)

    try {
        $stream = [System.IO.File]::Open(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite
        )
        $stream.Dispose()
        return "UNEXPECTED_READ_ALLOWED"
    }
    catch [System.UnauthorizedAccessException] {
        return "ACCESS_DENIED"
    }
    catch {
        return "READ_ERROR"
    }
}

function Get-Profile {
    param([string]$Mode)

    $reasons = New-Object System.Collections.Generic.List[string]
    $runtimeState = Get-LocalRoleState -Name $runtimeName
    $executionState = Get-LocalRoleState -Name $executionName

    if (-not $runtimeState.present -or $runtimeState.enabled -ne $false -or $runtimeState.administrator -ne $false) {
        [void]$reasons.Add("WP6_RUNTIME_ROLE_NOT_READY")
    }
    if (-not $executionState.present -or $executionState.enabled -ne $false -or $executionState.administrator -ne $false) {
        [void]$reasons.Add("WP6_EXECUTION_ROLE_NOT_READY")
    }
    if (-not (Test-Path -LiteralPath $secretRoot -PathType Container)) {
        [void]$reasons.Add("WP6_SECRET_ROOT_NOT_READY")
    }
    if (-not (Test-Path -LiteralPath $wp6Sentinel -PathType Leaf)) {
        [void]$reasons.Add("WP6_EXECUTION_SENTINEL_NOT_READY")
    }

    $runnerSid = $null
    try {
        $runnerSid = Get-RunnerServiceSid
    }
    catch {
        [void]$reasons.Add("RUNNER_SERVICE_IDENTITY_UNAVAILABLE")
    }

    $stateReady = $false
    $rotationRead = $false
    $rotationTelegram = $false
    $realSecretValuesUsed = $false
    $stateClasses = @{}
    if (Test-Path -LiteralPath $statePath -PathType Leaf) {
        try {
            $state = Get-Content -LiteralPath $statePath -Raw -ErrorAction Stop |
                ConvertFrom-Json -ErrorAction Stop
            if (
                [string]$state.schema_version -eq "1" -and
                [string]$state.owner_marker -eq $ownershipMarkerValue
            ) {
                $stateReady = $true
                $rotationRead = [bool]$state.rotation_rehearsal.broker_read
                $rotationTelegram = [bool]$state.rotation_rehearsal.telegram_bot
                $realSecretValuesUsed = [bool]$state.real_secret_values_used_for_wp8_acceptance
                foreach ($item in @($state.classes)) {
                    $stateClasses[[string]$item.secret_class] = $item
                }
            }
        }
        catch {
            $stateReady = $false
        }
    }
    if (-not $stateReady) {
        [void]$reasons.Add("WP8_SANITIZED_STATE_NOT_READY")
    }
    if (-not $rotationRead) {
        [void]$reasons.Add("BROKER_READ_ROTATION_REHEARSAL_NOT_PROVEN")
    }
    if (-not $rotationTelegram) {
        [void]$reasons.Add("TELEGRAM_ROTATION_REHEARSAL_NOT_PROVEN")
    }
    if ($realSecretValuesUsed) {
        [void]$reasons.Add("REAL_SECRET_VALUE_USED_IN_WP8_ACCEPTANCE")
    }

    $isRunnerProcess = $false
    if ($null -ne $runnerSid) {
        $isRunnerProcess = Test-CurrentProcessIsRunner -RunnerSid $runnerSid
    }

    $writeMask = (
        [System.Security.AccessControl.FileSystemRights]::WriteData -bor
        [System.Security.AccessControl.FileSystemRights]::AppendData -bor
        [System.Security.AccessControl.FileSystemRights]::WriteAttributes -bor
        [System.Security.AccessControl.FileSystemRights]::WriteExtendedAttributes -bor
        [System.Security.AccessControl.FileSystemRights]::Delete -bor
        [System.Security.AccessControl.FileSystemRights]::ChangePermissions -bor
        [System.Security.AccessControl.FileSystemRights]::TakeOwnership
    )

    $classProfiles = @(
        foreach ($spec in @($contract.secret_classes)) {
            $id = [string]$spec.id
            $directory = [string]$spec.directory
            $sentinel = Join-Path $directory ([string]$spec.sentinel_blob)
            $directoryPresent = Test-Path -LiteralPath $directory -PathType Container
            $sentinelPresent = Test-Path -LiteralPath $sentinel -PathType Leaf
            $intendedReadGrant = $false
            $runtimeReadGrant = $false
            $executionReadGrant = $false
            $runnerReadDataGrant = $false
            $runnerWriteGrant = $false
            $broadReadExposure = $false
            $runnerDataRead = if ($isRunnerProcess) { "NOT_TESTED" } else { "NOT_RUNNER_PROCESS" }

            if ($directoryPresent -and $sentinelPresent -and $null -ne $runnerSid) {
                try {
                    $rules = Get-AccessRulesBySid -Path $sentinel
                    $runnerReadDataGrant = Test-AllowRight -Rules $rules -Sid $runnerSid -Right ([System.Security.AccessControl.FileSystemRights]::ReadData)
                    $runnerWriteGrant = Test-AnyAllowMask -Rules $rules -Sid $runnerSid -Mask $writeMask
                    $broadReadExposure = Test-BroadReadExposure -Rules $rules
                    if ($runtimeState.present) {
                        $runtimeReadGrant = Test-AllowRight -Rules $rules -Sid $runtimeState.sid -Right ([System.Security.AccessControl.FileSystemRights]::ReadData)
                    }
                    if ($executionState.present) {
                        $executionReadGrant = Test-AllowRight -Rules $rules -Sid $executionState.sid -Right ([System.Security.AccessControl.FileSystemRights]::ReadData)
                    }
                    $consumer = [string]$spec.consumer_role
                    if ($consumer -eq $runtimeName) {
                        $intendedReadGrant = $runtimeReadGrant
                    }
                    elseif ($consumer -eq $executionName) {
                        $intendedReadGrant = $executionReadGrant
                    }
                    else {
                        $intendedReadGrant = (-not $runtimeReadGrant -and -not $executionReadGrant)
                    }
                    if ($isRunnerProcess) {
                        $runnerDataRead = Test-DataReadAttempt -Path $sentinel
                    }
                }
                catch {
                    $intendedReadGrant = $false
                    $runnerDataRead = "ACL_INSPECTION_ERROR"
                }
            }

            if (-not $directoryPresent) {
                [void]$reasons.Add("WP8_CLASS_DIRECTORY_NOT_READY:$id")
            }
            if (-not $sentinelPresent) {
                [void]$reasons.Add("WP8_SENTINEL_NOT_READY:$id")
            }
            if (-not $intendedReadGrant) {
                [void]$reasons.Add("WP8_INTENDED_SECRET_GRANT_INVALID:$id")
            }
            if ($runnerReadDataGrant) {
                [void]$reasons.Add("CI_RUNNER_SECRET_READ_GRANT_PRESENT:$id")
            }
            if ($runnerWriteGrant) {
                [void]$reasons.Add("CI_RUNNER_SECRET_WRITE_GRANT_PRESENT:$id")
            }
            if ($broadReadExposure) {
                [void]$reasons.Add("BROAD_SECRET_READ_EXPOSURE:$id")
            }
            if ($id -eq "broker_read" -and $executionReadGrant) {
                [void]$reasons.Add("EXECUTION_ROLE_READ_BROKER_SECRET_EXPOSURE")
            }
            if ($id -eq "broker_trading" -and $runtimeReadGrant) {
                [void]$reasons.Add("RUNTIME_ROLE_TRADING_SECRET_EXPOSURE")
            }
            if ($isRunnerProcess -and $runnerDataRead -ne "ACCESS_DENIED") {
                [void]$reasons.Add("CI_RUNNER_SECRET_DATA_READ_NOT_DENIED:$id")
            }

            $lifecycleState = "UNKNOWN"
            $lifecycleVersion = -1
            $provisioned = $null
            if ($stateClasses.ContainsKey($id)) {
                $entry = $stateClasses[$id]
                $lifecycleState = [string]$entry.state
                $lifecycleVersion = [int]$entry.version
                $provisioned = [bool]$entry.provisioned
                if ($provisioned) {
                    [void]$reasons.Add("REAL_SECRET_ALREADY_PROVISIONED_DURING_WP8_ACCEPTANCE:$id")
                }
            }
            else {
                [void]$reasons.Add("WP8_LIFECYCLE_METADATA_NOT_READY:$id")
            }

            [ordered]@{
                secret_class = $id
                directory_present = [bool]$directoryPresent
                sentinel_present = [bool]$sentinelPresent
                intended_read_grant = [bool]$intendedReadGrant
                runtime_read_grant = [bool]$runtimeReadGrant
                execution_read_grant = [bool]$executionReadGrant
                runner_read_data_grant = [bool]$runnerReadDataGrant
                runner_write_grant = [bool]$runnerWriteGrant
                broad_read_exposure = [bool]$broadReadExposure
                runner_data_read = $runnerDataRead
                lifecycle_state = $lifecycleState
                lifecycle_version = $lifecycleVersion
                real_secret_provisioned = $provisioned
            }
        }
    )

    $status = if ($reasons.Count -eq 0) { "PASS" } elseif ($Mode -eq "PREVIEW") { "OWNER_ACTION_REQUIRED" } else { "FAIL" }
    return [ordered]@{
        schema_version = "1"
        mode = $Mode
        status = $status
        reasons = @($reasons)
        provider = "WINDOWS_DPAPI_LOCAL_MACHINE_PLUS_PROTECTED_DACL"
        runner_process = [bool]$isRunnerProcess
        runtime_role = [ordered]@{
            present = [bool]$runtimeState.present
            enabled = $runtimeState.enabled
            administrator = $runtimeState.administrator
        }
        execution_role = [ordered]@{
            present = [bool]$executionState.present
            enabled = $executionState.enabled
            administrator = $executionState.administrator
        }
        rotation_rehearsal = [ordered]@{
            broker_read = [bool]$rotationRead
            telegram_bot = [bool]$rotationTelegram
        }
        classes = $classProfiles
        real_secret_values_used = [bool]$realSecretValuesUsed
        privacy = [ordered]@{
            raw_usernames_collected = $false
            sids_emitted = $false
            hostnames_collected = $false
            addresses_collected = $false
            secret_values_collected = $false
            secret_hashes_collected = $false
            ciphertext_collected = $false
            account_ids_collected = $false
            private_data_collected = $false
            process_dumps_collected = $false
        }
    }
}

function Write-Profile {
    param([Parameter(Mandatory = $true)]$Profile)

    if ($AsJson) {
        $Profile | ConvertTo-Json -Depth 10 -Compress
        return
    }

    Write-Host "WP8 secret-store mode: $($Profile.mode)"
    Write-Host "WP8 secret-store status: $($Profile.status)"
    Write-Host "DPAPI provider: LocalMachine + protected DACL"
    Write-Host "Runner process: $($Profile.runner_process)"
    Write-Host "Read-token rotation rehearsal: $($Profile.rotation_rehearsal.broker_read)"
    Write-Host "Telegram rotation rehearsal: $($Profile.rotation_rehearsal.telegram_bot)"
    foreach ($item in @($Profile.classes)) {
        Write-Host (
            "Class {0}: directory={1}; sentinel={2}; intended-read={3}; runner-read={4}; runner-write={5}; broad-read={6}; runner-data={7}; lifecycle={8}; provisioned={9}" -f
            $item.secret_class,
            $item.directory_present,
            $item.sentinel_present,
            $item.intended_read_grant,
            $item.runner_read_data_grant,
            $item.runner_write_grant,
            $item.broad_read_exposure,
            $item.runner_data_read,
            $item.lifecycle_state,
            $item.real_secret_provisioned
        )
    }
    Write-Host "Real secret values used: NO"
    if (@($Profile.reasons).Count -gt 0) {
        Write-Host "Reason codes: $(@($Profile.reasons) -join ', ')"
    }
}

if (-not $Apply -and -not $Verify) {
    $profile = Get-Profile -Mode "PREVIEW"
    Write-Profile -Profile $profile
    exit 0
}

if ($Apply) {
    if (-not (Test-Administrator)) {
        throw "WP8 secret-store -Apply requires an elevated OWNER-admin PowerShell."
    }
    if (-not (Test-Path -LiteralPath $secretRoot -PathType Container)) {
        throw "WP8 requires the accepted WP6 secret root before mutation."
    }
    if (-not (Test-Path -LiteralPath $wp6Sentinel -PathType Leaf)) {
        throw "WP8 requires the accepted WP6 execution sentinel before mutation."
    }

    $runtimeState = Get-LocalRoleState -Name $runtimeName
    $executionState = Get-LocalRoleState -Name $executionName
    foreach ($roleSpec in @(
        @("runtime", $runtimeState),
        @("execution", $executionState)
    )) {
        $roleState = $roleSpec[1]
        if (
            $roleState.present -ne $true -or
            $roleState.enabled -ne $false -or
            $roleState.administrator -ne $false
        ) {
            throw "WP6_ROLE_NOT_READY:$($roleSpec[0])"
        }
    }

    $runnerSid = Get-RunnerServiceSid
    foreach ($spec in @($contract.secret_classes)) {
        $consumerSid = Get-ConsumerSid -Spec $spec -RuntimeState $runtimeState -ExecutionState $executionState
        Ensure-OwnedClassDirectory -Spec $spec -ConsumerSid $consumerSid -RunnerSid $runnerSid
        Ensure-SentinelBlob -Spec $spec -ConsumerSid $consumerSid -RunnerSid $runnerSid
    }

    $readRotation = Invoke-RotationRehearsal
    $telegramRotation = Invoke-RotationRehearsal
    if (-not $readRotation) {
        throw "WP8 broker-read non-secret rotation rehearsal failed."
    }
    if (-not $telegramRotation) {
        throw "WP8 Telegram non-secret rotation rehearsal failed."
    }
    Write-SanitizedState -RunnerSid $runnerSid -ReadRotationPassed $readRotation -TelegramRotationPassed $telegramRotation

    $profile = Get-Profile -Mode "APPLY"
    Write-Profile -Profile $profile
    if ($profile.status -eq "PASS") {
        exit 0
    }
    exit 2
}

$verifyProfile = Get-Profile -Mode "VERIFY"
Write-Profile -Profile $verifyProfile
if ($verifyProfile.status -eq "PASS") {
    exit 0
}
exit 2
