[CmdletBinding()]
param()

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$pythonHome = "C:\actions-runner\_tool\omni-python-3.12.10"
$pythonExe = Join-Path $pythonHome "python.exe"
$wp15Root = "C:\ProgramData\OmniCIO\wp15"
$privateRoot = Join-Path $wp15Root "private"
$evidenceRoot = Join-Path $wp15Root "evidence"
$privateBinding = Join-Path $privateRoot "owner-account-binding.json"
$evidenceFile = Join-Path $evidenceRoot "wp15-owner-live-evidence.json"
$tempRoot = Join-Path $env:TEMP ("omni-cio-wp15-owner-" + [Guid]::NewGuid().ToString("N"))
$venvPath = Join-Path $tempRoot "venv"
$lockPath = Join-Path $tempRoot "windows-requirements.txt"

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

function Get-LocalRoleSid {
    param([Parameter(Mandatory = $true)][string]$Name)

    $user = Get-LocalUser -Name $Name -ErrorAction Stop
    return $user.SID
}

function Get-RunnerServiceSid {
    $runnerRoot = "C:\actions-runner"
    $services = @(
        Get-CimInstance Win32_Service -ErrorAction Stop |
            Where-Object {
                $pathName = [string]$_.PathName
                $_.Name -match '^actions\.runner\.' -and
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
    $account = [System.Security.Principal.NTAccount]::new(
        [string]$services[0].StartName
    )
    return $account.Translate(
        [System.Security.Principal.SecurityIdentifier]
    )
}

function New-FileSystemRule {
    param(
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$Sid,
        [Parameter(Mandatory = $true)]
        [System.Security.AccessControl.FileSystemRights]$Rights,
        [switch]$Container
    )

    $inheritance = [System.Security.AccessControl.InheritanceFlags]::None
    if ($Container) {
        $inheritance = (
            [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
            [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
        )
    }
    return [System.Security.AccessControl.FileSystemAccessRule]::new(
        $Sid,
        $Rights,
        $inheritance,
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
}

function Set-ProtectedDirectoryAcl {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$RuntimeSid,
        [System.Security.Principal.SecurityIdentifier]$RunnerSid,
        [switch]$Evidence
    )

    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-FileSystemRule `
        -Sid $systemSid `
        -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) `
        -Container))
    $acl.AddAccessRule((New-FileSystemRule `
        -Sid $adminsSid `
        -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) `
        -Container))
    $acl.AddAccessRule((New-FileSystemRule `
        -Sid $RuntimeSid `
        -Rights ([System.Security.AccessControl.FileSystemRights]::ReadAndExecute) `
        -Container))
    if ($Evidence -and $null -ne $RunnerSid) {
        $acl.AddAccessRule((New-FileSystemRule `
            -Sid $RunnerSid `
            -Rights ([System.Security.AccessControl.FileSystemRights]::Read) `
            -Container))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl -ErrorAction Stop
}

function Set-ProtectedFileAcl {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$RuntimeSid,
        [System.Security.Principal.SecurityIdentifier]$RunnerSid,
        [switch]$Evidence
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }
    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $acl = [System.Security.AccessControl.FileSecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-FileSystemRule `
        -Sid $systemSid `
        -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl)))
    $acl.AddAccessRule((New-FileSystemRule `
        -Sid $adminsSid `
        -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl)))
    $acl.AddAccessRule((New-FileSystemRule `
        -Sid $RuntimeSid `
        -Rights ([System.Security.AccessControl.FileSystemRights]::Read)))
    if ($Evidence -and $null -ne $RunnerSid) {
        $acl.AddAccessRule((New-FileSystemRule `
            -Sid $RunnerSid `
            -Rights ([System.Security.AccessControl.FileSystemRights]::Read)))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl -ErrorAction Stop
}

if (-not (Test-Administrator)) {
    throw "WP15 OWNER live gate requires elevated OWNER-admin PowerShell."
}
if ($env:GITHUB_ACTIONS -eq "true") {
    throw "WP15 OWNER live gate cannot run inside GitHub Actions."
}

Push-Location $repoRoot
try {
    $dirty = & git status --porcelain
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to verify repository checkout."
    }
    if (-not [string]::IsNullOrWhiteSpace(($dirty -join "`n"))) {
        throw "OWNER_CHECKOUT_NOT_CLEAN"
    }

    if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
        & cmd.exe /d /c "scripts\bootstrap_windows_ci_python.cmd"
        if ($LASTEXITCODE -ne 0) {
            throw "Protected Python bootstrap failed."
        }
    }
    & $pythonExe -c "import sys; assert sys.version_info[:3] == (3, 12, 10)"
    if ($LASTEXITCODE -ne 0) {
        throw "Protected Python version mismatch."
    }

    $runtimeSid = Get-LocalRoleSid -Name "omni-cio-runtime"
    $runnerSid = Get-RunnerServiceSid

    New-Item -ItemType Directory -Force -Path $privateRoot | Out-Null
    New-Item -ItemType Directory -Force -Path $evidenceRoot | Out-Null
    Set-ProtectedDirectoryAcl `
        -Path $privateRoot `
        -RuntimeSid $runtimeSid
    Set-ProtectedDirectoryAcl `
        -Path $evidenceRoot `
        -RuntimeSid $runtimeSid `
        -RunnerSid $runnerSid `
        -Evidence

    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
    & $pythonExe -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        throw "WP15 OWNER virtual environment creation failed."
    }
    $venvPython = Join-Path $venvPath "Scripts\python.exe"

    & $pythonExe scripts\windows_ci_lock.py project requirements.txt $lockPath
    if ($LASTEXITCODE -ne 0) {
        throw "WP15 OWNER dependency projection failed."
    }
    & $venvPython -m pip install `
        --disable-pip-version-check `
        --require-hashes `
        -r $lockPath
    if ($LASTEXITCODE -ne 0) {
        throw "WP15 OWNER dependency installation failed."
    }

    & $venvPython scripts\rehearse_v10_wp15_owner.py
    $gateExit = $LASTEXITCODE

    Set-ProtectedFileAcl `
        -Path $privateBinding `
        -RuntimeSid $runtimeSid
    Set-ProtectedFileAcl `
        -Path $evidenceFile `
        -RuntimeSid $runtimeSid `
        -RunnerSid $runnerSid `
        -Evidence

    if ($gateExit -ne 0) {
        exit $gateExit
    }
    exit 0
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
    Pop-Location
}
