[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedImplementationSha,
    [switch]$Inspect,
    [switch]$AsJson,
    [ValidateRange(1024, 65535)][int]$Port = 8765
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "WP15 live Web acceptance launcher requires Windows."
}

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not $Inspect -and -not (Test-Administrator)) {
    throw "WP15 live acceptance launcher requires OWNER administrator."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$provisioner = Join-Path $PSScriptRoot "provision_wp15_live_web_acceptance.ps1"
$runtimeName = "omni-cio-runtime"
$runtimeOwnershipMarker = "Omni-CIO V10 WP6 runtime role anchor"
$batchRight = "SeBatchLogonRight"
$denyBatchRight = "SeDenyBatchLogonRight"

$expected = $ExpectedImplementationSha.Trim().ToLowerInvariant()
if ($expected -notmatch '^[0-9a-f]{40}$') {
    throw "WP15_LIVE_EXPECTED_SHA_INVALID"
}
$head = @(& git -C $repoRoot rev-parse HEAD 2>$null)
if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1) {
    throw "WP15_LIVE_GIT_HEAD_UNAVAILABLE"
}
$actual = ([string]$head[0]).Trim().ToLowerInvariant()
if ($actual -ne $expected) {
    throw "WP15_LIVE_GIT_HEAD_MISMATCH"
}
$dirty = @(& git -C $repoRoot status --porcelain 2>$null)
if ($LASTEXITCODE -ne 0) {
    throw "WP15_LIVE_GIT_STATUS_UNAVAILABLE"
}
if ($dirty.Count -ne 0) {
    throw "WP15_LIVE_WORKTREE_NOT_CLEAN"
}
if (-not (Test-Path -LiteralPath $provisioner -PathType Leaf)) {
    throw "WP15_LIVE_PROVISIONER_MISSING"
}

$runtimeUser = Get-LocalUser -Name $runtimeName -ErrorAction Stop
if ([string]$runtimeUser.Description -ne $runtimeOwnershipMarker) {
    throw "WP15_LIVE_RUNTIME_ROLE_OWNERSHIP_INVALID"
}
$administratorsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
$admins = @(Get-LocalGroupMember -SID $administratorsSid -ErrorAction Stop)
if ($admins.SID.Value -contains $runtimeUser.SID.Value) {
    throw "WP15_LIVE_RUNTIME_IS_ADMINISTRATOR"
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
            attributes.Length = (uint)Marshal.SizeOf(typeof(LSA_OBJECT_ATTRIBUTES));
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

$runtimeSid = $runtimeUser.SID.Value
$rightsBefore = @([OmniCioV10.NativeAccountRights]::GetRights($runtimeSid))
$batchRightPresent = $rightsBefore -contains $batchRight
$denyBatchRightPresent = $rightsBefore -contains $denyBatchRight

if ($Inspect) {
    $inspectReady = (-not [bool]$runtimeUser.Enabled) -and (-not $denyBatchRightPresent)
    $result = [ordered]@{
        schema_version = "1"
        work_package = "WP15"
        evidence_type = "LIVE_RUNTIME_BATCH_LOGON_PREFLIGHT"
        implementation_sha = $actual
        runtime_role_enabled = [bool]$runtimeUser.Enabled
        runtime_is_administrator = $false
        batch_logon_right_present = [bool]$batchRightPresent
        deny_batch_logon_right_present = [bool]$denyBatchRightPresent
        mutation_performed = $false
        real_secret_values_used = $false
        broker_write_authority_added = $false
        trading_methods = $false
        gateway_entrypoint = "app:app"
        ready = [bool]$inspectReady
    }
    if ($AsJson) {
        $result | ConvertTo-Json -Depth 4
    }
    else {
        $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value }
    }
    if (-not $inspectReady) { exit 73 }
    exit 0
}

if ([bool]$runtimeUser.Enabled) {
    throw "WP15_LIVE_RUNTIME_ROLE_MUST_START_DISABLED"
}
if ($denyBatchRightPresent) {
    throw "WP15_LIVE_RUNTIME_DENY_BATCH_LOGON_RIGHT_PRESENT"
}

$batchRightAdded = $false
$childExit = $null
$executionFailure = $null
$restoreFailure = $null

try {
    if (-not $batchRightPresent) {
        [OmniCioV10.NativeAccountRights]::AddRight($runtimeSid, $batchRight)
        $batchRightAdded = $true
    }
    $rightsDuring = @([OmniCioV10.NativeAccountRights]::GetRights($runtimeSid))
    if ($rightsDuring -notcontains $batchRight) {
        throw "WP15_LIVE_RUNTIME_BATCH_LOGON_RIGHT_UNAVAILABLE"
    }

    $arguments = @(
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy", "Bypass",
        "-File", $provisioner,
        "-ExpectedImplementationSha", $expected,
        "-Apply",
        "-Port", [string]$Port
    )
    if ($AsJson) {
        $arguments += "-AsJson"
    }
    & powershell.exe @arguments
    $childExit = $LASTEXITCODE
}
catch {
    $executionFailure = $_
}
finally {
    if ($batchRightAdded) {
        try {
            [OmniCioV10.NativeAccountRights]::RemoveRight($runtimeSid, $batchRight)
            $rightsAfter = @([OmniCioV10.NativeAccountRights]::GetRights($runtimeSid))
            if ($rightsAfter -contains $batchRight) {
                throw "WP15_LIVE_RUNTIME_BATCH_LOGON_RIGHT_RESTORE_FAILED"
            }
        }
        catch {
            $restoreFailure = $_
        }
    }
}

if ($null -ne $restoreFailure) {
    throw "WP15_LIVE_RUNTIME_BATCH_LOGON_RIGHT_RESTORE_FAILED"
}
if ($null -ne $executionFailure) {
    throw $executionFailure
}
if ($null -eq $childExit) {
    throw "WP15_LIVE_PROVISIONER_EXIT_UNAVAILABLE"
}
if ([int]$childExit -ne 0) {
    exit [int]$childExit
}
exit 0
