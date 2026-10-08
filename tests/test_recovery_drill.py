"""Manual drill authority and independently validated receipt installation."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import runpy
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from cryptography.fernet import Fernet
from psycopg.conninfo import make_conninfo

from omnicio.recovery import sign_recovery_evidence

SCRIPTS = Path(__file__).resolve().parents[1] / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS))
controller = importlib.import_module("timeweb_recovery")
runner = importlib.import_module("run_recovery_drill")
upgrade = importlib.import_module("inplace_upgrade")
SHA = "a" * 40
KEY = "test-receipt-key-" + "x" * 40


def test_remote_upgrade_refuses_non_linux_before_runtime_io(monkeypatch):
    monkeypatch.setattr(upgrade.sys, "platform", "win32")
    with patch.object(upgrade, "_private_file") as read, \
            patch.object(upgrade, "_receipt_directory") as directory:
        with pytest.raises(upgrade.UpgradeBlocked, match="upgrade_requires_linux"):
            upgrade.remote_main({})
        with pytest.raises(upgrade.UpgradeBlocked, match="upgrade_requires_linux"):
            upgrade._write_receipt({})
        operation = upgrade._operation_lock()
        with pytest.raises(upgrade.UpgradeBlocked, match="upgrade_requires_linux"), operation:
            pass
    read.assert_not_called()
    directory.assert_not_called()


@pytest.mark.parametrize("runtime_password,stored_password,host", [
    ("synthetic-password", "synthetic-password", "10.0.0.5"),
    (None, None, "10.0.0.5"), (None, "synthetic-password", "10.0.0.5"),
    ("synthetic-password", "other-password", "10.0.0.5"),
    ("synthetic-password", "synthetic-password", "10.0.0.6"),
])
def test_upgrade_requires_explicit_existing_database_credentials(
    monkeypatch, runtime_password, stored_password, host,
):
    expected = {"host": "10.0.0.5", "port": 5432, "database": "omnicio", "user": "omnicio_app"}
    dsn = make_conninfo(host=host, port=5432, dbname="omnicio", user="omnicio_app",
                        password=runtime_password)
    keys = "CLIENT_IP_KEY=synthetic-ip\nBROKER_TOKEN_CRYPTO_KEY=synthetic-broker\n"
    keys += "VKID_FLOW_CRYPTO_KEY=synthetic-flow\n"
    environment = "DATABASE_URL=" + dsn + "\n" + keys
    secrets_file = keys + ("OMNICIO_DB_ADMIN_PASSWORD=" + stored_password + "\n"
                           if stored_password is not None else "")
    monkeypatch.setattr(upgrade, "_private_file", lambda path, _maximum:
                        environment if path.name == "runtime.env" else secrets_file)
    if runtime_password and runtime_password == stored_password and host == expected["host"]:
        assert upgrade._database_url(expected) == dsn
    else:
        with pytest.raises(upgrade.UpgradeBlocked, match="runtime_database_"):
            upgrade._database_url(expected)


def test_upgrade_receipt_keeps_actual_installation_trusted_after_failed_deploy(
    monkeypatch, tmp_path,
):
    plan = upgrade.load_plan()
    source = "READINESS_QUERY = 'SELECT true'\n"
    plan = plan | {"source_schema_sha256": upgrade._digest(source)}
    baseline = tmp_path / plan["source_release"] / "src/omnicio/schema.py"
    baseline.parent.mkdir(parents=True)
    baseline.write_text(source, encoding="utf-8")
    monkeypatch.setattr(upgrade, "RELEASE_ROOT", tmp_path)
    identity = upgrade.operation_identity(plan, {"database": "synthetic"})
    receipt = {"identity": identity, "phase": "completed", "release_sha": "b" * 40,
               "installed_release": "a" * 40}
    for current, saved, succeeds in (
        (plan["source_release"], None, True), ("a" * 40, None, False),
        ("a" * 40, receipt, True), ("c" * 40, receipt, False),
    ):
        selected = Mock(resolve=Mock(return_value=tmp_path / current))
        monkeypatch.setattr(upgrade, "CURRENT_RELEASE", selected)
        version = "1.2.0" if current == plan["source_release"] else "1.3.0"
        monkeypatch.setattr("importlib.metadata.version", lambda _package, value=version: value)
        upgrade.validate_receipt(saved, identity)
        if succeeds:
            assert upgrade._existing_installation(plan, saved, "b" * 40) == ("SELECT true", current)
        else:
            with pytest.raises(upgrade.UpgradeBlocked, match="source_release_mismatch"):
                upgrade._existing_installation(plan, saved, "b" * 40)
    for changes in ({"identity": {}}, {"installed_release": []}, {"phase": "unknown"}):
        with pytest.raises(upgrade.UpgradeBlocked, match="upgrade_receipt_mismatch"):
            upgrade.validate_receipt(receipt | changes, identity)


def receipt(**changes):
    now = datetime.now(UTC) - timedelta(seconds=1)
    return sign_recovery_evidence(
        {
            "kind": "logical_restore_v1",
            "source_kind": "runtime_pg_dump",
            "cluster_id": 4215095,
            "release_sha": SHA,
            "source_at": (now - timedelta(minutes=1)).isoformat(),
            "verified_at": now.isoformat(),
            "source_system_id": "100",
            "target_system_id": "200",
            "archive_sha256": "b" * 64,
            "duration_seconds": 5,
            "checks": dict.fromkeys(
                ("content", "schema", "foreign_keys", "tenant_isolation"), True
            ),
            **changes,
        },
        KEY,
    )


@pytest.mark.parametrize(
    "event,allowed", [("push", "true"), ("schedule", "true"), ("workflow_dispatch", "false")]
)
def test_restore_job_cannot_run_without_explicit_manual_input(monkeypatch, event, allowed):
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.setenv("OMNICIO_RESTORE_DRILL_ALLOWED", allowed)
    with (
        patch.object(runner, "load_policy",
                     return_value=replace(runner.load_policy(), mode="managed_backups")),
        patch.object(runner, "release_context") as release,
        pytest.raises(controller.RecoveryBlocked),
    ):
        runner.authorize()
    release.assert_not_called()


def test_manual_job_still_requires_exact_checkout_and_successful_main_checks(monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("OMNICIO_RESTORE_DRILL_ALLOWED", "true")
    with (
        patch.object(runner, "load_policy",
                     return_value=replace(runner.load_policy(), mode="managed_backups")),
        patch.object(runner, "release_context", return_value=(SHA, "test-token")),
        patch.object(runner, "require_checkout") as checkout,
        patch.object(runner, "wait_for_release") as checks,
    ):
        assert runner.authorize() == (SHA, "test-token")
    checkout.assert_called_once_with(SHA)
    assert checks.call_args.args[1] == SHA


def test_single_database_policy_blocks_even_manual_export_before_any_io(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("OMNICIO_RESTORE_DRILL_ALLOWED", "true")
    archive_key = Fernet.generate_key().decode()
    with patch.object(runner, "release_context") as release, \
            patch("psycopg.connect") as connect, \
            patch.object(controller, "restore_artifact_path") as destination:
        with pytest.raises(controller.RecoveryBlocked, match="single-database policy"):
            runner.authorize()
        with pytest.raises(controller.RecoveryBlocked, match="single-database policy"):
            controller.export_logical_archive(
                "never-opened-source", tmp_path, cluster_id=4215095, release_sha=SHA,
                signing_key=KEY, archive_key=archive_key,
            )
    release.assert_not_called()
    connect.assert_not_called()
    destination.assert_not_called()


@pytest.mark.parametrize(
    "changes",
    [
        {"release_sha": "b" * 40},
        {"cluster_id": 42},
        {"target_system_id": "100"},
        {"checks": {"content": True}},
    ],
)
def test_invalid_receipt_never_touches_runtime(monkeypatch, changes):
    monkeypatch.setenv("OMNICIO_RESTORE_RECEIPT_KEY", KEY)
    remote = Mock()
    proof = receipt(**changes)
    with pytest.raises(controller.RecoveryBlocked):
        controller.install_restore_receipt(remote, proof, SHA)
    remote.run.assert_not_called()


@pytest.mark.parametrize(
    "runtime_key,release,success",
    [(KEY, SHA, True), ("wrong-runtime-key" * 3, SHA, False), (KEY, "c" * 40, False)],
)
def test_remote_runtime_independently_verifies_and_preserves_physical_receipts(
    monkeypatch,
    tmp_path,
    runtime_key,
    release,
    success,
):
    monkeypatch.setenv("OMNICIO_RESTORE_RECEIPT_KEY", KEY)
    target = tmp_path / "status.json"
    initial = {
        "schema_version": 1,
        "cluster_id": 4215095,
        "release_copy": {"id": 123},
        "provider_status": "ok",
        "logical_rows": "never-present",
    }
    target.write_text(json.dumps(initial))
    proof = receipt()

    class LocalRuntime:
        def run(self, command, *, input_text):
            assert "/etc/omnicio/product.env" in command
            assert KEY not in input_text
            assert "archive_key" not in input_text
            script = input_text.replace(
                "pathlib.Path('/opt/omnicio/current').resolve().name",
                repr(release),
            )
            output = io.StringIO()
            with (
                contextlib.ExitStack() as native,
                patch.dict(os.environ, {"OMNICIO_RESTORE_RECEIPT_KEY": runtime_key}),
                contextlib.redirect_stdout(output),
            ):
                if os.name == "nt":
                    # The deployed runtime is Linux. Windows cannot open/fsync
                    # a directory, so substitute only that kernel boundary;
                    # file writes, atomic replacement, signatures and readback
                    # still execute against real temporary files.
                    probe = tmp_path / "directory-sync-probe"
                    probe.touch()
                    open_file = os.open

                    def open_directory(path, flags):
                        assert Path(path) == target.parent
                        assert flags == os.O_RDONLY | os.O_DIRECTORY
                        return open_file(probe, os.O_RDWR)

                    native.enter_context(patch.object(os, "O_DIRECTORY", 0x100000, create=True))
                    native.enter_context(patch.object(os, "open", open_directory))
                exec(compile(script, "<synthetic-runtime-receipt>", "exec"), {})
            return output.getvalue()

    runtime = LocalRuntime()
    with patch.object(controller, "REMOTE_STATUS_PATH", str(target)):
        if success:
            controller.install_restore_receipt(runtime, proof, SHA)
        else:
            with pytest.raises(SystemExit):
                controller.install_restore_receipt(runtime, proof, SHA)
    restored = json.loads(target.read_text())
    if success:
        assert restored == {**initial, "restore_verification": proof}
    else:
        assert restored == initial


def test_native_child_does_not_inherit_production_credentials(monkeypatch):
    monkeypatch.setenv("OMNICIO_RESTORE_SOURCE_DSN", "private-source-credential")
    monkeypatch.setenv("OMNICIO_RESTORE_ARCHIVE_KEY", "private-key")
    with patch.object(
        runner.subprocess, "Popen", return_value=Mock(wait=Mock(return_value=0))
    ) as proc:
        runner.native(["owned-pg_ctl", "start"], timeout=1)
    assert "OMNICIO_RESTORE_SOURCE_DSN" not in proc.call_args.kwargs["env"]
    assert "OMNICIO_RESTORE_ARCHIVE_KEY" not in proc.call_args.kwargs["env"]
    for channel in ("stdin", "stdout", "stderr"):
        assert proc.call_args.kwargs[channel] == runner.subprocess.DEVNULL


@pytest.mark.parametrize("name", ["../outside", "/absolute-output", r"..\outside",
                                  "nested/manifest.json", "unexpected.json"])
def test_restore_artifact_names_cannot_select_paths(monkeypatch, tmp_path, name):
    monkeypatch.setattr(controller, "RESTORE_ROOT", tmp_path)
    with pytest.raises(controller.RecoveryBlocked, match="Unexpected restore artifact"):
        controller._private_json(name, {})
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("arguments", [
    ["--directory", "../outside"], ["--postgres-bin", "/unreviewed/binaries"],
    ["--cleanup-artifact", "../outside"],
])
def test_restore_runner_rejects_paths_before_authorization_or_io(monkeypatch, arguments):
    monkeypatch.setattr(sys, "argv", ["run_recovery_drill.py", *arguments])
    monkeypatch.setattr(sys, "platform", "win32")
    with patch.object(runner, "authorize") as authorize, \
            patch.object(runner, "export_logical_archive") as export, \
            pytest.raises(controller.RecoveryBlocked):
        runner.main()
    authorize.assert_not_called()
    export.assert_not_called()


def test_retired_restore_cli_cannot_write_caller_destination(monkeypatch, tmp_path):
    outside = tmp_path / "unreviewed-output"
    script = str(SCRIPTS / "timeweb_recovery.py")
    monkeypatch.setattr(sys, "argv", [script, "export-logical", "--directory", str(outside),
                                     "--postgres-bin", str(tmp_path)])
    with pytest.raises(SystemExit, match="standalone paths are refused"):
        runpy.run_path(script, run_name="__main__")
    assert not outside.exists()


@pytest.mark.parametrize("linked_component", ["artifacts", "restore"])
def test_restore_rejects_symlink_or_junction_before_database_process_and_cleanup(
    monkeypatch, tmp_path, linked_component,
):
    root, outside = tmp_path / "checkout", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    marker = outside / "must-remain"
    marker.write_bytes(b"outside-owned-restore-area")
    link = root / "artifacts"
    if linked_component == "restore":
        link.mkdir()
        link = link / "restore"
    if os.name == "nt":
        # Directory junctions need no symlink privilege on the native Windows CI.
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                       check=True, capture_output=True, timeout=5)
    else:
        link.symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(controller, "RESTORE_ROOT", root)
    monkeypatch.setattr(sys, "argv", ["run_recovery_drill.py", "--cleanup-artifact"])
    archive_key = Fernet.generate_key().decode()
    with patch.object(controller, "load_policy",
                      return_value=replace(controller.load_policy(), mode="managed_backups")), \
            patch("psycopg.connect") as database, \
            patch.object(controller, "_postgres_process") as process:
        with pytest.raises(controller.RecoveryBlocked, match="link or escapes"):
            controller.export_logical_archive(
                "never-opened-source", tmp_path, cluster_id=4215095, release_sha=SHA,
                signing_key=KEY, archive_key=archive_key,
            )
        with pytest.raises(controller.RecoveryBlocked, match="link or escapes"):
            runner.main()
    database.assert_not_called()
    process.assert_not_called()
    assert marker.read_bytes() == b"outside-owned-restore-area"
    assert len(list(outside.iterdir())) == 1


def test_fixed_restore_cleanup_preserves_neighboring_artifacts(monkeypatch, tmp_path):
    monkeypatch.setattr(controller, "RESTORE_ROOT", tmp_path)
    destination = controller.restore_artifact_path()
    destination.mkdir(parents=True)
    neighbor = destination.parent / "unrelated.txt"
    neighbor.write_text("preserve", encoding="utf-8")
    controller._private_json("manifest.json", {"test": "owned"})
    assert json.loads(controller.restore_artifact_path("manifest.json").read_text()) == {
        "test": "owned",
    }
    monkeypatch.setattr(sys, "argv", ["run_recovery_drill.py", "--cleanup-artifact"])
    assert runner.main() == 0
    assert not destination.exists()
    assert neighbor.read_text(encoding="utf-8") == "preserve"
