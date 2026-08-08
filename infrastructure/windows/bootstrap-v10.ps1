[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Verify,
    [switch]$InstallPrerequisites,
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($Apply -and $Verify) {
    throw "Choose exactly one mutating mode: -Apply or non-mutating -Verify."
}
if ($InstallPrerequisites -and -not $Apply) {
    throw "-InstallPrerequisites is valid only together with -Apply."
}
if ($env:OS -ne "Windows_NT" -and $Apply) {
    throw "WP7 bootstrap mutation requires Windows."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$contractPath = Join-Path $repoRoot "docs\architecture\V10_WP7_BOOTSTRAP_CONTRACT.json"
$toolchainPath = Join-Path $repoRoot "docs\architecture\V10_TOOLCHAIN_BASELINE.json"
$runnerChecker = Join-Path $repoRoot "scripts\check_self_hosted_windows_runner_service.ps1"

$contract = Get-Content -LiteralPath $contractPath -Raw -ErrorAction Stop |
    ConvertFrom-Json -ErrorAction Stop
$toolchain = Get-Content -LiteralPath $toolchainPath -Raw -ErrorAction Stop |
    ConvertFrom-Json -ErrorAction Stop

if ([string]$contract.schema_version -ne "1") {
    throw "Unsupported WP7 bootstrap contract schema."
}
if ([int]$toolchain.schema_version -ne 1) {
    throw "Unsupported V10 toolchain contract schema."
}

$expectedRoot = "C:\ProgramData\OmniCIO"
$bootstrapRoot = Join-Path $expectedRoot "bootstrap"
$runtimeRoot = Join-Path $expectedRoot "runtime"
$dataRoot = Join-Path $expectedRoot "data"
$logsRoot = Join-Path $expectedRoot "logs"
$servicesRoot = Join-Path $expectedRoot "services"
$secretRoot = Join-Path $expectedRoot "secrets"
$runnerRoot = "C:\actions-runner"
$ownershipMarker = "OMNI-CIO-V10-WP7-NON-SECRET-OWNED-v1"
$ownershipMarkerName = ".omni-cio-wp7-owned"
$statePath = Join-Path $bootstrapRoot "wp7-bootstrap-state.json"
$serviceDefinitionsPath = Join-Path $servicesRoot "wp7-service-definitions.json"
$runtimeName = "omni-cio-runtime"
$executionName = "omni-cio-execution"

$expectedPaths = @{
    root = $expectedRoot
    bootstrap_state = $bootstrapRoot
    runtime = $runtimeRoot
    data = $dataRoot
    logs = $logsRoot
    services = $servicesRoot
    secret_root_owned_by_wp8 = $secretRoot
    runner_root_external = $runnerRoot
}
foreach ($key in $expectedPaths.Keys) {
    if ([string]$contract.paths.$key -ne $expectedPaths[$key]) {
        throw "WP7 path contract mismatch for '$key'."
    }
}

$pythonVersion = [string]$toolchain.backend.python
$nodeVersion = [string]$toolchain.frontend.node
$npmVersion = [string]$toolchain.frontend.npm
$postgresMajor = [int]$toolchain.database.postgresql_major
$postgresVersion = [string]$toolchain.database.tested_patch

if ($pythonVersion -ne [string]$contract.toolchain.python.runtime_version) {
    throw "WP7 Python target does not match the selected V10 toolchain."
}
if ($nodeVersion -ne [string]$contract.toolchain.node.runtime_version) {
    throw "WP7 Node target does not match the selected V10 toolchain."
}
if ($npmVersion -ne [string]$contract.toolchain.npm.runtime_version) {
    throw "WP7 npm target does not match the selected V10 toolchain."
}
if ($postgresMajor -ne [int]$contract.toolchain.postgresql.major) {
    throw "WP7 PostgreSQL major does not match the selected V10 toolchain."
}
if ($postgresVersion -ne [string]$contract.toolchain.postgresql.runtime_version) {
    throw "WP7 PostgreSQL patch does not match the selected V10 toolchain."
}

$plannedServices = @(
    foreach ($definition in @($contract.service_definitions)) {
        [ordered]@{
            id = [string]$definition.id
            windows_service_name = [string]$definition.windows_service_name
            identity_role = [string]$definition.identity_role
            activation = [string]$definition.activation
        }
    }
)

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
    param([string]$Name)

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

function Get-RunnerHealth {
    if ($env:OS -ne "Windows_NT") {
        return [ordered]@{
            healthy = $false
            error_code = "RUNNER_SERVICE_WINDOWS_REQUIRED"
        }
    }
    if (-not (Test-Path -LiteralPath $runnerChecker -PathType Leaf)) {
        return [ordered]@{
            healthy = $false
            error_code = "RUNNER_CHECKER_MISSING"
        }
    }

    $raw = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
        -File $runnerChecker `
        -RunnerRoot $runnerRoot `
        -ExpectedRunnerName ([string]$contract.runner.expected_name) `
        -AsJson 2>$null
    try {
        $parsed = $raw | Out-String | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        return [ordered]@{
            healthy = $false
            error_code = "RUNNER_CHECKER_OUTPUT_INVALID"
        }
    }
    return [ordered]@{
        healthy = [bool]$parsed.healthy
        error_code = if ($parsed.error_code) { [string]$parsed.error_code } else { $null }
    }
}

function Invoke-VersionCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    try {
        $output = & $FilePath @Arguments 2>$null | Out-String
        if ($LASTEXITCODE -ne 0) {
            return $null
        }
        return $output.Trim()
    }
    catch {
        return $null
    }
}

function Test-MachineVisiblePath {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $false
    }
    try {
        $full = [System.IO.Path]::GetFullPath($Path)
    }
    catch {
        return $false
    }

    foreach ($privateRoot in @($env:USERPROFILE, $env:LOCALAPPDATA, $env:APPDATA)) {
        if ([string]::IsNullOrWhiteSpace($privateRoot)) {
            continue
        }
        $normalized = [System.IO.Path]::GetFullPath($privateRoot).TrimEnd('\') + '\'
        if ($full.StartsWith($normalized, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $false
        }
    }
    return $true
}

function Get-PythonInfo {
    $version = $null
    $executable = $null

    try {
        $payload = & py.exe -3.14 -c `
            "import json,sys; print(json.dumps({'v':'.'.join(map(str,sys.version_info[:3])),'p':sys.executable}))" `
            2>$null | Out-String
        if ($LASTEXITCODE -eq 0 -and $payload.Trim()) {
            $parsed = $payload.Trim() | ConvertFrom-Json -ErrorAction Stop
            $version = [string]$parsed.v
            $executable = [string]$parsed.p
        }
    }
    catch {
        $version = $null
        $executable = $null
    }

    if (-not $version) {
        $candidate = "C:\Program Files\Python314\python.exe"
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $version = Invoke-VersionCommand -FilePath $candidate -Arguments @(
                "-c",
                "import sys; print('.'.join(map(str, sys.version_info[:3])))"
            )
            $executable = $candidate
        }
    }

    return [ordered]@{
        version = $version
        machine_visible = Test-MachineVisiblePath -Path $executable
    }
}

function Get-NodeInfo {
    $version = Invoke-VersionCommand -FilePath "node.exe" -Arguments @("--version")
    $path = $null
    try {
        $command = Get-Command node.exe -ErrorAction Stop
        $path = [string]$command.Source
    }
    catch {
        $path = $null
    }
    if (-not $version) {
        $candidate = "C:\Program Files\nodejs\node.exe"
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $version = Invoke-VersionCommand -FilePath $candidate -Arguments @("--version")
            $path = $candidate
        }
    }
    if ($version -and $version.StartsWith("v")) {
        $version = $version.Substring(1)
    }
    return [ordered]@{
        version = $version
        machine_visible = Test-MachineVisiblePath -Path $path
    }
}

function Get-NpmInfo {
    $version = Invoke-VersionCommand -FilePath "npm.cmd" -Arguments @("--version")
    $path = $null
    try {
        $command = Get-Command npm.cmd -ErrorAction Stop
        $path = [string]$command.Source
    }
    catch {
        $path = $null
    }
    if (-not $version) {
        $candidate = "C:\Program Files\nodejs\npm.cmd"
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $version = Invoke-VersionCommand -FilePath $candidate -Arguments @("--version")
            $path = $candidate
        }
    }
    return [ordered]@{
        version = $version
        machine_visible = Test-MachineVisiblePath -Path $path
    }
}

function Get-PostgreSqlInfo {
    $version = $null
    $path = $null
    $candidates = @("psql.exe", "C:\Program Files\PostgreSQL\18\bin\psql.exe")
    foreach ($candidate in $candidates) {
        $value = Invoke-VersionCommand -FilePath $candidate -Arguments @("--version")
        if ($value -and $value -match '([0-9]+\.[0-9]+)') {
            $version = $Matches[1]
            if ($candidate -eq "psql.exe") {
                try {
                    $command = Get-Command psql.exe -ErrorAction Stop
                    $path = [string]$command.Source
                }
                catch {
                    $path = $null
                }
            }
            else {
                $path = $candidate
            }
            break
        }
    }
    return [ordered]@{
        version = $version
        machine_visible = Test-MachineVisiblePath -Path $path
    }
}

function Get-PrerequisiteState {
    param(
        [string]$Expected,
        [string]$Actual,
        [bool]$MachineVisible
    )

    if ([string]::IsNullOrWhiteSpace($Actual)) {
        return "MISSING"
    }
    if (-not [string]::Equals($Expected, $Actual, [System.StringComparison]::Ordinal)) {
        return "MISMATCH"
    }
    if (-not $MachineVisible) {
        return "NOT_MACHINE_VISIBLE"
    }
    return "MATCH"
}

function Get-Prerequisites {
    if ($env:OS -ne "Windows_NT") {
        return [ordered]@{
            python = [ordered]@{ expected = $pythonVersion; actual = $null; state = "UNAVAILABLE"; machine_visible = $false }
            node = [ordered]@{ expected = $nodeVersion; actual = $null; state = "UNAVAILABLE"; machine_visible = $false }
            npm = [ordered]@{ expected = $npmVersion; actual = $null; state = "UNAVAILABLE"; machine_visible = $false }
            postgresql = [ordered]@{ expected = $postgresVersion; actual = $null; state = "UNAVAILABLE"; machine_visible = $false }
        }
    }

    $python = Get-PythonInfo
    $node = Get-NodeInfo
    $npm = Get-NpmInfo
    $postgres = Get-PostgreSqlInfo

    return [ordered]@{
        python = [ordered]@{
            expected = $pythonVersion
            actual = $python.version
            machine_visible = [bool]$python.machine_visible
            state = Get-PrerequisiteState -Expected $pythonVersion -Actual $python.version -MachineVisible $python.machine_visible
        }
        node = [ordered]@{
            expected = $nodeVersion
            actual = $node.version
            machine_visible = [bool]$node.machine_visible
            state = Get-PrerequisiteState -Expected $nodeVersion -Actual $node.version -MachineVisible $node.machine_visible
        }
        npm = [ordered]@{
            expected = $npmVersion
            actual = $npm.version
            machine_visible = [bool]$npm.machine_visible
            state = Get-PrerequisiteState -Expected $npmVersion -Actual $npm.version -MachineVisible $npm.machine_visible
        }
        postgresql = [ordered]@{
            expected = $postgresVersion
            actual = $postgres.version
            machine_visible = [bool]$postgres.machine_visible
            state = Get-PrerequisiteState -Expected $postgresVersion -Actual $postgres.version -MachineVisible $postgres.machine_visible
        }
    }
}

function Install-ExactWingetPackage {
    param(
        [string]$Id,
        [string]$Version,
        [switch]$Interactive
    )

    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($null -eq $winget) {
        throw "WINGET_NOT_AVAILABLE"
    }

    $arguments = @(
        "install",
        "--id", $Id,
        "--exact",
        "--version", $Version,
        "--source", "winget",
        "--scope", "machine",
        "--accept-package-agreements",
        "--accept-source-agreements"
    )
    if ($Interactive) {
        $arguments += "--interactive"
    }
    else {
        $arguments += "--silent"
    }

    Write-Host "Installing reviewed public prerequisite: $Id $Version"
    if ($Id -eq "PostgreSQL.PostgreSQL.18") {
        Write-Host (
            "If the official PostgreSQL installer requests a local database password, " +
            "enter it only in the installer UI. Do not type or paste it into PowerShell."
        ) -ForegroundColor Yellow
    }
    & $winget.Source @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "WINGET_INSTALL_FAILED:$Id"
    }
}

function Install-MissingPrerequisites {
    param([System.Collections.IDictionary]$Before)

    foreach ($name in @("python", "node", "npm", "postgresql")) {
        if ($Before[$name].state -eq "MISMATCH") {
            throw "PREREQUISITE_VERSION_MISMATCH:$name"
        }
        if ($Before[$name].state -eq "NOT_MACHINE_VISIBLE") {
            throw "PREREQUISITE_NOT_MACHINE_VISIBLE:$name"
        }
    }

    if ($Before.python.state -eq "MISSING") {
        Install-ExactWingetPackage `
            -Id ([string]$contract.toolchain.python.winget_id) `
            -Version ([string]$contract.toolchain.python.winget_version)
    }
    if ($Before.node.state -eq "MISSING") {
        Install-ExactWingetPackage `
            -Id ([string]$contract.toolchain.node.winget_id) `
            -Version ([string]$contract.toolchain.node.winget_version)
    }
    if ($Before.postgresql.state -eq "MISSING") {
        Install-ExactWingetPackage `
            -Id ([string]$contract.toolchain.postgresql.winget_id) `
            -Version ([string]$contract.toolchain.postgresql.winget_version) `
            -Interactive
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

function Set-OwnerOnlyDirectoryAcl {
    param([string]$Path)

    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor `
        [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-AllowRule -Identity $systemSid -Rights FullControl -Inheritance $inherit))
    $acl.AddAccessRule((New-AllowRule -Identity $adminsSid -Rights FullControl -Inheritance $inherit))
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Set-RuntimeDirectoryAcl {
    param(
        [string]$Path,
        [System.Security.Principal.SecurityIdentifier]$RuntimeSid
    )

    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor `
        [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-AllowRule -Identity $systemSid -Rights FullControl -Inheritance $inherit))
    $acl.AddAccessRule((New-AllowRule -Identity $adminsSid -Rights FullControl -Inheritance $inherit))
    $acl.AddAccessRule((New-AllowRule -Identity $RuntimeSid -Rights Modify -Inheritance $inherit))
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Test-OwnedDirectory {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return $false
    }
    $marker = Join-Path $Path $ownershipMarkerName
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
        return $false
    }
    try {
        return (Get-Content -LiteralPath $marker -Raw -ErrorAction Stop).Trim() -eq $ownershipMarker
    }
    catch {
        return $false
    }
}

function Ensure-OwnedDirectory {
    param(
        [string]$Path,
        [ValidateSet("OWNER_ONLY", "RUNTIME")]
        [string]$AclClass,
        [System.Security.Principal.SecurityIdentifier]$RuntimeSid
    )

    $changed = $false
    if (Test-Path -LiteralPath $Path) {
        if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
            throw "WP7 expected directory path is occupied by a non-directory."
        }
        if (-not (Test-OwnedDirectory -Path $Path)) {
            throw "WP7 refuses to adopt a pre-existing unmarked directory."
        }
    }
    else {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
        $marker = Join-Path $Path $ownershipMarkerName
        Set-Content -LiteralPath $marker -Value $ownershipMarker -Encoding ASCII -NoNewline
        $changed = $true
    }

    if ($AclClass -eq "OWNER_ONLY") {
        Set-OwnerOnlyDirectoryAcl -Path $Path
    }
    else {
        Set-RuntimeDirectoryAcl -Path $Path -RuntimeSid $RuntimeSid
    }
    return $changed
}

function Get-ServiceDefinitionsJson {
    return ([ordered]@{
        schema_version = "1"
        status = "DEFINITIONS_ONLY_FUTURE_ACTIVATION"
        services = $plannedServices
    } | ConvertTo-Json -Depth 6)
}

function Ensure-ExactFile {
    param(
        [string]$Path,
        [string]$ExpectedContent
    )

    if (Test-Path -LiteralPath $Path) {
        $existing = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
        if ($existing.Trim() -ne $ExpectedContent.Trim()) {
            throw "WP7 refuses to overwrite unexpected owned-file content."
        }
        return $false
    }
    Set-Content -LiteralPath $Path -Value $ExpectedContent -Encoding UTF8
    return $true
}

function Get-ExistingInstalledPackages {
    if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
        return @()
    }
    if (-not (Test-OwnedDirectory -Path $bootstrapRoot)) {
        throw "WP7 refuses to read bootstrap state from an unowned directory."
    }
    try {
        $state = Get-Content -LiteralPath $statePath -Raw -ErrorAction Stop |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "Existing WP7 bootstrap state is invalid."
    }
    if (
        [string]$state.schema_version -ne "1" -or
        [string]$state.ownership -ne $ownershipMarker
    ) {
        throw "Existing WP7 bootstrap state ownership/schema mismatch."
    }
    return @($state.installed_by_wp7 | ForEach-Object { [string]$_ })
}

function Get-BootstrapStateJson {
    param([string[]]$InstalledPackages)

    return ([ordered]@{
        schema_version = "1"
        ownership = $ownershipMarker
        toolchain = [ordered]@{
            python = $pythonVersion
            node = $nodeVersion
            npm = $npmVersion
            postgresql = $postgresVersion
        }
        installed_by_wp7 = @($InstalledPackages | Sort-Object -Unique)
        secret_values_present = $false
        future_services_activated = $false
    } | ConvertTo-Json -Depth 6)
}

function Ensure-Wp7State {
    param(
        [System.Security.Principal.SecurityIdentifier]$RuntimeSid,
        [string[]]$InstalledPackages
    )

    $changes = 0
    foreach ($spec in @(
        @($bootstrapRoot, "OWNER_ONLY"),
        @($runtimeRoot, "RUNTIME"),
        @($dataRoot, "RUNTIME"),
        @($logsRoot, "RUNTIME"),
        @($servicesRoot, "OWNER_ONLY")
    )) {
        if (Ensure-OwnedDirectory -Path $spec[0] -AclClass $spec[1] -RuntimeSid $RuntimeSid) {
            $changes += 1
        }
    }

    if (Ensure-ExactFile -Path $serviceDefinitionsPath -ExpectedContent (Get-ServiceDefinitionsJson)) {
        $changes += 1
    }
    if (Ensure-ExactFile `
        -Path $statePath `
        -ExpectedContent (Get-BootstrapStateJson -InstalledPackages $InstalledPackages)
    ) {
        $changes += 1
    }
    return $changes
}

function Test-ServiceDefinitionsReady {
    if (-not (Test-OwnedDirectory -Path $servicesRoot)) {
        return $false
    }
    if (-not (Test-Path -LiteralPath $serviceDefinitionsPath -PathType Leaf)) {
        return $false
    }
    try {
        $expected = Get-ServiceDefinitionsJson
        $actual = Get-Content -LiteralPath $serviceDefinitionsPath -Raw -ErrorAction Stop
        return $actual.Trim() -eq $expected.Trim()
    }
    catch {
        return $false
    }
}

function Test-BootstrapStateReady {
    if (-not (Test-OwnedDirectory -Path $bootstrapRoot)) {
        return $false
    }
    if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
        return $false
    }
    try {
        $state = Get-Content -LiteralPath $statePath -Raw -ErrorAction Stop |
            ConvertFrom-Json -ErrorAction Stop
        return (
            [string]$state.schema_version -eq "1" -and
            [string]$state.ownership -eq $ownershipMarker -and
            [string]$state.toolchain.python -eq $pythonVersion -and
            [string]$state.toolchain.node -eq $nodeVersion -and
            [string]$state.toolchain.npm -eq $npmVersion -and
            [string]$state.toolchain.postgresql -eq $postgresVersion -and
            $state.secret_values_present -eq $false -and
            $state.future_services_activated -eq $false
        )
    }
    catch {
        return $false
    }
}

function Test-FutureServicesInactive {
    if ($env:OS -ne "Windows_NT") {
        return $true
    }
    foreach ($definition in $plannedServices) {
        $service = Get-Service -Name $definition.windows_service_name -ErrorAction SilentlyContinue
        if ($null -ne $service) {
            return $false
        }
    }
    return $true
}

function Get-Profile {
    param(
        [string]$Mode,
        [bool]$IdempotenceVerified
    )

    $prerequisites = Get-Prerequisites
    $runtimeState = Get-LocalRoleState -Name $runtimeName
    $executionState = Get-LocalRoleState -Name $executionName
    $runner = Get-RunnerHealth

    $rolesValid = (
        $runtimeState.present -eq $true -and
        $runtimeState.enabled -eq $false -and
        $runtimeState.administrator -eq $false -and
        $executionState.present -eq $true -and
        $executionState.enabled -eq $false -and
        $executionState.administrator -eq $false
    )

    $ownedDirectoriesReady = (
        (Test-OwnedDirectory -Path $bootstrapRoot) -and
        (Test-OwnedDirectory -Path $runtimeRoot) -and
        (Test-OwnedDirectory -Path $dataRoot) -and
        (Test-OwnedDirectory -Path $logsRoot) -and
        (Test-OwnedDirectory -Path $servicesRoot)
    )
    $serviceDefinitionsReady = Test-ServiceDefinitionsReady
    $bootstrapStateReady = Test-BootstrapStateReady
    $futureServicesInactive = Test-FutureServicesInactive
    $prerequisitesExact = [bool](
        @($prerequisites.Values | Where-Object { $_.state -ne "MATCH" }).Count -eq 0
    )

    $reasons = @()
    if ($env:OS -ne "Windows_NT") { $reasons += "WINDOWS_REQUIRED" }
    if (-not $prerequisitesExact) { $reasons += "PREREQUISITES_NOT_EXACT" }
    if (-not $runner.healthy) { $reasons += "RUNNER_NOT_HEALTHY" }
    if (-not $rolesValid) { $reasons += "WP6_ROLES_NOT_VALID" }
    if (-not $ownedDirectoriesReady) { $reasons += "WP7_DIRECTORIES_NOT_READY" }
    if (-not $serviceDefinitionsReady) { $reasons += "SERVICE_DEFINITIONS_NOT_READY" }
    if (-not $bootstrapStateReady) { $reasons += "BOOTSTRAP_STATE_NOT_READY" }
    if (-not $futureServicesInactive) { $reasons += "FUTURE_SERVICE_ACTIVATED_EARLY" }
    if ($Mode -eq "APPLY" -and -not $IdempotenceVerified) {
        $reasons += "IDEMPOTENCE_NOT_PROVEN"
    }

    $status = if ($reasons.Count -eq 0) {
        "PASS"
    }
    elseif ($Mode -eq "PREVIEW") {
        "OWNER_ACTION_REQUIRED"
    }
    else {
        "FAIL"
    }

    return [ordered]@{
        schema_version = "1"
        mode = $Mode
        status = $status
        reasons = $reasons
        prerequisites = $prerequisites
        runner = [ordered]@{
            healthy = [bool]$runner.healthy
            error_code = $runner.error_code
        }
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
        bootstrap = [ordered]@{
            owned_directories_ready = $ownedDirectoriesReady
            service_definitions_ready = $serviceDefinitionsReady
            state_ready = $bootstrapStateReady
            future_services_inactive = $futureServicesInactive
            idempotence_verified = $IdempotenceVerified
        }
        privacy = [ordered]@{
            raw_usernames_collected = $false
            sids_emitted = $false
            hostnames_collected = $false
            addresses_collected = $false
            secret_values_collected = $false
            runner_credentials_collected = $false
            private_data_collected = $false
        }
    }
}

function Write-Profile {
    param([System.Collections.IDictionary]$Profile)

    if ($AsJson) {
        $Profile | ConvertTo-Json -Depth 10 -Compress
        return
    }

    Write-Host "WP7 bootstrap mode: $($Profile.mode)"
    Write-Host "WP7 bootstrap status: $($Profile.status)" -ForegroundColor $(
        if ($Profile.status -eq "PASS") { "Green" }
        elseif ($Profile.status -eq "OWNER_ACTION_REQUIRED") { "Yellow" }
        else { "Red" }
    )
    foreach ($name in @("python", "node", "npm", "postgresql")) {
        $item = $Profile.prerequisites[$name]
        Write-Host "Prerequisite $name: $($item.state) (expected $($item.expected))"
    }
    Write-Host "Runner healthy: $($Profile.runner.healthy)"
    Write-Host "WP7 directories ready: $($Profile.bootstrap.owned_directories_ready)"
    Write-Host "WP7 service definitions ready: $($Profile.bootstrap.service_definitions_ready)"
    Write-Host "Future services inactive: $($Profile.bootstrap.future_services_inactive)"
    Write-Host "Idempotence verified: $($Profile.bootstrap.idempotence_verified)"
    if ($Profile.reasons.Count -gt 0) {
        Write-Host "Reason codes: $($Profile.reasons -join ', ')"
    }
    Write-Host "Real secret values used: NO"
}

if (-not $Apply -and -not $Verify) {
    $profile = Get-Profile -Mode "PREVIEW" -IdempotenceVerified $false
    Write-Profile -Profile $profile
    exit 0
}

if ($Verify) {
    $profile = Get-Profile -Mode "VERIFY" -IdempotenceVerified $true
    Write-Profile -Profile $profile
    if ($profile.status -eq "PASS") { exit 0 }
    exit 2
}

if (-not (Test-Administrator)) {
    throw "WP7 bootstrap -Apply requires an elevated OWNER-admin PowerShell."
}
if (-not (Test-Path -LiteralPath $expectedRoot -PathType Container)) {
    throw "WP7 requires the accepted WP6 Omni-CIO root before mutation."
}

$runnerBefore = Get-RunnerHealth
if (-not $runnerBefore.healthy) {
    throw "RUNNER_NOT_HEALTHY:$($runnerBefore.error_code)"
}
$runtimeBefore = Get-LocalRoleState -Name $runtimeName
$executionBefore = Get-LocalRoleState -Name $executionName
foreach ($roleSpec in @(
    @("runtime", $runtimeBefore),
    @("execution", $executionBefore)
)) {
    $state = $roleSpec[1]
    if (
        $state.present -ne $true -or
        $state.enabled -ne $false -or
        $state.administrator -ne $false
    ) {
        throw "WP6_ROLE_NOT_READY:$($roleSpec[0])"
    }
}

$prerequisitesBefore = Get-Prerequisites
$installedThisRun = @()
if ($InstallPrerequisites) {
    if ($prerequisitesBefore.python.state -eq "MISSING") {
        $installedThisRun += "Python.Python.3.14@$([string]$contract.toolchain.python.winget_version)"
    }
    if ($prerequisitesBefore.node.state -eq "MISSING") {
        $installedThisRun += "OpenJS.NodeJS.LTS@$([string]$contract.toolchain.node.winget_version)"
    }
    if ($prerequisitesBefore.postgresql.state -eq "MISSING") {
        $installedThisRun += "PostgreSQL.PostgreSQL.18@$([string]$contract.toolchain.postgresql.winget_version)"
    }
    Install-MissingPrerequisites -Before $prerequisitesBefore
}

$prerequisitesAfterInstall = Get-Prerequisites
$notExact = @(
    $prerequisitesAfterInstall.GetEnumerator() |
        Where-Object { $_.Value.state -ne "MATCH" } |
        ForEach-Object { $_.Key }
)
if ($notExact.Count -gt 0) {
    Write-Host (
        "WP7 bootstrap requires exact machine-visible prerequisites before filesystem mutation: " +
        ($notExact -join ", ")
    ) -ForegroundColor Yellow
    exit 3
}

$existingInstalled = @(Get-ExistingInstalledPackages)
$installedByWp7 = @($existingInstalled + $installedThisRun | Sort-Object -Unique)

$firstPassChanges = Ensure-Wp7State `
    -RuntimeSid $runtimeBefore.sid `
    -InstalledPackages $installedByWp7
$secondPassChanges = Ensure-Wp7State `
    -RuntimeSid $runtimeBefore.sid `
    -InstalledPackages $installedByWp7
$idempotenceVerified = ($secondPassChanges -eq 0)
if (-not $idempotenceVerified) {
    throw "WP7 bootstrap second pass was not idempotent."
}

Write-Host "WP7 bootstrap first-pass structural changes: $firstPassChanges"
Write-Host "WP7 bootstrap second-pass structural changes: $secondPassChanges"

$profile = Get-Profile -Mode "APPLY" -IdempotenceVerified $idempotenceVerified
Write-Profile -Profile $profile
if ($profile.status -eq "PASS") {
    exit 0
}
exit 2
