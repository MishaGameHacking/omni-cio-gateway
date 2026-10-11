"""On-host operator boundary; no real secrets, network or production database."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".github/scripts"))
host = importlib.import_module("host_recovery")
runner = importlib.import_module("run_recovery_drill")
tenant = importlib.import_module("tenant_archive")
SHA = "a" * 40


@pytest.mark.parametrize(
    "event,ref,allowed",
    [
        ("push", "refs/heads/main", "true"),
        ("workflow_dispatch", "refs/heads/work", "true"),
        ("workflow_dispatch", "refs/heads/main", "false"),
    ],
)
def test_host_recovery_requires_manual_main_before_reading_credentials(
    monkeypatch, event, ref, allowed
):
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.setenv("GITHUB_REF", ref)
    monkeypatch.setenv("OMNICIO_RESTORE_DRILL_ALLOWED", allowed)
    with (
        patch.object(runner, "release_context") as release,
        pytest.raises(host.recovery.RecoveryBlocked),
    ):
        runner.authorize_host()
    release.assert_not_called()


def test_host_recovery_requires_exact_main_gate(monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("OMNICIO_RESTORE_DRILL_ALLOWED", "true")
    with (
        patch.object(runner, "release_context", return_value=(SHA, "token")),
        patch.object(runner, "require_checkout") as checkout,
        patch.object(runner, "wait_for_main_release") as gates,
    ):
        assert runner.authorize_host() == (SHA, "token")
    checkout.assert_called_once_with(SHA)
    gates.assert_called_once_with(SHA, "token", timeout=600)


def test_host_program_is_self_contained_and_has_no_operator_secret_values(monkeypatch):
    monkeypatch.setenv("OMNICIO_RESTORE_ARCHIVE_KEY", "must-not-travel")
    monkeypatch.setenv("DATABASE_URL", "must-not-travel-either")
    code = runner.host_program({"release_sha": SHA})
    compile(code, "<accepted-host-program>", "exec")
    assert "must-not-travel" not in code
    assert "from host_recovery import recover" in code
    assert "shutil.rmtree(work)" in code


def test_missing_keys_created_together_and_existing_keys_not_rotated(monkeypatch, tmp_path):
    monkeypatch.setattr(host, "ROOT", tmp_path)
    original = "EXISTING_SETTING=value\n"
    with (
        patch.object(host.upgrade, "_private_file", return_value=original),
        patch.object(host, "atomic_file") as write,
    ):
        signing, archive = host.ensure_keys()
    Fernet(archive)
    assert len(signing) >= 32
    contents = write.call_args.args[1].decode()
    assert contents.startswith(original)
    with (
        patch.object(host.upgrade, "_private_file", return_value=contents),
        patch.object(host, "atomic_file") as write,
    ):
        assert host.ensure_keys() == (signing, archive)
    write.assert_not_called()


@pytest.mark.parametrize("existing", ["incomplete-key", "orphan-archive"])
def test_existing_custody_is_never_replaced_to_make_backup_work(monkeypatch, tmp_path, existing):
    monkeypatch.setattr(host, "ROOT", tmp_path)
    contents = "OMNICIO_RESTORE_RECEIPT_KEY=existing\n" if existing == "incomplete-key" else ""
    if existing == "orphan-archive":
        (tmp_path / "database.dump.encrypted").write_bytes(b"existing encrypted data")
    with (
        patch.object(host.upgrade, "_private_file", return_value=contents),
        patch.object(host, "atomic_file") as write,
        pytest.raises(host.recovery.RecoveryBlocked),
    ):
        host.ensure_keys()
    write.assert_not_called()


@pytest.mark.parametrize("qualifier,forced", [("true", True), (tenant.TENANT_QUAL, False)])
def test_non_exhaustive_tenant_policy_is_rejected(qualifier, forced):
    source = Mock()
    source.execute.return_value.fetchone.return_value = (False,)
    source.execute.return_value.fetchall.return_value = [("00000000-0000-0000-0000-000000000001",)]
    with (
        patch.object(
            tenant.contract,
            "database_guards",
            return_value=[
                ("positions", True, forced, "policy", qualifier, qualifier),
            ],
        ),
        pytest.raises(host.recovery.RecoveryBlocked),
    ):
        tenant.tenant_partition(source)


def test_existing_destination_is_not_a_restore_target(tmp_path):
    key = Fernet.generate_key().decode()
    with (
        patch("psycopg.connect") as connect,
        pytest.raises(host.recovery.RecoveryBlocked, match="loopback"),
    ):
        tenant.export_tenant_archive(
            "not-opened",
            "postgresql://user@10.0.0.5/postgres",
            tmp_path,
            cluster_id=4215095,
            source_release=SHA,
            signing_key="x" * 40,
            archive_key=key,
        )
    connect.assert_not_called()


def test_atomic_evidence_refuses_link_destination(tmp_path):
    other = tmp_path / "other"
    other.write_bytes(b"keep")
    link = tmp_path / "archive"
    link.symlink_to(other)
    with pytest.raises(host.recovery.RecoveryBlocked):
        host.atomic_file(link, b"replace")
    assert other.read_bytes() == b"keep"
