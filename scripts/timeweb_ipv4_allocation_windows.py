"""CurrentUser-only verifier custody, outside GitHub's disposable workspace.

This local journal is never a V10 production dependency. Runner replacement or
journal loss requires explicit recovery; no missing APPLY store is initialized.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from scripts.timeweb_ipv4_allocation_journal import JournalError, SqliteJournal


_ACL_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
try {
    $root = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($root)) { exit 20 }
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $system = [Security.Principal.SecurityIdentifier]::new('S-1-5-18')
    $allowed = @($sid.Value, $system.Value)
    $new = -not (Test-Path -LiteralPath $root)
    if ($new) {
        $acl = [Security.AccessControl.DirectorySecurity]::new()
        $acl.SetOwner($sid)
        $acl.SetAccessRuleProtection($true, $false)
        foreach ($identity in @($sid, $system)) {
            $rule = [Security.AccessControl.FileSystemAccessRule]::new(
                $identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
            [void]$acl.AddAccessRule($rule)
        }
        [void][IO.Directory]::CreateDirectory($root, $acl)
    }
    $directory = Get-Item -LiteralPath $root -Force
    if (-not $directory.PSIsContainer) { exit 20 }
    $acl = Get-Acl -LiteralPath $root
    if (-not $acl.AreAccessRulesProtected) { exit 20 }
    if ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $sid.Value) { exit 20 }
    $items = @($directory) + @(Get-ChildItem -LiteralPath $root -Force)
    foreach ($item in $items) {
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { exit 20 }
        if ($item.FullName -ne $directory.FullName -and ($item.PSIsContainer -or
            $item.Name -notin @('allocation.sqlite3', 'allocation.sqlite3-journal',
                'allocation.sqlite3-wal', 'allocation.sqlite3-shm'))) { exit 20 }
        $current = Get-Acl -LiteralPath $item.FullName
        $rules = @($current.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
        if ($rules.Count -eq 0) { exit 20 }
        $owner = $current.GetOwner([Security.Principal.SecurityIdentifier]).Value
        if ($owner -notin $allowed) { exit 20 }
        foreach ($rule in $rules) {
            if ($rule.IdentityReference.Value -notin $allowed -or
                $rule.AccessControlType -ne 'Allow' -or
                $rule.FileSystemRights -ne 'FullControl') { exit 20 }
        }
    }
    [Console]::Out.Write('ACL_VERIFIED')
} catch { exit 20 }
"""


def verify_directory(root: Path) -> None:
    if os.name != "nt" or not root.is_absolute():
        raise JournalError("TIMEWEB_JOURNAL_WINDOWS_REQUIRED")
    # Reject existing reparse points in the entire ancestor chain as well.
    for path in (root, *root.parents):
        if path.exists() and getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
            raise JournalError("TIMEWEB_JOURNAL_REPARSE_FORBIDDEN")
    system_root = os.environ.get("SystemRoot", "")
    if not system_root or not Path(system_root).is_absolute():
        raise JournalError("TIMEWEB_JOURNAL_WINDOWS_REQUIRED")
    executable = Path(system_root) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    try:
        result = subprocess.run(
            [str(executable), "-NoProfile", "-NonInteractive", "-Command", _ACL_SCRIPT],
            input=str(root),
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        raise JournalError("TIMEWEB_JOURNAL_ACL_UNPROVEN") from None
    if result.returncode != 0 or result.stdout != "ACL_VERIFIED" or result.stderr:
        raise JournalError("TIMEWEB_JOURNAL_ACL_UNPROVEN")


def open_journal(*, initialize: bool) -> SqliteJournal:
    location = os.environ.get("LOCALAPPDATA", "")
    if os.name != "nt" or not location or not Path(location).is_absolute():
        raise JournalError("TIMEWEB_JOURNAL_WINDOWS_REQUIRED")
    root = Path(location) / "OmniCIO" / "TimewebIpv4AllocationV1"
    workspace = os.environ.get("GITHUB_WORKSPACE", "")
    if workspace and root.resolve().is_relative_to(Path(workspace).resolve()):
        raise JournalError("TIMEWEB_JOURNAL_WORKSPACE_FORBIDDEN")
    missing = not (root / "allocation.sqlite3").is_file()
    if (root.exists() or not initialize) and missing:
        raise JournalError("TIMEWEB_JOURNAL_MISSING_RECONCILIATION_REQUIRED")
    return SqliteJournal(
        root / "allocation.sqlite3",
        verify_location=lambda: verify_directory(root),
        initialize=initialize,
    )
