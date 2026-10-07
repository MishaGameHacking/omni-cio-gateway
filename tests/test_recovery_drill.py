"""Manual drill authority and independently validated receipt installation."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from omnicio.recovery import sign_recovery_evidence

SCRIPTS = Path(__file__).resolve().parents[1] / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS))
controller = importlib.import_module("timeweb_recovery")
runner = importlib.import_module("run_recovery_drill")
SHA = "a" * 40
KEY = "test-receipt-key-" + "x" * 40


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
        patch.object(runner, "release_context") as release,
        pytest.raises(controller.RecoveryBlocked),
    ):
        runner.authorize()
    release.assert_not_called()


def test_manual_job_still_requires_exact_checkout_and_successful_main_checks(monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("OMNICIO_RESTORE_DRILL_ALLOWED", "true")
    with (
        patch.object(runner, "release_context", return_value=(SHA, "test-token")),
        patch.object(runner, "require_checkout") as checkout,
        patch.object(runner, "wait_for_release") as checks,
    ):
        assert runner.authorize() == (SHA, "test-token")
    checkout.assert_called_once_with(SHA)
    assert checks.call_args.args[1] == SHA


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
            assert KEY not in input_text and "archive_key" not in input_text
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

    with patch.object(controller, "REMOTE_STATUS_PATH", str(target)):
        if success:
            controller.install_restore_receipt(LocalRuntime(), proof, SHA)
        else:
            with pytest.raises(SystemExit):
                controller.install_restore_receipt(LocalRuntime(), proof, SHA)
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
