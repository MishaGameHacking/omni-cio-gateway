[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedImplementationSha,
    [switch]$Apply,
    [switch]$Verify,
    [switch]$Cleanup,
    [switch]$AsJson,
    [ValidateRange(1024, 65535)][int]$Port = 8765
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$modeCount = @($Apply, $Verify, $Cleanup | Where-Object { $_ }).Count
if ($modeCount -gt 1) { throw "Choose only one of -Apply, -Verify, or -Cleanup." }
if (($Apply -or $Verify -or $Cleanup) -and $env:OS -ne "Windows_NT") {
    throw "WP15 live Web acceptance provisioning requires Windows."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$contractPath = Join-Path $repoRoot "docs\architecture\V10_WP15_LIVE_WEB_ACCEPTANCE_CONTRACT.json"
$launcherRelative = "infrastructure\windows\run_wp15_live_web_runtime.ps1"
$bootstrapDbRelative = "infrastructure\windows\bootstrap_wp15_live_database.py"
$wp17VaultProvisioner = Join-Path $repoRoot "infrastructure\windows\provision_wp17_web_read_vault.ps1"
$runtimeName = "omni-cio-runtime"
$runtimeOwnershipMarker = "Omni-CIO V10 WP6 runtime role anchor"
$taskName = "OmniCIO.V10.WP15LiveAcceptance"
$runtimeRoot = "C:\ProgramData\OmniCIO\runtime\wp15-live"
$runtimeMarker = Join-Path $runtimeRoot ".omni-cio-wp15-live-owned"
$runtimeMarkerValue = "OMNI-CIO-V10-WP15-LIVE-RUNTIME-v1"
$appRoot = Join-Path $runtimeRoot "app"
$deploymentMarker = Join-Path $appRoot ".omni-cio-wp15-live-deployment"
$venvRoot = Join-Path $runtimeRoot "venv"
$pendingRoot = Join-Path $runtimeRoot "pending"
$pendingMarker = Join-Path $pendingRoot ".omni-cio-wp15-live-pending"
$pendingMarkerValue = "OMNI-CIO-V10-WP15-LIVE-PENDING-v1"
$pendingEvidencePath = Join-Path $pendingRoot "owner-confirmation.json"
$backupRoot = Join-Path $runtimeRoot "postgres-backup"
$backupMarker = Join-Path $backupRoot ".omni-cio-wp15-live-postgres-backup"
$backupMarkerValue = "OMNI-CIO-V10-WP15-LIVE-POSTGRES-BACKUP-v1"
$hbaBackup = Join-Path $backupRoot "pg_hba.conf.pre-wp15-live"
$identBackup = Join-Path $backupRoot "pg_ident.conf.pre-wp15-live"
$pythonMachine = "C:\Program Files\Python314\python.exe"
$nodeExe = "C:\Program Files\nodejs\node.exe"
$npmCmd = "C:\Program Files\nodejs\npm.cmd"
$psqlExe = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
$pgCtlExe = "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe"
$managedBegin = "# BEGIN OMNI-CIO V10 WP15 LIVE ACCEPTANCE"
$managedEnd = "# END OMNI-CIO V10 WP15 LIVE ACCEPTANCE"
$runnerRoot = "C:\actions-runner"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Resolve-IdentitySid {
    param([Parameter(Mandatory = $true)][System.Security.Principal.IdentityReference]$IdentityReference)
    if ($IdentityReference -is [System.Security.Principal.SecurityIdentifier]) {
        return [System.Security.Principal.SecurityIdentifier]$IdentityReference
    }
    try {
        return $IdentityReference.Translate([System.Security.Principal.SecurityIdentifier])
    }
    catch [System.Security.Principal.IdentityNotMappedException] {
        return $null
    }
}

function Get-RunnerSid {
    $services = @(
        Get-CimInstance Win32_Service -ErrorAction Stop |
            Where-Object {
                $pathName = [string]$_.PathName
                $_.Name -match '^actions\.runner\.' -and
                -not [string]::IsNullOrWhiteSpace($pathName) -and
                $pathName.IndexOf($runnerRoot, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
            }
    )
    if ($services.Count -ne 1) { throw "RUNNER_SERVICE_IDENTITY_UNAVAILABLE" }
    $account = [System.Security.Principal.NTAccount]::new([string]$services[0].StartName)
    return $account.Translate([System.Security.Principal.SecurityIdentifier])
}

function Get-RuntimeUser {
    $user = Get-LocalUser -Name $runtimeName -ErrorAction Stop
    if ([string]$user.Description -ne $runtimeOwnershipMarker) {
        throw "WP15_LIVE_RUNTIME_ROLE_OWNERSHIP_INVALID"
    }
    $admins = @(
        Get-LocalGroupMember -Group "Administrators" -ErrorAction Stop |
            ForEach-Object {
                try { Resolve-IdentitySid -IdentityReference $_.SID } catch { $null }
            } |
            Where-Object { $null -ne $_ }
    )
    if ($admins.Value -contains $user.SID.Value) { throw "WP15_LIVE_RUNTIME_IS_ADMINISTRATOR" }
    return $user
}

function Get-ReviewedHead {
    $expected = $ExpectedImplementationSha.Trim().ToLowerInvariant()
    if ($expected -notmatch '^[0-9a-f]{40}$') { throw "WP15_LIVE_EXPECTED_SHA_INVALID" }
    $head = @(& git -C $repoRoot rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1) { throw "WP15_LIVE_GIT_HEAD_UNAVAILABLE" }
    $actual = ([string]$head[0]).Trim().ToLowerInvariant()
    if ($actual -ne $expected) { throw "WP15_LIVE_GIT_HEAD_MISMATCH" }
    $dirty = @(& git -C $repoRoot status --porcelain 2>$null)
    if ($LASTEXITCODE -ne 0) { throw "WP15_LIVE_GIT_STATUS_UNAVAILABLE" }
    if ($dirty.Count -ne 0) { throw "WP15_LIVE_WORKTREE_NOT_CLEAN" }
    return $actual
}

function New-Rule {
    param(
        [Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$Sid,
        [Parameter(Mandatory = $true)][System.Security.AccessControl.FileSystemRights]$Rights,
        [System.Security.AccessControl.InheritanceFlags]$Inheritance = [System.Security.AccessControl.InheritanceFlags]::None
    )
    return [System.Security.AccessControl.FileSystemAccessRule]::new(
        $Sid,
        $Rights,
        $Inheritance,
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
}

function Set-ProtectedDirectoryAcl {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$RuntimeSid,
        [Parameter(Mandatory = $true)][System.Security.AccessControl.FileSystemRights]$RuntimeRights,
        [switch]$IncludeRuntime
    )
    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-Rule -Sid $systemSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) -Inheritance $inherit))
    $acl.AddAccessRule((New-Rule -Sid $adminsSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) -Inheritance $inherit))
    if ($IncludeRuntime) {
        $acl.AddAccessRule((New-Rule -Sid $RuntimeSid -Rights $RuntimeRights -Inheritance $inherit))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl -ErrorAction Stop
}

function Test-DirectoryAcl {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$RuntimeSid,
        [Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$RunnerSid,
        [Parameter(Mandatory = $true)][bool]$RuntimeWriteExpected
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return [ordered]@{ present = $false; protected = $false; runtime_read = $false; runtime_write = $false; runner_read = $true; runner_write = $true; broad = $true }
    }
    $acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
    $rules = @($acl.Access)
    $runtimeRules = @($rules | Where-Object {
        $sid = Resolve-IdentitySid -IdentityReference $_.IdentityReference
        $null -ne $sid -and $sid.Value -eq $RuntimeSid.Value -and $_.AccessControlType -eq 'Allow'
    })
    $runnerRules = @($rules | Where-Object {
        $sid = Resolve-IdentitySid -IdentityReference $_.IdentityReference
        $null -ne $sid -and $sid.Value -eq $RunnerSid.Value -and $_.AccessControlType -eq 'Allow'
    })
    $broadSidValues = @("S-1-1-0", "S-1-5-11", "S-1-5-32-545")
    $broad = @($rules | Where-Object {
        $sid = Resolve-IdentitySid -IdentityReference $_.IdentityReference
        $name = [string]$_.IdentityReference
        ($null -ne $sid -and $broadSidValues -contains $sid.Value) -or $name -match '(?i)Everyone|Authenticated Users|\\Users$'
    })
    $runtimeRead = [bool]($runtimeRules | Where-Object { ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::ReadData) -ne 0 })
    $runtimeWrite = [bool]($runtimeRules | Where-Object { ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::WriteData) -ne 0 })
    $runnerRead = [bool]($runnerRules | Where-Object { ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::ReadData) -ne 0 })
    $runnerWrite = [bool]($runnerRules | Where-Object { ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::WriteData) -ne 0 -or ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::Delete) -ne 0 })
    return [ordered]@{
        present = $true
        protected = [bool]$acl.AreAccessRulesProtected
        runtime_read = $runtimeRead
        runtime_write = $runtimeWrite
        runtime_write_expected = $RuntimeWriteExpected
        runner_read = $runnerRead
        runner_write = $runnerWrite
        broad = ($broad.Count -gt 0)
    }
}

function Get-PostgresDataRoot {
    $services = @(
        Get-CimInstance Win32_Service -ErrorAction Stop |
            Where-Object { $_.Name -match '(?i)postgres' -and [string]$_.PathName -match '(?i)\s-D\s+' }
    )
    $candidates = @()
    foreach ($service in $services) {
        $pathName = [string]$service.PathName
        $match = [regex]::Match($pathName, '(?i)(?:^|\s)-D\s+(?:"([^"]+)"|(\S+))')
        if ($match.Success) {
            $candidate = if (-not [string]::IsNullOrWhiteSpace($match.Groups[1].Value)) { $match.Groups[1].Value } else { $match.Groups[2].Value }
            if (Test-Path -LiteralPath (Join-Path $candidate "PG_VERSION") -PathType Leaf) {
                $major = (Get-Content -LiteralPath (Join-Path $candidate "PG_VERSION") -Raw).Trim()
                if ($major -eq "18") { $candidates += $candidate }
            }
        }
    }
    $unique = @($candidates | Select-Object -Unique)
    if ($unique.Count -ne 1) { throw "WP15_LIVE_POSTGRES18_DATA_ROOT_UNAVAILABLE" }
    return [string]$unique[0]
}

function Quote-PgField {
    param([Parameter(Mandatory = $true)][string]$Value)
    return '"' + $Value.Replace('"', '""') + '"'
}

function Convert-NtAccountToSspiPrincipal {
    param([Parameter(Mandatory = $true)][string]$Value)
    $separator = $Value.IndexOf('\')
    if ($separator -lt 1 -or $separator -ge ($Value.Length - 1)) {
        throw "WP15_LIVE_SSPI_ACCOUNT_NAME_INVALID"
    }
    $realm = $Value.Substring(0, $separator).Trim()
    $user = $Value.Substring($separator + 1).Trim()
    if ([string]::IsNullOrWhiteSpace($realm) -or [string]::IsNullOrWhiteSpace($user)) {
        throw "WP15_LIVE_SSPI_ACCOUNT_NAME_INVALID"
    }
    return $user + "@" + $realm
}

function Remove-ManagedBlock {
    param([Parameter(Mandatory = $true)][string]$Text)
    $pattern = '(?ms)^' + [regex]::Escape($managedBegin) + '.*?^' + [regex]::Escape($managedEnd) + '\r?\n?'
    return [regex]::Replace($Text, $pattern, '')
}

function Set-ManagedConfigBlock {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string[]]$Lines
    )
    $original = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
    $clean = Remove-ManagedBlock -Text $original
    $block = @($managedBegin) + $Lines + @($managedEnd)
    $text = ($block -join "`r`n") + "`r`n" + $clean.TrimStart("`r", "`n")
    [System.IO.File]::WriteAllText($Path, $text, [System.Text.UTF8Encoding]::new($false))
}

function Reload-Postgres {
    param([Parameter(Mandatory = $true)][string]$DataRoot)
    & $pgCtlExe reload -D $DataRoot -s *> $null
    if ($LASTEXITCODE -ne 0) { throw "WP15_LIVE_POSTGRES_RELOAD_FAILED" }
}

function Invoke-PsqlText {
    param(
        [Parameter(Mandatory = $true)][string]$Database,
        [Parameter(Mandatory = $true)][string]$Sql
    )
    $sqlPath = Join-Path $env:TEMP ("omni-cio-wp15-live-" + [guid]::NewGuid().ToString("N") + ".sql")
    try {
        [System.IO.File]::WriteAllText($sqlPath, $Sql, [System.Text.UTF8Encoding]::new($false))
        $previousRequireAuth = $env:PGREQUIREAUTH
        $env:PGREQUIREAUTH = "sspi"
        try {
            & $psqlExe -X -q -v ON_ERROR_STOP=1 -h 127.0.0.1 -U postgres -d $Database -f $sqlPath *> $null
            if ($LASTEXITCODE -ne 0) { throw "WP15_LIVE_POSTGRES_ADMIN_SQL_FAILED" }
        }
        finally {
            $env:PGREQUIREAUTH = $previousRequireAuth
        }
    }
    finally {
        Remove-Item -LiteralPath $sqlPath -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-MigrationsAsOwnerSspi {
    param([Parameter(Mandatory = $true)][string]$PythonPath)
    $previous = @{
        PGHOST = $env:PGHOST; PGPORT = $env:PGPORT; PGDATABASE = $env:PGDATABASE;
        PGUSER = $env:PGUSER; PGREQUIREAUTH = $env:PGREQUIREAUTH; PYTHONDONTWRITEBYTECODE = $env:PYTHONDONTWRITEBYTECODE
    }
    $env:PGHOST = "127.0.0.1"
    $env:PGPORT = "5432"
    $env:PGDATABASE = "omni_cio_v10"
    $env:PGUSER = "postgres"
    $env:PGREQUIREAUTH = "sspi"
    $env:PYTHONDONTWRITEBYTECODE = "1"
    Push-Location -LiteralPath $appRoot
    try {
        & $PythonPath (Join-Path $appRoot $bootstrapDbRelative) *> $null
        if ($LASTEXITCODE -ne 0) { throw "WP15_LIVE_DATABASE_MIGRATION_FAILED" }
    }
    finally {
        Pop-Location
        foreach ($name in $previous.Keys) { Set-Item -Path ("Env:" + $name) -Value $previous[$name] -ErrorAction SilentlyContinue }
    }
}

function New-RandomRuntimePassword {
    $bytes = New-Object byte[] 36
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
        return ([Convert]::ToBase64String($bytes) + "!Aa1")
    }
    finally {
        $rng.Dispose()
        [Array]::Clear($bytes, 0, $bytes.Length)
    }
}

function Stop-And-RemoveTask {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($null -ne $task) {
        try { Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue } catch { }
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction Stop
    }
}

function Restore-PostgresConfig {
    if (-not (Test-Path -LiteralPath $backupRoot -PathType Container)) { return $false }
    if (-not (Test-Path -LiteralPath $backupMarker -PathType Leaf)) { throw "WP15_LIVE_POSTGRES_BACKUP_UNOWNED" }
    if ((Get-Content -LiteralPath $backupMarker -Raw).Trim() -ne $backupMarkerValue) { throw "WP15_LIVE_POSTGRES_BACKUP_MARKER_MISMATCH" }
    if (-not (Test-Path -LiteralPath $hbaBackup -PathType Leaf) -or -not (Test-Path -LiteralPath $identBackup -PathType Leaf)) {
        throw "WP15_LIVE_POSTGRES_BACKUP_INCOMPLETE"
    }
    $dataRoot = Get-PostgresDataRoot
    Copy-Item -LiteralPath $hbaBackup -Destination (Join-Path $dataRoot "pg_hba.conf") -Force
    Copy-Item -LiteralPath $identBackup -Destination (Join-Path $dataRoot "pg_ident.conf") -Force
    Reload-Postgres -DataRoot $dataRoot
    return $true
}

$implementationSha = if ($Apply -or $Verify -or $Cleanup) { Get-ReviewedHead } else { $ExpectedImplementationSha.Trim().ToLowerInvariant() }
$contract = Get-Content -LiteralPath $contractPath -Raw | ConvertFrom-Json
if ([string]$contract.windows_runtime.principal -ne $runtimeName) { throw "WP15_LIVE_CONTRACT_RUNTIME_MISMATCH" }
if ([string]$contract.windows_runtime.temporary_task -ne $taskName) { throw "WP15_LIVE_CONTRACT_TASK_MISMATCH" }
if ([string]$contract.scope.loopback_bind -ne "127.0.0.1") { throw "WP15_LIVE_CONTRACT_BIND_MISMATCH" }
if ([bool]$contract.invariants.trading_methods -or [bool]$contract.invariants.real_trading_enabled -or [bool]$contract.invariants.broker_write_authority_added) {
    throw "WP15_LIVE_CONTRACT_AUTHORITY_INVALID"
}
if (-not (Test-Path -LiteralPath $wp17VaultProvisioner -PathType Leaf)) { throw "WP17_READ_VAULT_PROVISIONER_MISSING" }

$runtimeUser = if ($env:OS -eq "Windows_NT") { Get-RuntimeUser } else { $null }
$runnerSid = if ($env:OS -eq "Windows_NT") { Get-RunnerSid } else { $null }

if ($Cleanup) {
    if (-not (Test-Administrator)) { throw "WP15 live cleanup requires OWNER administrator." }
    Stop-And-RemoveTask
    if ($null -ne $runtimeUser) { Disable-LocalUser -Name $runtimeName -ErrorAction Stop }
    $postgresRestored = Restore-PostgresConfig
    if (Test-Path -LiteralPath $runtimeRoot -PathType Container) {
        if (-not (Test-Path -LiteralPath $runtimeMarker -PathType Leaf)) { throw "WP15_LIVE_RUNTIME_ROOT_UNOWNED" }
        if ((Get-Content -LiteralPath $runtimeMarker -Raw).Trim() -ne $runtimeMarkerValue) { throw "WP15_LIVE_RUNTIME_MARKER_MISMATCH" }
        Remove-Item -LiteralPath $runtimeRoot -Recurse -Force -ErrorAction Stop
    }
    $result = [ordered]@{
        schema_version = "1"; work_package = "WP15"; evidence_type = "LIVE_WEB_RUNTIME_CLEANUP";
        implementation_sha = $implementationSha; temporary_task_present = $false; runtime_role_enabled = $false;
        postgres_config_restored = [bool]$postgresRestored; pending_private_evidence_removed = $true;
        real_secret_values_logged = $false; broker_write_authority_added = $false; trading_methods = $false;
        gateway_entrypoint = "app:app"; ready = $true
    }
    if ($AsJson) { $result | ConvertTo-Json -Depth 4 } else { $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value } }
    exit 0
}

if ($Apply) {
    if (-not (Test-Administrator)) { throw "WP15 live apply requires OWNER administrator." }
    if ([bool]$runtimeUser.Enabled) { throw "WP15_LIVE_RUNTIME_ROLE_MUST_START_DISABLED" }
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { throw "WP15_LIVE_TASK_ALREADY_EXISTS" }
    if (Test-Path -LiteralPath $runtimeRoot) { throw "WP15_LIVE_RUNTIME_ROOT_ALREADY_EXISTS" }
    if (-not (Test-Path -LiteralPath $pythonMachine -PathType Leaf)) { throw "WP15_LIVE_PYTHON314_MISSING" }
    if (-not (Test-Path -LiteralPath $nodeExe -PathType Leaf) -or -not (Test-Path -LiteralPath $npmCmd -PathType Leaf)) { throw "WP15_LIVE_NODE_TOOLCHAIN_MISSING" }
    if (-not (Test-Path -LiteralPath $psqlExe -PathType Leaf) -or -not (Test-Path -LiteralPath $pgCtlExe -PathType Leaf)) { throw "WP15_LIVE_POSTGRES18_TOOLS_MISSING" }

    $pythonVersion = @(& $pythonMachine -c "import platform; print(platform.python_version())")
    if ($LASTEXITCODE -ne 0 -or ($pythonVersion -join "").Trim() -ne "3.14.6") { throw "WP15_LIVE_PYTHON_VERSION_MISMATCH" }
    $nodeVersion = @(& $nodeExe --version)
    if ($LASTEXITCODE -ne 0 -or ($nodeVersion -join "").Trim() -ne "v24.18.0") { throw "WP15_LIVE_NODE_VERSION_MISMATCH" }
    $npmVersion = @(& $npmCmd --version)
    if ($LASTEXITCODE -ne 0 -or ($npmVersion -join "").Trim() -ne "11.16.0") { throw "WP15_LIVE_NPM_VERSION_MISMATCH" }

    $runtimeSid = $runtimeUser.SID
    New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
    Set-Content -LiteralPath $runtimeMarker -Value $runtimeMarkerValue -Encoding ASCII -NoNewline
    Set-ProtectedDirectoryAcl -Path $runtimeRoot -RuntimeSid $runtimeSid -RuntimeRights ([System.Security.AccessControl.FileSystemRights]::ReadAndExecute) -IncludeRuntime
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    Set-ProtectedDirectoryAcl -Path $backupRoot -RuntimeSid $runtimeSid -RuntimeRights ([System.Security.AccessControl.FileSystemRights]::ReadAndExecute)
    Set-Content -LiteralPath $backupMarker -Value $backupMarkerValue -Encoding ASCII -NoNewline

    $dataRoot = Get-PostgresDataRoot
    $hbaPath = Join-Path $dataRoot "pg_hba.conf"
    $identPath = Join-Path $dataRoot "pg_ident.conf"
    Copy-Item -LiteralPath $hbaPath -Destination $hbaBackup -ErrorAction Stop
    Copy-Item -LiteralPath $identPath -Destination $identBackup -ErrorAction Stop

    $zipPath = Join-Path $env:TEMP ("omni-cio-wp15-live-" + [guid]::NewGuid().ToString("N") + ".zip")
    try {
        & git -C $repoRoot archive --format=zip --output=$zipPath HEAD
        if ($LASTEXITCODE -ne 0) { throw "WP15_LIVE_GIT_ARCHIVE_FAILED" }
        New-Item -ItemType Directory -Path $appRoot -Force | Out-Null
        Expand-Archive -LiteralPath $zipPath -DestinationPath $appRoot -Force
    }
    finally {
        Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue
    }
    Set-Content -LiteralPath $deploymentMarker -Value $implementationSha -Encoding ASCII -NoNewline

    Push-Location -LiteralPath (Join-Path $appRoot "apps\web")
    $previousGitSha = $env:GITHUB_SHA
    $env:GITHUB_SHA = $implementationSha
    try {
        & $npmCmd ci --ignore-scripts --no-audit --no-fund *> $null
        if ($LASTEXITCODE -ne 0) { throw "WP15_LIVE_WEB_NPM_CI_FAILED" }
        & $npmCmd run typecheck *> $null
        if ($LASTEXITCODE -ne 0) { throw "WP15_LIVE_WEB_TYPECHECK_FAILED" }
        & $npmCmd run build *> $null
        if ($LASTEXITCODE -ne 0) { throw "WP15_LIVE_WEB_BUILD_FAILED" }
    }
    finally {
        $env:GITHUB_SHA = $previousGitSha
        Remove-Item -LiteralPath (Join-Path $appRoot "apps\web\node_modules") -Recurse -Force -ErrorAction SilentlyContinue
        Pop-Location
    }

    & $pythonMachine -m venv $venvRoot *> $null
    if ($LASTEXITCODE -ne 0) { throw "WP15_LIVE_VENV_CREATE_FAILED" }
    $venvPython = Join-Path $venvRoot "Scripts\python.exe"
    & $venvPython -m pip install --disable-pip-version-check --require-hashes -r (Join-Path $appRoot "requirements.txt") *> $null
    if ($LASTEXITCODE -ne 0) { throw "WP15_LIVE_DEPENDENCY_INSTALL_FAILED" }

    New-Item -ItemType Directory -Path $pendingRoot -Force | Out-Null
    Set-Content -LiteralPath $pendingMarker -Value $pendingMarkerValue -Encoding ASCII -NoNewline
    Set-ProtectedDirectoryAcl -Path $pendingRoot -RuntimeSid $runtimeSid -RuntimeRights ([System.Security.AccessControl.FileSystemRights]::Modify) -IncludeRuntime
    Set-ProtectedDirectoryAcl -Path $appRoot -RuntimeSid $runtimeSid -RuntimeRights ([System.Security.AccessControl.FileSystemRights]::ReadAndExecute) -IncludeRuntime
    Set-ProtectedDirectoryAcl -Path $venvRoot -RuntimeSid $runtimeSid -RuntimeRights ([System.Security.AccessControl.FileSystemRights]::ReadAndExecute) -IncludeRuntime

    $ownerIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $runtimeAccount = $runtimeSid.Translate([System.Security.Principal.NTAccount]).Value
    $ownerPrincipal = Convert-NtAccountToSspiPrincipal -Value $ownerIdentity
    $runtimePrincipal = Convert-NtAccountToSspiPrincipal -Value $runtimeAccount
    $ownerField = Quote-PgField -Value $ownerPrincipal
    $runtimeField = Quote-PgField -Value $runtimePrincipal
    $sspiOptions = "include_realm=1 compat_realm=1 upn_username=0"
    Set-ManagedConfigBlock -Path $hbaPath -Lines @(
        "host all postgres 127.0.0.1/32 sspi $sspiOptions map=omni_cio_owner_admin_map",
        "host omni_cio_v10 omni_cio_runtime 127.0.0.1/32 sspi $sspiOptions map=omni_cio_runtime_map"
    )
    Set-ManagedConfigBlock -Path $identPath -Lines @(
        "omni_cio_owner_admin_map $ownerField postgres",
        "omni_cio_runtime_map $runtimeField omni_cio_runtime"
    )
    Reload-Postgres -DataRoot $dataRoot

    try {
        Invoke-PsqlText -Database "postgres" -Sql @'
\set ON_ERROR_STOP on
DO $omni$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'omni_cio_runtime') THEN
        CREATE ROLE omni_cio_runtime LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    ELSE
        ALTER ROLE omni_cio_runtime LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
END
$omni$;
SELECT 'CREATE DATABASE omni_cio_v10 WITH OWNER = postgres ENCODING = ''UTF8''' WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'omni_cio_v10') \gexec
REVOKE ALL ON DATABASE omni_cio_v10 FROM PUBLIC;
GRANT CONNECT ON DATABASE omni_cio_v10 TO omni_cio_runtime;
'@
        Invoke-MigrationsAsOwnerSspi -PythonPath $venvPython
        Invoke-PsqlText -Database "omni_cio_v10" -Sql @'
\set ON_ERROR_STOP on
GRANT USAGE ON SCHEMA omni_cio_v10 TO omni_cio_runtime;
GRANT SELECT ON TABLE omni_cio_v10.schema_migrations TO omni_cio_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    omni_cio_v10.web_sessions,
    omni_cio_v10.broker_connections,
    omni_cio_v10.broker_connection_accounts,
    omni_cio_v10.broker_accounts
TO omni_cio_runtime;
DO $omni$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_hba_file_rules WHERE error IS NOT NULL) THEN
        RAISE EXCEPTION 'HBA_RULE_PARSE_ERROR';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_ident_file_mappings WHERE error IS NOT NULL) THEN
        RAISE EXCEPTION 'IDENT_RULE_PARSE_ERROR';
    END IF;
END
$omni$;
'@
    }
    catch {
        Copy-Item -LiteralPath $hbaBackup -Destination $hbaPath -Force -ErrorAction SilentlyContinue
        Copy-Item -LiteralPath $identBackup -Destination $identPath -Force -ErrorAction SilentlyContinue
        try { Reload-Postgres -DataRoot $dataRoot } catch { }
        throw
    }

    Set-ManagedConfigBlock -Path $hbaPath -Lines @(
        "host omni_cio_v10 omni_cio_runtime 127.0.0.1/32 sspi $sspiOptions map=omni_cio_runtime_map"
    )
    Set-ManagedConfigBlock -Path $identPath -Lines @(
        "omni_cio_runtime_map $runtimeField omni_cio_runtime"
    )
    Reload-Postgres -DataRoot $dataRoot

    $runtimePassword = New-RandomRuntimePassword
    try {
        $securePassword = ConvertTo-SecureString -String $runtimePassword -AsPlainText -Force
        Set-LocalUser -Name $runtimeName -Password $securePassword -ErrorAction Stop
        Enable-LocalUser -Name $runtimeName -ErrorAction Stop
        $launcher = Join-Path $appRoot $launcherRelative
        $arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$launcher`" -AppRoot `"$appRoot`" -ImplementationSha $implementationSha -PendingEvidencePath `"$pendingEvidencePath`" -Port $Port"
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments
        $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew -RestartCount 0
        Register-ScheduledTask -TaskName $taskName -Action $action -Settings $settings -User $runtimeAccount -Password $runtimePassword -RunLevel Limited -Force | Out-Null
        Start-ScheduledTask -TaskName $taskName -ErrorAction Stop
    }
    finally {
        $runtimePassword = $null
        $securePassword = $null
    }

    $readyHttp = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Seconds 2
        try {
            $status = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:{0}/api/v10/web/private-test-login/status" -f $Port) -TimeoutSec 2
            if ($null -ne $status -and [bool]$status.enabled) { $readyHttp = $true; break }
        }
        catch { }
    }
    if (-not $readyHttp) {
        Stop-And-RemoveTask
        Disable-LocalUser -Name $runtimeName -ErrorAction SilentlyContinue
        throw "WP15_LIVE_LOOPBACK_RUNTIME_NOT_READY"
    }
}

$present = Test-Path -LiteralPath $runtimeRoot -PathType Container
$owned = $present -and (Test-Path -LiteralPath $runtimeMarker -PathType Leaf) -and ((Get-Content -LiteralPath $runtimeMarker -Raw).Trim() -eq $runtimeMarkerValue)
$deploymentBound = $owned -and (Test-Path -LiteralPath $deploymentMarker -PathType Leaf) -and ((Get-Content -LiteralPath $deploymentMarker -Raw).Trim().ToLowerInvariant() -eq $implementationSha)
$pendingMarkerOk = $owned -and (Test-Path -LiteralPath $pendingMarker -PathType Leaf) -and ((Get-Content -LiteralPath $pendingMarker -Raw).Trim() -eq $pendingMarkerValue)
$task = if ($env:OS -eq "Windows_NT") { Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue } else { $null }
$taskPresent = $null -ne $task
$taskRunning = $taskPresent -and [string]$task.State -eq "Running"
$runtimeEnabled = if ($null -ne $runtimeUser) { [bool](Get-LocalUser -Name $runtimeName -ErrorAction Stop).Enabled } else { $false }
$appAcl = if ($null -ne $runtimeUser -and $null -ne $runnerSid) { Test-DirectoryAcl -Path $appRoot -RuntimeSid $runtimeUser.SID -RunnerSid $runnerSid -RuntimeWriteExpected $false } else { $null }
$pendingAcl = if ($null -ne $runtimeUser -and $null -ne $runnerSid) { Test-DirectoryAcl -Path $pendingRoot -RuntimeSid $runtimeUser.SID -RunnerSid $runnerSid -RuntimeWriteExpected $true } else { $null }
$loopbackReady = $false
if ($taskRunning) {
    try {
        $status = Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:{0}/api/v10/web/private-test-login/status" -f $Port) -TimeoutSec 2
        $loopbackReady = $null -ne $status -and [bool]$status.enabled
    }
    catch { $loopbackReady = $false }
}

$ready = $owned -and $deploymentBound -and $pendingMarkerOk -and $taskPresent -and $taskRunning -and $runtimeEnabled -and $loopbackReady -and $null -ne $appAcl -and $appAcl.protected -and $appAcl.runtime_read -and (-not $appAcl.runtime_write) -and (-not $appAcl.runner_read) -and (-not $appAcl.runner_write) -and (-not $appAcl.broad) -and $null -ne $pendingAcl -and $pendingAcl.protected -and $pendingAcl.runtime_read -and $pendingAcl.runtime_write -and (-not $pendingAcl.runner_read) -and (-not $pendingAcl.runner_write) -and (-not $pendingAcl.broad)

$result = [ordered]@{
    schema_version = "1"
    work_package = "WP15"
    evidence_type = "LIVE_WEB_RUNTIME_PROVISIONING"
    implementation_sha = $implementationSha
    runtime_root_owned = [bool]$owned
    deployment_bound = [bool]$deploymentBound
    pending_boundary_ready = [bool]$pendingMarkerOk
    temporary_task_present = [bool]$taskPresent
    temporary_task_running = [bool]$taskRunning
    runtime_role_enabled = [bool]$runtimeEnabled
    loopback_runtime_ready = [bool]$loopbackReady
    app_runtime_read = if ($null -ne $appAcl) { [bool]$appAcl.runtime_read } else { $false }
    app_runtime_write = if ($null -ne $appAcl) { [bool]$appAcl.runtime_write } else { $true }
    pending_runtime_write = if ($null -ne $pendingAcl) { [bool]$pendingAcl.runtime_write } else { $false }
    runner_private_runtime_read = if ($null -ne $pendingAcl) { [bool]$pendingAcl.runner_read } else { $true }
    runner_private_runtime_write = if ($null -ne $pendingAcl) { [bool]$pendingAcl.runner_write } else { $true }
    postgres_authentication = "SSPI"
    postgres_trust_used = $false
    database_password_persisted = $false
    runtime_password_logged_or_exported = $false
    wp9_permanent_task_modified = $false
    real_secret_values_used = $false
    broker_write_authority_added = $false
    trading_methods = $false
    gateway_entrypoint = "app:app"
    ready = [bool]$ready
}

if ($AsJson) { $result | ConvertTo-Json -Depth 5 } else { $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value } }
if (($Apply -or $Verify) -and -not $ready) { exit 71 }
if (-not $Apply -and -not $Verify -and -not $Cleanup -and -not $ready) { exit 72 }
