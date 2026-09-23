from __future__ import annotations

from pathlib import Path

import pytest

from omni_cio.web.broker_vault_v1 import (
    READ_CONNECTION_MARKER,
    READ_CONNECTION_MARKER_VALUE,
    ReadBrokerConnectionVaultV1,
    ReadConnectionVaultError,
    new_read_connection_secret_ref,
)


ROOT = Path(__file__).resolve().parents[1]
ACL_PROVISIONER = (
    ROOT / "infrastructure" / "windows" / "provision_wp17_web_read_vault.ps1"
)
OWNER_EVIDENCE_FINALIZER = (
    ROOT / "infrastructure" / "windows" / "finalize_wp17_web_read_vault_evidence.ps1"
)
RUNNER_AUDITOR = (
    ROOT / "infrastructure" / "windows" / "audit_wp17_read_vault_runner.ps1"
)
OWNER_AUDIT_WORKFLOW = (
    ROOT / ".github" / "workflows" / "v10-wp17-owner-read-vault-audit.yml"
)


def fake_protect(payload: bytes) -> bytes:
    return b"P:" + payload[::-1]


def fake_unprotect(payload: bytes) -> bytes:
    assert payload.startswith(b"P:")
    return payload[2:][::-1]


def ready_root(tmp_path: Path) -> Path:
    root = tmp_path / "connections"
    root.mkdir()
    (root / READ_CONNECTION_MARKER).write_text(
        READ_CONNECTION_MARKER_VALUE,
        encoding="ascii",
    )
    return root


def test_vault_round_trip_rotate_and_revoke_are_secret_ref_scoped(
    tmp_path: Path,
) -> None:
    root = ready_root(tmp_path)
    vault = ReadBrokerConnectionVaultV1(
        root=root,
        protect=fake_protect,
        unprotect=fake_unprotect,
    )
    first = new_read_connection_secret_ref()
    second = new_read_connection_secret_ref()

    vault.store(secret_ref=first, token="read-token-a")
    vault.store(secret_ref=second, token="read-token-b")
    assert vault.load(secret_ref=first) == "read-token-a"
    assert vault.load(secret_ref=second) == "read-token-b"

    vault.store(secret_ref=first, token="rotated-read-token-a")
    assert vault.load(secret_ref=first) == "rotated-read-token-a"
    assert vault.load(secret_ref=second) == "read-token-b"

    assert vault.revoke(secret_ref=first) is True
    assert vault.revoke(secret_ref=first) is False
    assert vault.load(secret_ref=second) == "read-token-b"


def test_vault_rejects_path_traversal_and_unprovisioned_root(tmp_path: Path) -> None:
    missing = ReadBrokerConnectionVaultV1(
        root=tmp_path / "missing",
        protect=fake_protect,
        unprotect=fake_unprotect,
    )
    with pytest.raises(ReadConnectionVaultError, match="NOT_PROVISIONED"):
        missing.store(secret_ref=new_read_connection_secret_ref(), token="read-token")

    root = ready_root(tmp_path)
    vault = ReadBrokerConnectionVaultV1(
        root=root,
        protect=fake_protect,
        unprotect=fake_unprotect,
    )
    invalid_ref = "../.." + "/broker_trading"
    with pytest.raises(ReadConnectionVaultError, match="SECRET_REF_INVALID"):
        vault.store(secret_ref=invalid_ref, token="read-token")


def test_vault_requires_exact_owner_marker(tmp_path: Path) -> None:
    root = tmp_path / "connections"
    root.mkdir()
    vault = ReadBrokerConnectionVaultV1(
        root=root,
        protect=fake_protect,
        unprotect=fake_unprotect,
    )
    with pytest.raises(ReadConnectionVaultError, match="MARKER_MISSING"):
        vault.store(secret_ref=new_read_connection_secret_ref(), token="read-token")

    (root / READ_CONNECTION_MARKER).write_text("wrong", encoding="ascii")
    with pytest.raises(ReadConnectionVaultError, match="MARKER_INVALID"):
        vault.store(secret_ref=new_read_connection_secret_ref(), token="read-token")


def test_acl_verifier_normalizes_identity_references_to_sid() -> None:
    source = ACL_PROVISIONER.read_text(encoding="utf-8")

    assert "function Resolve-IdentitySid" in source
    assert (
        "$IdentityReference.Translate([System.Security.Principal.SecurityIdentifier])"
        in source
    )
    assert "$ruleSid.Value -eq $RuntimeSid.Value" in source
    assert "$ruleSid.Value -eq $RunnerSid.Value" in source
    assert "IdentityReference -eq $RuntimeSid" not in source
    assert "IdentityReference -eq $RunnerSid" not in source
    for broad_sid in ("S-1-1-0", "S-1-5-11", "S-1-5-32-545"):
        assert broad_sid in source


def test_owner_acl_evidence_is_exact_head_bound_and_runner_verified() -> None:
    finalizer = OWNER_EVIDENCE_FINALIZER.read_text(encoding="utf-8")
    auditor = RUNNER_AUDITOR.read_text(encoding="utf-8")
    workflow = OWNER_AUDIT_WORKFLOW.read_text(encoding="utf-8")

    for marker in (
        "owner-read-vault-evidence.sanitized.local.json",
        "implementation_sha",
        "provisioner_sha256",
        "evidence_finalizer_sha256",
        "status --porcelain",
        "runner_evidence_write_allowed",
    ):
        assert marker in finalizer
    assert "SetAccessRuleProtection($true, $false)" in finalizer
    assert "ReadAndExecute" in finalizer

    for marker in (
        "ExpectedImplementationSha",
        "implementation_bound",
        "script_hashes_bound",
        "runner_secret_read_allowed",
        "runner_secret_write_allowed",
        "runner_evidence_write_allowed",
        "Test-ReadDataDenied",
        "Test-CreateDenied",
        "runner_is_administrator",
        "permission_probes_executed",
    ):
        assert marker in auditor

    for reason in (
        "WP17_OWNER_EVIDENCE_HEAD_DRIFT",
        "WP17_OWNER_EVIDENCE_SCRIPT_DRIFT",
        "WP17_RUNNER_SECRET_READ_NOT_DENIED",
        "WP17_RUNNER_SECRET_WRITE_NOT_DENIED",
        "WP17_RUNNER_EVIDENCE_WRITE_NOT_DENIED",
    ):
        assert reason in auditor

    assert "audit_wp17_read_vault_runner.ps1" in workflow
    assert "-ExpectedImplementationSha" in workflow
    assert "github.event.pull_request.head.sha || github.sha" in workflow
    assert (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in workflow
    )
