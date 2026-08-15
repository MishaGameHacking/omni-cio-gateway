from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OWNER_APPLY_WRAPPER = (
    ROOT / "infrastructure" / "windows" / "invoke_wp22a_owner_apply_safe.ps1"
)


def test_safe_apply_result_reparse_checks_precede_descendant_creation() -> None:
    source = OWNER_APPLY_WRAPPER.read_text(encoding="utf-8")
    boundary = source[
        source.index("function Set-ProtectedResultRoot") : source.index(
            "function Set-ProtectedResultFileAcl"
        )
    ]

    first_check = boundary.index("foreach ($path in @($omniStateRoot, $resultRoot))")
    creation = boundary.index("New-Item -ItemType Directory -Path $resultRoot -Force")
    second_check = boundary.index(
        "foreach ($path in @($omniStateRoot, $resultRoot))",
        first_check + 1,
    )

    assert first_check < creation < second_check
    assert boundary.count("WP22A_SAFE_RESULT_ROOT_REPARSE_POINT_FORBIDDEN") == 2
    assert boundary.count("[System.IO.FileAttributes]::ReparsePoint") == 2
    assert "if (-not (Test-Path -LiteralPath $path)) { continue }" in boundary


def test_safe_apply_hardens_existing_result_file_before_atomic_replace() -> None:
    source = OWNER_APPLY_WRAPPER.read_text(encoding="utf-8")
    file_acl = source[
        source.index("function Set-ProtectedResultFileAcl") : source.index(
            "function Get-SafeReasonCode"
        )
    ]
    save = source[
        source.index("function Save-SanitizedResult") : source.index(
            "function Write-Summary"
        )
    ]

    assert "WP22A_SAFE_RESULT_FILE_BOUNDARY_INVALID" in file_acl
    assert "WP22A_SAFE_RESULT_FILE_ACL_INVALID" in file_acl
    assert "[System.IO.FileAttributes]::ReparsePoint" in file_acl
    assert "[System.Security.AccessControl.FileSecurity]::new()" in file_acl
    assert "SetAccessRuleProtection($true, $false)" in file_acl
    assert '"S-1-5-18"' in file_acl
    assert '"S-1-5-32-544"' in file_acl
    assert "$unexpected.Count -ne 0" in file_acl

    first_file_acl = save.index("Set-ProtectedResultFileAcl")
    write = save.index("[System.IO.File]::WriteAllText")
    replace = save.index("[System.IO.File]::Replace")
    second_file_acl = save.index("Set-ProtectedResultFileAcl", first_file_acl + 1)
    assert first_file_acl < write < replace < second_file_acl


def test_safe_apply_persists_marker_only_after_result_root_is_protected() -> None:
    source = OWNER_APPLY_WRAPPER.read_text(encoding="utf-8")
    save = source[
        source.index("function Save-SanitizedResult") : source.index(
            "function Write-Summary"
        )
    ]
    marker = source.index('reason = "WP22A_OWNER_APPLY_IN_PROGRESS"')
    child = source.index("& powershell.exe")

    assert save.index("Set-ProtectedResultRoot") < save.index(
        "[System.IO.File]::WriteAllText"
    )
    assert marker < child
    assert "raw_child_output_persisted = $false" in source
    assert "private_url_persisted = $false" in source
