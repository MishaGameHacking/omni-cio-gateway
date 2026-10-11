"""On-host operator boundary; no real secrets, network or production database."""

from __future__ import annotations

import importlib
import json
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


@pytest.fixture
def capacity_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(host, "ROOT", tmp_path)
    writers = {unit: {"active": unit == host.upgrade.AUTH_SERVICE, "enabled": "enabled"}
               for unit in host.upgrade.WRITER_UNITS}
    monkeypatch.setattr(host.upgrade, "_capture_writer_state", lambda: writers)
    monkeypatch.setattr(host.upgrade, "_unit_state", lambda *_args: "inactive")
    monkeypatch.setattr(host, "atomic_file", lambda path, data: path.write_bytes(data))
    monkeypatch.setattr(host.shutil, "disk_usage", lambda _path: Mock(free=2 * 1024**3))
    return tmp_path / "maintenance.json"


def test_sufficient_capacity_keeps_application_running(capacity_runtime):
    with (
        patch.object(host, "ensure_capacity"),
        patch.object(host.upgrade, "_change_units") as change,
        patch.object(host, "resume_maintenance") as resume,
        host.existing_host_capacity("private", {}, {"source_release": SHA}, "query", {}),
    ):
        pass
    change.assert_not_called()
    resume.assert_not_called()
    assert not capacity_runtime.exists()


@pytest.mark.parametrize("fails_during_restore", [False, True])
def test_low_memory_pause_has_durable_receipt_and_always_resumes(
    capacity_runtime, fails_during_restore,
):
    observation = {}
    calls = []

    def change(command, units):
        assert capacity_runtime.exists()  # Durable intent must precede the first stop.
        calls.append((command, units))

    with (
        patch.object(host, "ensure_capacity", side_effect=[host.recovery.RecoveryBlocked(), None]),
        patch.object(host.upgrade, "_change_units", side_effect=change),
        patch.object(host, "resume_maintenance") as resume,
    ):
        try:
            with host.existing_host_capacity(
                "private", {}, {"source_release": SHA}, "query", observation,
            ) as paused:
                assert paused is True
                observation["stage"] = "temporary_restore"
                if fails_during_restore:
                    raise RuntimeError("private database failure")
        except RuntimeError:
            assert fails_during_restore
    assert calls == [("stop", [host.upgrade.OBSERVER_TIMER, host.upgrade.OBSERVER_SERVICE,
                              host.upgrade.AUTH_SERVICE])]
    resume.assert_called_once_with(
        capacity_runtime, "private", {}, {"source_release": SHA}, "query",
    )
    assert observation["stage"] == "temporary_restore"


def test_disk_shortage_does_not_stop_application(capacity_runtime, monkeypatch):
    monkeypatch.setattr(host.shutil, "disk_usage", lambda _path: Mock(free=1))
    with (
        patch.object(host, "ensure_capacity", side_effect=host.recovery.RecoveryBlocked()),
        patch.object(host.upgrade, "_change_units") as change,
        pytest.raises(host.recovery.RecoveryBlocked),
        host.existing_host_capacity("private", {}, {"source_release": SHA}, "query", {}),
    ):
        pytest.fail("Recovery must remain blocked")
    change.assert_not_called()
    assert not capacity_runtime.exists()


@pytest.mark.parametrize("source_proven", [False, True])
def test_resume_requires_source_proof_and_retains_receipt_on_failure(tmp_path, source_proven):
    path = tmp_path / "maintenance.json"
    receipt = {"schema": 1, "source_release": SHA, "writers": {
        unit: {"active": unit == host.upgrade.AUTH_SERVICE, "enabled": "enabled"}
        for unit in host.upgrade.WRITER_UNITS
    }}
    path.write_text(json.dumps(receipt))
    with (
        patch.object(host.upgrade, "_private_file", return_value=path.read_text()),
        patch.object(
            host.upgrade, "_resume_source_after_failure", return_value=source_proven,
        ) as prove,
    ):
        if source_proven:
            host.resume_maintenance(path, "private", {}, {"source_release": SHA}, "query")
        else:
            with pytest.raises(host.recovery.RecoveryBlocked):
                host.resume_maintenance(path, "private", {}, {"source_release": SHA}, "query")
    prove.assert_called_once_with(
        "private", {}, {"source_release": SHA}, "query", receipt["writers"],
    )
    assert path.exists() is not source_proven


def test_interrupted_maintenance_is_resumed_before_another_capacity_check(capacity_runtime):
    capacity_runtime.write_text("previous maintenance")
    order = []
    with (
        patch.object(host, "resume_maintenance", side_effect=lambda *_args: order.append("resume")),
        patch.object(host, "ensure_capacity", side_effect=lambda: order.append("capacity")),
        host.existing_host_capacity("private", {}, {"source_release": SHA}, "query", {}),
    ):
        order.append("work")
    assert order == ["resume", "capacity", "work"]


def test_failure_report_preserves_stage_without_sql_secrets_or_rows(capsys):
    capacity = {"status": "unavailable", "code": "host_capacity_unavailable"}
    with patch.object(host.upgrade, "inspect_host_capacity", return_value=capacity):
        report = host.failure_report(
            "temporary_restore", RuntimeError("secret DSN; SELECT private"),
        )
    assert host.validate_failure_report(report)
    raw = json.dumps(report)
    with pytest.raises(host.recovery.RecoveryBlocked):
        runner.parse_host_report(raw, {})
    output = capsys.readouterr().out
    assert "temporary_restore" in output
    assert "unexpected_error" in output
    assert "secret" not in output
    assert "SELECT" not in output


@pytest.mark.parametrize("change", [
    {"detail": "secret"}, {"stage": "SQL secret"}, {"error_kind": []},
    {"host_capacity": {"secret": "value"}}, {"status": "recovery_verified"},
])
def test_untrusted_failure_report_is_rejected_without_echo(change, capsys):
    report = {"status": "recovery_failed", "stage": "capacity", "error_kind": "recovery_blocked",
              "host_capacity": {"status": "unavailable", "code": "host_capacity_unavailable"}}
    report.update(change)
    raw = json.dumps(report)
    with pytest.raises(host.recovery.RecoveryBlocked):
        runner.parse_host_report(raw, {})
    assert capsys.readouterr().out == ""


def test_oversized_host_report_is_rejected_without_echo(capsys):
    with pytest.raises(host.recovery.RecoveryBlocked):
        runner.parse_host_report("private" * 3000, {})
    assert capsys.readouterr().out == ""

