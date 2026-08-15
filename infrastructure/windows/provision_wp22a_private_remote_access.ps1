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

$modeCount = @(@($Apply, $Verify, $Cleanup) | Where-Object { $_ }).Count
if ($modeCount -ne 1) { throw "Choose exactly one of -Apply, -Verify, or -Cleanup." }
if ($env:OS -ne "Windows_NT") { throw "WP22A private remote provisioning requires Windows." }

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$baseProvisioner = Join-Path $repoRoot "infrastructure\windows\provision_wp15_live_web_acceptance.ps1"
$baseStarter = Join-Path $repoRoot "infrastructure\windows\start_wp15_live_web_acceptance.ps1"
$runtimeName = "omni-cio-runtime"
$baseTaskName = "OmniCIO.V10.WP15LiveAcceptance"
$remoteTaskName = "OmniCIO.V10.WP22APrivateRemote"
$runnerFirewallRuleName = "OmniCIO.V10.WP22A.BlockRunnerLoopback"
$runtimeRoot = "C:\ProgramData\OmniCIO\runtime\wp15-live"
$appRoot = Join-Path $runtimeRoot "app"
$launcherRelative = "infrastructure\windows\run_wp22a_private_remote_runtime.ps1"
$deploymentMarker = Join-Path $appRoot ".omni-cio-wp15-live-deployment"
$batchRight = "SeBatchLogonRight"
$denyBatchRight = "SeDenyBatchLogonRight"
$remoteTaskDescription = "Omni-CIO V10 WP22A private remote runtime"
$remoteTaskOwnedBatchRightDescription = "$remoteTaskDescription; BatchRightOwned=true"
$remoteTaskPreservedBatchRightDescription = "$remoteTaskDescription; BatchRightOwned=false"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-ReviewedHead {
    $expected = $ExpectedImplementationSha.Trim().ToLowerInvariant()
    if ($expected -notmatch '^[0-9a-f]{40}$') { throw "WP22A_EXPECTED_SHA_INVALID" }
    $head = @(& git -C $repoRoot rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1) { throw "WP22A_GIT_HEAD_UNAVAILABLE" }
    $actual = ([string]$head[0]).Trim().ToLowerInvariant()
    if ($actual -ne $expected) { throw "WP22A_GIT_HEAD_MISMATCH" }
    $dirty = @(& git -C $repoRoot status --porcelain 2>$null)
    if ($LASTEXITCODE -ne 0) { throw "WP22A_GIT_STATUS_UNAVAILABLE" }
    if ($dirty.Count -ne 0) { throw "WP22A_WORKTREE_NOT_CLEAN" }
    return $actual
}

function Get-SafeReasonCode {
    param(
        [AllowNull()][string]$Text,
        [Parameter(Mandatory = $true)][string]$Fallback
    )

    if (-not [string]::IsNullOrWhiteSpace($Text)) {
        $matches = [regex]::Matches($Text, '(?<![A-Z0-9_])(?:WP15|WP17|WP22A)_[A-Z0-9_]+')
        if ($matches.Count -gt 0) {
            return [string]$matches[$matches.Count - 1].Value
        }
    }
    return $Fallback
}

function Get-AccountSidValue {
    param([Parameter(Mandatory = $true)][string]$AccountName)

    $normalized = $AccountName.Trim().ToUpperInvariant()
    if ($normalized -in @("LOCALSYSTEM", ".\LOCALSYSTEM", "NT AUTHORITY\SYSTEM")) {
        return "S-1-5-18"
    }
    if ($normalized -eq "NT AUTHORITY\NETWORKSERVICE") { return "S-1-5-20" }
    if ($normalized -eq "NT AUTHORITY\LOCALSERVICE") { return "S-1-5-19" }
    try {
        $account = [System.Security.Principal.NTAccount]::new($AccountName)
        return $account.Translate([System.Security.Principal.SecurityIdentifier]).Value
    }
    catch { throw "WP22A_RUNNER_IDENTITY_SID_UNAVAILABLE" }
}

function Get-RunnerSidValue {
    $services = @(
        Get-CimInstance Win32_Service -ErrorAction Stop |
            Where-Object { $_.Name -like "actions.runner.*" }
    )
    if ($services.Count -ne 1) { throw "WP22A_RUNNER_SERVICE_IDENTITY_AMBIGUOUS" }
    $startName = ([string]$services[0].StartName).Trim()
    $normalized = $startName.ToUpperInvariant()
    if ($normalized -in @("LOCALSYSTEM", ".\LOCALSYSTEM", "NT AUTHORITY\SYSTEM")) {
        throw "WP22A_RUNNER_LOCAL_SYSTEM_FORBIDDEN"
    }
    return Get-AccountSidValue -AccountName $startName
}

function Resolve-TailscaleExe {
    $candidate = Get-Command tailscale.exe -ErrorAction SilentlyContinue
    if ($null -ne $candidate) { return $candidate.Source }
    $paths = @(
        (Join-Path $env:ProgramFiles "Tailscale\tailscale.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Tailscale\tailscale.exe")
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    foreach ($path in $paths) {
        if (Test-Path -LiteralPath $path -PathType Leaf) { return $path }
    }
    throw "WP22A_TAILSCALE_CLI_NOT_INSTALLED"
}

function Invoke-TailscaleText {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$AllowFailure,
        [string]$FailureCode = "WP22A_TAILSCALE_COMMAND_FAILED"
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = @(& $Exe @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    $text = ($output | ForEach-Object { [string]$_ }) -join "`n"
    if (-not $AllowFailure -and $exitCode -ne 0) {
        throw $FailureCode
    }
    return [ordered]@{ exit_code = [int]$exitCode; text = $text }
}

function Get-TailscaleIdentity {
    param([Parameter(Mandatory = $true)][string]$Exe)

    $raw = Invoke-TailscaleText -Exe $Exe -Arguments @("status", "--json") -FailureCode "WP22A_TAILSCALE_STATUS_UNAVAILABLE"
    try { $status = $raw.text | ConvertFrom-Json -ErrorAction Stop }
    catch { throw "WP22A_TAILSCALE_STATUS_INVALID" }
    if ([string]$status.BackendState -ne "Running") { throw "WP22A_TAILSCALE_NOT_RUNNING" }
    if ($null -eq $status.Self -or -not [bool]$status.Self.Online) {
        throw "WP22A_TAILSCALE_SELF_OFFLINE"
    }
    $tagsProperty = @($status.Self.PSObject.Properties | Where-Object { $_.Name -eq "Tags" }) | Select-Object -First 1
    $tags = if ($null -ne $tagsProperty) { @($tagsProperty.Value) } else { @() }
    $activeTags = @($tags | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($activeTags.Count -ne 0) { throw "WP22A_TAILSCALE_TAGGED_NODE_UNSUPPORTED" }

    $hostName = ([string]$status.Self.DNSName).Trim().ToLowerInvariant().TrimEnd('.')
    if ($hostName -notmatch '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*\.ts\.net$') {
        throw "WP22A_TAILSCALE_DNS_NAME_INVALID"
    }
    $userId = [string]$status.Self.UserID
    $property = @($status.User.PSObject.Properties | Where-Object { $_.Name -eq $userId }) | Select-Object -First 1
    if ($null -eq $property) { throw "WP22A_TAILSCALE_OWNER_IDENTITY_UNAVAILABLE" }
    $login = ([string]$property.Value.LoginName).Trim()
    if ([string]::IsNullOrWhiteSpace($login)) { throw "WP22A_TAILSCALE_OWNER_LOGIN_EMPTY" }
    if ($login.ToCharArray() | Where-Object { [int]$_ -gt 127 }) {
        throw "WP22A_TAILSCALE_OWNER_LOGIN_NON_ASCII_UNSUPPORTED"
    }

    $normalized = $login.ToLowerInvariant()
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalized)
        $digest = $sha.ComputeHash($bytes)
        $fingerprint = -join ($digest | ForEach-Object { $_.ToString("x2") })
    }
    finally { $sha.Dispose() }
    return [ordered]@{ host = $hostName; owner_login_sha256 = $fingerprint }
}

function Test-NoFunnel {
    param([Parameter(Mandatory = $true)][string]$Exe)

    $status = Invoke-TailscaleText -Exe $Exe -Arguments @("funnel", "status") -AllowFailure
    if ($status.exit_code -ne 0) { throw "WP22A_TAILSCALE_FUNNEL_STATUS_UNAVAILABLE" }
    return -not (
        $status.text -match '(?i)Available on the internet:' -or
        $status.text -match '(?i)\(Funnel on\)'
    )
}

function Get-ServeState {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][string]$HostName
    )

    $status = Invoke-TailscaleText -Exe $Exe -Arguments @("serve", "status") -AllowFailure
    if ($status.exit_code -ne 0) { throw "WP22A_TAILSCALE_SERVE_STATUS_UNAVAILABLE" }
    $target = "127.0.0.1:$Port"
    $matches = $status.text.IndexOf($HostName, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $status.text.IndexOf($target, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    $anyServe = $status.text -match '(?i)https://[^\s]+\.ts\.net'
    return [ordered]@{ expected = [bool]$matches; any = [bool]$anyServe }
}

function Disable-ServeChecked {
    param([Parameter(Mandatory = $true)][string]$Exe)

    # Current Tailscale CLI exposes `serve reset` as the supported way to clear
    # the Serve configuration. The previous bare `serve off` invocation is not a
    # documented current command and could leave a partially configured route.
    $reset = Invoke-TailscaleText -Exe $Exe -Arguments @("serve", "reset") -AllowFailure
    if ($reset.exit_code -ne 0) { throw "WP22A_TAILSCALE_SERVE_RESET_FAILED" }
    $status = Invoke-TailscaleText -Exe $Exe -Arguments @("serve", "status") -AllowFailure
    if ($status.exit_code -ne 0) { throw "WP22A_TAILSCALE_SERVE_STATUS_UNAVAILABLE" }
    if ($status.text -match '(?i)https://[^\s]+\.ts\.net') {
        throw "WP22A_TAILSCALE_SERVE_DISABLE_FAILED"
    }
}

function New-RandomRuntimePassword {
    $bytes = New-Object byte[] 48
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $password = $null
    try {
        $rng.GetBytes($bytes)
        $password = [Convert]::ToBase64String($bytes) + "!aA7"
    }
    finally {
        $rng.Dispose()
        [Array]::Clear($bytes, 0, $bytes.Length)
    }
    return $password
}

if (-not ("OmniCioV10.NativeAccountRights" -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.Principal;

namespace OmniCioV10
{
    public static class NativeAccountRights
    {
        private const uint POLICY_CREATE_ACCOUNT = 0x00000010;
        private const uint POLICY_LOOKUP_NAMES = 0x00000800;
        private const uint STATUS_SUCCESS = 0x00000000;

        [StructLayout(LayoutKind.Sequential)]
        private struct LSA_OBJECT_ATTRIBUTES
        {
            public uint Length;
            public IntPtr RootDirectory;
            public IntPtr ObjectName;
            public uint Attributes;
            public IntPtr SecurityDescriptor;
            public IntPtr SecurityQualityOfService;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct LSA_UNICODE_STRING
        {
            public ushort Length;
            public ushort MaximumLength;
            public IntPtr Buffer;
        }

        [DllImport("advapi32.dll", SetLastError = true, PreserveSig = true)]
        private static extern uint LsaOpenPolicy(
            IntPtr SystemName,
            ref LSA_OBJECT_ATTRIBUTES ObjectAttributes,
            uint DesiredAccess,
            out IntPtr PolicyHandle);

        [DllImport("advapi32.dll", SetLastError = true, PreserveSig = true)]
        private static extern uint LsaEnumerateAccountRights(
            IntPtr PolicyHandle,
            IntPtr AccountSid,
            out IntPtr UserRights,
            out uint CountOfRights);

        [DllImport("advapi32.dll", SetLastError = true, PreserveSig = true)]
        private static extern uint LsaAddAccountRights(
            IntPtr PolicyHandle,
            IntPtr AccountSid,
            [In] LSA_UNICODE_STRING[] UserRights,
            uint CountOfRights);

        [DllImport("advapi32.dll", SetLastError = true, PreserveSig = true)]
        private static extern uint LsaRemoveAccountRights(
            IntPtr PolicyHandle,
            IntPtr AccountSid,
            [MarshalAs(UnmanagedType.U1)] bool AllRights,
            [In] LSA_UNICODE_STRING[] UserRights,
            uint CountOfRights);

        [DllImport("advapi32.dll")]
        private static extern uint LsaNtStatusToWinError(uint Status);

        [DllImport("advapi32.dll")]
        private static extern uint LsaClose(IntPtr PolicyHandle);

        [DllImport("advapi32.dll")]
        private static extern uint LsaFreeMemory(IntPtr Buffer);

        private static IntPtr OpenPolicy(uint desiredAccess)
        {
            var attributes = new LSA_OBJECT_ATTRIBUTES();
            IntPtr handle;
            uint status = LsaOpenPolicy(
                IntPtr.Zero,
                ref attributes,
                desiredAccess,
                out handle);
            ThrowForStatus(status, "LsaOpenPolicy");
            return handle;
        }

        private static IntPtr AllocSid(string sidText)
        {
            var sid = new SecurityIdentifier(sidText);
            var bytes = new byte[sid.BinaryLength];
            sid.GetBinaryForm(bytes, 0);
            IntPtr ptr = Marshal.AllocHGlobal(bytes.Length);
            Marshal.Copy(bytes, 0, ptr, bytes.Length);
            Array.Clear(bytes, 0, bytes.Length);
            return ptr;
        }

        private static LSA_UNICODE_STRING MakeString(string value)
        {
            IntPtr buffer = Marshal.StringToHGlobalUni(value);
            return new LSA_UNICODE_STRING
            {
                Buffer = buffer,
                Length = checked((ushort)(value.Length * 2)),
                MaximumLength = checked((ushort)((value.Length + 1) * 2))
            };
        }

        private static void FreeString(LSA_UNICODE_STRING value)
        {
            if (value.Buffer != IntPtr.Zero)
            {
                Marshal.FreeHGlobal(value.Buffer);
            }
        }

        private static void ThrowForStatus(uint status, string operation)
        {
            if (status == STATUS_SUCCESS)
            {
                return;
            }
            uint error = LsaNtStatusToWinError(status);
            throw new Win32Exception(unchecked((int)error), operation + " failed");
        }

        public static string[] GetRights(string sidText)
        {
            IntPtr policy = IntPtr.Zero;
            IntPtr sid = IntPtr.Zero;
            IntPtr rights = IntPtr.Zero;
            try
            {
                policy = OpenPolicy(POLICY_LOOKUP_NAMES);
                sid = AllocSid(sidText);
                uint count;
                uint status = LsaEnumerateAccountRights(policy, sid, out rights, out count);
                if (status != STATUS_SUCCESS)
                {
                    uint error = LsaNtStatusToWinError(status);
                    if (error == 2)
                    {
                        return new string[0];
                    }
                    throw new Win32Exception(unchecked((int)error), "LsaEnumerateAccountRights failed");
                }

                var result = new List<string>();
                int size = Marshal.SizeOf(typeof(LSA_UNICODE_STRING));
                for (uint index = 0; index < count; index++)
                {
                    IntPtr current = IntPtr.Add(rights, checked((int)(index * (uint)size)));
                    var item = (LSA_UNICODE_STRING)Marshal.PtrToStructure(current, typeof(LSA_UNICODE_STRING));
                    string value = Marshal.PtrToStringUni(item.Buffer, item.Length / 2);
                    if (!String.IsNullOrWhiteSpace(value))
                    {
                        result.Add(value);
                    }
                }
                return result.ToArray();
            }
            finally
            {
                if (rights != IntPtr.Zero) { LsaFreeMemory(rights); }
                if (sid != IntPtr.Zero) { Marshal.FreeHGlobal(sid); }
                if (policy != IntPtr.Zero) { LsaClose(policy); }
            }
        }

        public static void AddRight(string sidText, string right)
        {
            ChangeRight(sidText, right, true);
        }

        public static void RemoveRight(string sidText, string right)
        {
            ChangeRight(sidText, right, false);
        }

        private static void ChangeRight(string sidText, string right, bool add)
        {
            IntPtr policy = IntPtr.Zero;
            IntPtr sid = IntPtr.Zero;
            LSA_UNICODE_STRING nativeRight = default(LSA_UNICODE_STRING);
            try
            {
                uint access = POLICY_LOOKUP_NAMES | (add ? POLICY_CREATE_ACCOUNT : 0);
                policy = OpenPolicy(access);
                sid = AllocSid(sidText);
                nativeRight = MakeString(right);
                var rights = new[] { nativeRight };
                uint status = add
                    ? LsaAddAccountRights(policy, sid, rights, 1)
                    : LsaRemoveAccountRights(policy, sid, false, rights, 1);
                ThrowForStatus(status, add ? "LsaAddAccountRights" : "LsaRemoveAccountRights");
            }
            finally
            {
                FreeString(nativeRight);
                if (sid != IntPtr.Zero) { Marshal.FreeHGlobal(sid); }
                if (policy != IntPtr.Zero) { LsaClose(policy); }
            }
        }
    }
}
'@
}


function Test-RemoteTaskOwnsBatchRight {
    $task = Get-ScheduledTask -TaskName $remoteTaskName -ErrorAction SilentlyContinue
    if ($null -eq $task) { return $false }
    return ([string]$task.Description).Equals(
        $remoteTaskOwnedBatchRightDescription,
        [System.StringComparison]::Ordinal
    )
}

function Get-RuntimeAccountRights {
    $runtimeUser = Get-LocalUser -Name $runtimeName -ErrorAction Stop
    return @([OmniCioV10.NativeAccountRights]::GetRights($runtimeUser.SID.Value))
}

function Remove-RemoteBatchRightIfOwned {
    param([Parameter(Mandatory = $true)][bool]$Owned)

    if (-not $Owned) { return }
    $runtimeUser = Get-LocalUser -Name $runtimeName -ErrorAction Stop
    $runtimeSid = $runtimeUser.SID.Value
    $rights = @([OmniCioV10.NativeAccountRights]::GetRights($runtimeSid))
    if ($rights -contains $batchRight) {
        [OmniCioV10.NativeAccountRights]::RemoveRight($runtimeSid, $batchRight)
    }
    $rightsAfter = @([OmniCioV10.NativeAccountRights]::GetRights($runtimeSid))
    if ($rightsAfter -contains $batchRight) {
        throw "WP22A_REMOTE_RUNTIME_BATCH_LOGON_RIGHT_CLEANUP_FAILED"
    }
}

function Test-RemoteRuntimeBatchRight {
    try {
        $rights = @(Get-RuntimeAccountRights)
        return (
            $rights -contains $batchRight -and
            $rights -notcontains $denyBatchRight
        )
    }
    catch { return $false }
}

function Get-RemoteTaskFailureReason {
    $task = Get-ScheduledTask -TaskName $remoteTaskName -ErrorAction SilentlyContinue
    if ($null -eq $task) { return "WP22A_REMOTE_TASK_MISSING" }

    $state = ([string]$task.State).ToUpperInvariant()
    $taskInfo = Get-ScheduledTaskInfo -TaskName $remoteTaskName -ErrorAction SilentlyContinue
    $lastResult = if ($null -ne $taskInfo) { [int64]$taskInfo.LastTaskResult } else { -1 }

    if ($lastResult -in @(2147943785, -2147023511)) {
        return "WP22A_REMOTE_TASK_BATCH_LOGON_DENIED"
    }
    if ($state -eq "READY" -and $lastResult -eq 267011) {
        return "WP22A_REMOTE_TASK_HAS_NOT_RUN"
    }
    if ($state -eq "RUNNING") { return "WP22A_REMOTE_BACKEND_NOT_READY" }
    if ($state -eq "DISABLED") { return "WP22A_REMOTE_TASK_DISABLED" }
    return "WP22A_REMOTE_TASK_EXITED_BEFORE_READY"
}

function Get-BaseWebFailureReason {
    param(
        [AllowNull()][string]$Text,
        [Parameter(Mandatory = $true)][ValidateSet("Apply", "Cleanup", "Verify")][string]$Mode
    )

    $fallback = "WP22A_BASE_WEB_{0}_FAILED" -f $Mode.ToUpperInvariant()
    $symbolic = Get-SafeReasonCode -Text $Text -Fallback $fallback
    if ($symbolic -ne $fallback) { return $symbolic }
    if ($Mode -ne "Apply" -or [string]::IsNullOrWhiteSpace($Text)) { return $fallback }

    try {
        $payload = $Text | ConvertFrom-Json -ErrorAction Stop
    }
    catch { return $fallback }

    if (
        [string]$payload.work_package -ne "WP15" -or
        [string]$payload.evidence_type -ne "LIVE_WEB_RUNTIME_PROVISIONING"
    ) {
        return $fallback
    }

    $checks = @(
        [ordered]@{ name = "runtime_root_owned"; expected = $true; code = "WP15_LIVE_RUNTIME_ROOT_NOT_OWNED" },
        [ordered]@{ name = "deployment_bound"; expected = $true; code = "WP15_LIVE_DEPLOYMENT_NOT_BOUND" },
        [ordered]@{ name = "pending_boundary_ready"; expected = $true; code = "WP15_LIVE_PENDING_BOUNDARY_NOT_READY" },
        [ordered]@{ name = "temporary_task_present"; expected = $true; code = "WP15_LIVE_TASK_MISSING" },
        [ordered]@{ name = "temporary_task_running"; expected = $true; code = "WP15_LIVE_TASK_NOT_RUNNING" },
        [ordered]@{ name = "runtime_role_enabled"; expected = $true; code = "WP15_LIVE_RUNTIME_ROLE_DISABLED" },
        [ordered]@{ name = "loopback_runtime_ready"; expected = $true; code = "WP15_LIVE_LOOPBACK_RUNTIME_NOT_READY" },
        [ordered]@{ name = "app_runtime_read"; expected = $true; code = "WP15_LIVE_APP_RUNTIME_READ_DENIED" },
        [ordered]@{ name = "app_runtime_write"; expected = $false; code = "WP15_LIVE_APP_RUNTIME_WRITE_EXPOSED" },
        [ordered]@{ name = "pending_runtime_write"; expected = $true; code = "WP15_LIVE_PENDING_RUNTIME_WRITE_DENIED" },
        [ordered]@{ name = "runner_private_runtime_read"; expected = $false; code = "WP15_LIVE_RUNNER_PRIVATE_READ_EXPOSED" },
        [ordered]@{ name = "runner_private_runtime_write"; expected = $false; code = "WP15_LIVE_RUNNER_PRIVATE_WRITE_EXPOSED" }
    )
    foreach ($check in $checks) {
        $name = [string]$check["name"]
        $expected = [bool]$check["expected"]
        $property = @(
            $payload.PSObject.Properties |
                Where-Object { $_.Name -eq $name }
        ) | Select-Object -First 1
        if (
            $null -ne $property -and
            [bool]$property.Value -ne $expected
        ) {
            return [string]$check["code"]
        }
    }
    return $fallback
}

function Invoke-BaseProvisioner {
    param(
        [Parameter(Mandatory = $true)][string]$Sha,
        [Parameter(Mandatory = $true)][ValidateSet("Apply", "Cleanup", "Verify")][string]$Mode
    )

    # WP15 Apply must enter through the accepted OWNER starter. That boundary
    # grants SeBatchLogonRight only for task registration/start and restores the
    # original account rights afterward. Cleanup and Verify remain direct,
    # accepted provisioner calls.
    $entrypoint = if ($Mode -eq "Apply") { $baseStarter } else { $baseProvisioner }
    if (-not (Test-Path -LiteralPath $entrypoint -PathType Leaf)) {
        throw "WP22A_BASE_WEB_ENTRYPOINT_MISSING"
    }
    $arguments = @(
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy", "Bypass",
        "-File", $entrypoint,
        "-ExpectedImplementationSha", $Sha
    )
    if ($Mode -eq "Cleanup") { $arguments += "-Cleanup" }
    if ($Mode -eq "Verify") { $arguments += "-Verify" }
    $arguments += @(
        "-Port", [string]$Port,
        "-AsJson"
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = @(& powershell.exe @arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($exitCode -ne 0) {
        $text = ($output | ForEach-Object { [string]$_ }) -join "`n"
        $reason = Get-BaseWebFailureReason -Text $text -Mode $Mode
        throw $reason
    }
}

function Test-BaseLocalWebReady {
    param([Parameter(Mandatory = $true)][string]$Sha)

    try {
        Invoke-BaseProvisioner -Sha $Sha -Mode Verify
        return $true
    }
    catch { return $false }
}

function Ensure-BaseLocalWebReady {
    param([Parameter(Mandatory = $true)][string]$Sha)

    if (Test-BaseLocalWebReady -Sha $Sha) { return }
    Invoke-BaseProvisioner -Sha $Sha -Mode Cleanup
    Invoke-BaseProvisioner -Sha $Sha -Mode Apply
    if (-not (Test-BaseLocalWebReady -Sha $Sha)) {
        throw "WP15_LIVE_VERIFY_AFTER_APPLY_FAILED"
    }
}

function Remove-RunnerLoopbackFirewall {
    Remove-NetFirewallRule -Name $runnerFirewallRuleName -ErrorAction SilentlyContinue
}

function Install-RunnerLoopbackFirewall {
    if (-not (Test-Administrator)) { throw "WP22A_FIREWALL_REQUIRES_ADMINISTRATOR" }
    $runnerSid = Get-RunnerSidValue
    $runnerSddl = "D:(A;;CC;;;$runnerSid)"
    Remove-RunnerLoopbackFirewall
    New-NetFirewallRule `
        -Name $runnerFirewallRuleName `
        -DisplayName "Omni-CIO V10 WP22A block CI runner loopback Web" `
        -Description "Blocks the ordinary GitHub runner identity from connecting directly to the WP22A loopback backend and spoofing Tailscale identity headers." `
        -Direction Outbound `
        -Action Block `
        -Enabled True `
        -Profile Any `
        -Protocol TCP `
        -RemoteAddress 127.0.0.1 `
        -RemotePort $Port `
        -LocalUser $runnerSddl `
        -ErrorAction Stop | Out-Null
}

function Test-RunnerLoopbackFirewall {
    $runnerSid = Get-RunnerSidValue
    $rule = Get-NetFirewallRule -Name $runnerFirewallRuleName -ErrorAction SilentlyContinue
    if ($null -eq $rule) { return $false }
    if ([string]$rule.Enabled -ne "True" -or [string]$rule.Direction -ne "Outbound" -or [string]$rule.Action -ne "Block") {
        return $false
    }
    $portFilter = $rule | Get-NetFirewallPortFilter -ErrorAction Stop
    $addressFilter = $rule | Get-NetFirewallAddressFilter -ErrorAction Stop
    $securityFilter = $rule | Get-NetFirewallSecurityFilter -ErrorAction Stop
    $remotePorts = @($portFilter.RemotePort | ForEach-Object { [string]$_ })
    $remoteAddresses = @($addressFilter.RemoteAddress | ForEach-Object { [string]$_ })
    $localUser = [string]$securityFilter.LocalUser
    $expectedRunnerSddl = "D:(A;;CC;;;$runnerSid)"
    return (
        [string]$portFilter.Protocol -eq "TCP" -and
        $remotePorts -contains [string]$Port -and
        $remoteAddresses -contains "127.0.0.1" -and
        $localUser.Equals(
            $expectedRunnerSddl,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    )
}

function Restore-LocalWebTask {
    param(
        [Parameter(Mandatory = $true)][string]$Sha,
        [Parameter(Mandatory = $true)][string]$TailscaleExe
    )

    Disable-ServeChecked -Exe $TailscaleExe
    if (-not (Test-NoFunnel -Exe $TailscaleExe)) { throw "WP22A_FUNNEL_PUBLIC_INGRESS_ACTIVE" }

    $remoteTaskOwnedBatchRight = Test-RemoteTaskOwnsBatchRight
    Stop-ScheduledTask -TaskName $remoteTaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $remoteTaskName -Confirm:$false -ErrorAction SilentlyContinue

    $batchRightCleanupFailure = $null
    try {
        Remove-RemoteBatchRightIfOwned -Owned $remoteTaskOwnedBatchRight
    }
    catch {
        $batchRightCleanupFailure = $_
    }
    Remove-RunnerLoopbackFirewall

    # The accepted WP15 cleanup is intentionally safe when its task/runtime root
    # are already absent. It also disables the runtime identity. Run it
    # unconditionally so recovery works from partial cutover states where the
    # root/task disappeared but omni-cio-runtime remained enabled.
    Invoke-BaseProvisioner -Sha $Sha -Mode Cleanup
    Invoke-BaseProvisioner -Sha $Sha -Mode Apply

    $baseTask = Get-ScheduledTask -TaskName $baseTaskName -ErrorAction SilentlyContinue
    if ($null -eq $baseTask -or [string]$baseTask.State -ne "Running") {
        throw "WP22A_LOCAL_WEB_ROLLBACK_NOT_RUNNING"
    }
    if ($null -ne $batchRightCleanupFailure) {
        throw "WP22A_REMOTE_RUNTIME_BATCH_LOGON_RIGHT_CLEANUP_FAILED"
    }
}

function Install-RemoteTask {
    param(
        [Parameter(Mandatory = $true)][string]$Sha,
        [Parameter(Mandatory = $true)][string]$HostName,
        [Parameter(Mandatory = $true)][string]$OwnerFingerprint
    )
    if (-not (Test-Administrator)) { throw "WP22A_APPLY_REQUIRES_ADMINISTRATOR" }

    $existingTaskOwnedBatchRight = Test-RemoteTaskOwnsBatchRight
    # Keep an existing task definition registered until the replacement is
    # committed with -Force. Its sanitized description is the crash-safe record
    # of whether WP22A owns the runtime account's batch-logon assignment.
    Stop-ScheduledTask -TaskName $remoteTaskName -ErrorAction SilentlyContinue

    # Reuse an already accepted exact-head WP15 runtime instead of rebuilding it
    # a second time immediately after a successful OWNER Cleanup. Any stale or
    # partial state fails the accepted WP15 Verify gate and is normalized through
    # Cleanup -> Apply before remote cutover.
    Ensure-BaseLocalWebReady -Sha $Sha

    $launcher = Join-Path $appRoot $launcherRelative
    if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "WP22A_REMOTE_LAUNCHER_MISSING" }
    if (-not (Test-Path -LiteralPath $deploymentMarker -PathType Leaf)) { throw "WP22A_DEPLOYMENT_MARKER_MISSING" }
    if ((Get-Content -LiteralPath $deploymentMarker -Raw).Trim().ToLowerInvariant() -ne $Sha) {
        throw "WP22A_DEPLOYMENT_MARKER_MISMATCH"
    }

    Stop-ScheduledTask -TaskName $baseTaskName -ErrorAction SilentlyContinue

    $runtimeUser = Get-LocalUser -Name $runtimeName -ErrorAction Stop
    $administratorsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $admins = @(Get-LocalGroupMember -SID $administratorsSid -ErrorAction Stop)
    if ($admins.SID.Value -contains $runtimeUser.SID.Value) { throw "WP22A_REMOTE_RUNTIME_IS_ADMINISTRATOR" }

    $runtimeSid = $runtimeUser.SID.Value
    $rightsBefore = @([OmniCioV10.NativeAccountRights]::GetRights($runtimeSid))
    if ($rightsBefore -contains $denyBatchRight) {
        throw "WP22A_REMOTE_RUNTIME_DENY_BATCH_LOGON_RIGHT_PRESENT"
    }
    $batchRightPresent = $rightsBefore -contains $batchRight
    $batchRightOwned = [bool]($existingTaskOwnedBatchRight -or -not $batchRightPresent)
    $taskDescription = if ($batchRightOwned) {
        $remoteTaskOwnedBatchRightDescription
    }
    else {
        $remoteTaskPreservedBatchRightDescription
    }

    Install-RunnerLoopbackFirewall
    if (-not (Test-RunnerLoopbackFirewall)) { throw "WP22A_RUNNER_LOOPBACK_FIREWALL_NOT_BOUND" }

    $runtimePassword = New-RandomRuntimePassword
    $securePassword = $null
    try {
        $securePassword = ConvertTo-SecureString -String $runtimePassword -AsPlainText -Force
        Set-LocalUser -Name $runtimeName -Password $securePassword -ErrorAction Stop
        Enable-LocalUser -Name $runtimeName -ErrorAction Stop
        $runtimeAccount = "$env:COMPUTERNAME\$runtimeName"
        $arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$launcher`" -AppRoot `"$appRoot`" -ImplementationSha $Sha -ExternalHost $HostName -OwnerLoginSha256 $OwnerFingerprint -Port $Port"
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
        Register-ScheduledTask -TaskName $remoteTaskName -Action $action -Trigger $trigger -Settings $settings -User $runtimeAccount -Password $runtimePassword -RunLevel Limited -Description $taskDescription -Force | Out-Null

        $rightsAfterRegistration = @([OmniCioV10.NativeAccountRights]::GetRights($runtimeSid))
        if ($rightsAfterRegistration -notcontains $batchRight) {
            [OmniCioV10.NativeAccountRights]::AddRight($runtimeSid, $batchRight)
        }
        $rightsBeforeStart = @([OmniCioV10.NativeAccountRights]::GetRights($runtimeSid))
        if ($rightsBeforeStart -notcontains $batchRight) {
            throw "WP22A_REMOTE_RUNTIME_BATCH_LOGON_RIGHT_UNAVAILABLE"
        }
        if ($rightsBeforeStart -contains $denyBatchRight) {
            throw "WP22A_REMOTE_RUNTIME_DENY_BATCH_LOGON_RIGHT_PRESENT"
        }

        Start-ScheduledTask -TaskName $remoteTaskName -ErrorAction Stop
    }
    finally {
        $runtimePassword = $null
        $securePassword = $null
    }
}

function Test-BackendLoopback {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    if ($listeners.Count -eq 0) { return $false }
    foreach ($listener in $listeners) {
        if ([string]$listener.LocalAddress -ne "127.0.0.1") { return $false }
    }
    return $true
}

function Wait-LocalRemoteStatus {
    param([Parameter(Mandatory = $true)][string]$HostName)

    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/api/v10/web/private-tailnet-login/status" -Headers @{ Host = $HostName } -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                $body = $response.Content | ConvertFrom-Json -ErrorAction Stop
                if ([bool]$body.enabled) { return $true }
            }
        }
        catch { }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Test-RemoteOwnerSession {
    param([Parameter(Mandatory = $true)][string]$HostName)

    $origin = "https://$HostName"
    $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    try {
        $login = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$origin/api/v10/web/private-tailnet-login" -Headers @{ Origin = $origin } -WebSession $session -ContentType "application/json" -Body "{}" -TimeoutSec 10
        if ($login.StatusCode -ne 200) { return $false }
        $view = Invoke-WebRequest -UseBasicParsing -Uri "$origin/api/v10/web/session" -WebSession $session -TimeoutSec 10
        if ($view.StatusCode -ne 200) { return $false }
        $payload = $view.Content | ConvertFrom-Json -ErrorAction Stop
        if (-not [bool]$payload.authenticated) { return $false }
        $csrf = $session.Cookies.GetCookies([Uri]$origin)["__Host-omni_v10_csrf"]
        if ($null -eq $csrf -or [string]::IsNullOrWhiteSpace($csrf.Value)) { return $false }
        $logout = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$origin/api/v10/web/session/logout" -Headers @{ Origin = $origin; "X-Omni-CSRF" = $csrf.Value } -WebSession $session -ContentType "application/json" -Body "{}" -TimeoutSec 10
        return $logout.StatusCode -eq 200
    }
    catch { return $false }
}

function Enable-ServeChecked {
    param([Parameter(Mandatory = $true)][string]$Exe)

    $enable = Invoke-TailscaleText -Exe $Exe -Arguments @("serve", "--bg", "http://127.0.0.1:$Port") -AllowFailure
    if ($enable.exit_code -eq 0) { return }
    if ($enable.text -match '(?i)https://[^\s]*tailscale[^\s]*') {
        throw "WP22A_TAILSCALE_HTTPS_CONSENT_REQUIRED"
    }
    throw "WP22A_TAILSCALE_SERVE_ENABLE_FAILED"
}

function Write-Result {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$Result)
    if ($AsJson) { $Result | ConvertTo-Json -Depth 4 -Compress; return }
    foreach ($key in $Result.Keys) { Write-Output ("{0}: {1}" -f $key, $Result[$key]) }
}

$sha = Get-ReviewedHead
$tailscale = Resolve-TailscaleExe

if ($Cleanup) {
    if (-not (Test-Administrator)) { throw "WP22A_CLEANUP_REQUIRES_ADMINISTRATOR" }
    Restore-LocalWebTask -Sha $sha -TailscaleExe $tailscale
    Write-Result -Result ([ordered]@{
        status = "PASS"
        reason = "WP22A_PRIVATE_REMOTE_DISABLED_LOCAL_WEB_RESTORED"
        public_ingress = $false
        local_web_restored = $true
        remote_runtime_batch_logon_restored = $true
    })
    exit 0
}

$identity = Get-TailscaleIdentity -Exe $tailscale
if (-not (Test-NoFunnel -Exe $tailscale)) { throw "WP22A_FUNNEL_PUBLIC_INGRESS_ACTIVE" }
$serveBefore = Get-ServeState -Exe $tailscale -HostName $identity.host
if ($Apply -and $serveBefore.any -and -not $serveBefore.expected) {
    throw "WP22A_EXISTING_SERVE_CONFIGURATION_REQUIRES_OWNER_REVIEW"
}

if ($Apply) {
    try {
        Install-RemoteTask -Sha $sha -HostName $identity.host -OwnerFingerprint $identity.owner_login_sha256
        if (-not (Wait-LocalRemoteStatus -HostName $identity.host)) {
            throw (Get-RemoteTaskFailureReason)
        }
        if (-not (Test-BackendLoopback)) { throw "WP22A_BACKEND_NOT_LOOPBACK_ONLY" }
        if (-not (Test-RunnerLoopbackFirewall)) { throw "WP22A_RUNNER_LOOPBACK_FIREWALL_NOT_BOUND" }
        if (-not $serveBefore.expected) { Enable-ServeChecked -Exe $tailscale }
    }
    catch {
        $primaryReason = Get-SafeReasonCode -Text ([string]$_.Exception.Message) -Fallback "WP22A_APPLY_FAILED"
        try {
            Restore-LocalWebTask -Sha $sha -TailscaleExe $tailscale
        }
        catch {
            $rollbackReason = Get-SafeReasonCode -Text ([string]$_.Exception.Message) -Fallback "WP22A_LOCAL_ROLLBACK_FAILED"
            throw ("WP22A_APPLY_FAILED:{0};LOCAL_ROLLBACK_FAILED:{1}" -f $primaryReason, $rollbackReason)
        }
        throw ("WP22A_APPLY_FAILED:{0};LOCAL_ROLLBACK_PASS" -f $primaryReason)
    }
}

$serve = Get-ServeState -Exe $tailscale -HostName $identity.host
$loopbackOnly = Test-BackendLoopback
$runnerFirewallBound = Test-RunnerLoopbackFirewall
$remoteRuntimeBatchLogonBound = Test-RemoteRuntimeBatchRight
$remoteOwnerSession = $false
if ($serve.expected -and $loopbackOnly -and $runnerFirewallBound -and $remoteRuntimeBatchLogonBound) {
    $remoteOwnerSession = Test-RemoteOwnerSession -HostName $identity.host
}

$noFunnel = Test-NoFunnel -Exe $tailscale
$ok = $serve.expected -and $loopbackOnly -and $runnerFirewallBound -and $remoteRuntimeBatchLogonBound -and $remoteOwnerSession -and $noFunnel
$result = [ordered]@{
    status = $(if ($ok) { "PASS" } else { "FAIL" })
    reason = $(if ($ok) { "WP22A_PRIVATE_REMOTE_RUNTIME_ACCEPTED" } else { "WP22A_PRIVATE_REMOTE_RUNTIME_NOT_READY" })
    exact_implementation_binding = $true
    backend_loopback_only = [bool]$loopbackOnly
    runner_loopback_firewall_bound = [bool]$runnerFirewallBound
    remote_runtime_batch_logon_bound = [bool]$remoteRuntimeBatchLogonBound
    tailscale_serve_private = [bool]$serve.expected
    funnel_public_ingress = [bool](-not $noFunnel)
    owner_identity_binding = [bool]$remoteOwnerSession
    secure_server_session = [bool]$remoteOwnerSession
    external_url = "https://$($identity.host)"
    phone_rehearsal_required = $true
}
Write-Result -Result $result
if (-not $ok) { exit 2 }
exit 0
