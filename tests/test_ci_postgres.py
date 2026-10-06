"""The CI database runner must never consume an inherited deployment DSN."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/test_with_postgres.py"


@pytest.fixture
def runner():
    spec = importlib.util.spec_from_file_location("ci_postgres_supervisor", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unverified_postgres_archive_is_never_extracted(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("ci_postgres_checksum", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    response = MagicMock(status=200)
    response.read.return_value = b"untrusted executable bytes"
    client = MagicMock()
    client.getresponse.return_value = response
    destination = tmp_path / "postgres"
    with patch.object(runner.http.client, "HTTPSConnection", return_value=client), \
            pytest.raises(RuntimeError, match="checksum mismatch"):
        runner.install_binaries(destination)
    assert not destination.exists()
    client.close.assert_called_once()


@pytest.mark.parametrize("times_out", [False, True])
def test_ci_uses_own_database_and_always_stops_it(tmp_path: Path, times_out: bool) -> None:
    spec = importlib.util.spec_from_file_location("ci_postgres_runner", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    data = tmp_path / "data"
    data.mkdir()
    (data / "postmaster.pid").write_text("fake", encoding="utf-8")

    def run(command: list[str], **kwargs: object) -> int:
        if "pytest" in command and times_out:
            return 124
        return 0

    process = MagicMock(side_effect=run)
    with (
        patch.dict("os.environ", {"OMNICIO_TEST_DATABASE_URL": "must-not-be-used"}),
        patch.object(runner, "available_port", return_value=54321),
        patch.object(runner.psycopg, "connect") as connect,
        patch.object(runner, "_run_native", process),
    ):
        result = runner.run_suite(tmp_path / "bin", tmp_path)
        assert result == (124 if times_out else 0)

    assert connect.call_args.args == ("postgresql://postgres@127.0.0.1:54321/postgres",)
    statements = [
        call.args[0]
        for call in connect.return_value.__enter__.return_value.execute.call_args_list
    ]
    assert statements == [
        "CREATE DATABASE omnicio_test",
        "ALTER DATABASE omnicio_test SET lock_timeout = '15s'",
        "ALTER DATABASE omnicio_test SET statement_timeout = '60s'",
    ]
    invocation = next(call for call in process.call_args_list if "pytest" in call.args[0])
    assert invocation.kwargs["env"]["OMNICIO_TEST_DATABASE_URL"] == (
        "postgresql://postgres@127.0.0.1:54321/omnicio_test"
    )
    expected_binary = str((tmp_path / "bin").resolve())
    assert invocation.kwargs["env"]["OMNICIO_TEST_POSTGRES_BIN"] == expected_binary
    assert invocation.kwargs["timeout"] == 600
    assert process.call_args.args[0][-3:] == ["-m", "fast", "stop"]


def test_oversized_archive_is_rejected_before_extraction(runner, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "MAX_ARCHIVE_BYTES", 3)
    response = MagicMock(status=200)
    response.read.return_value = b"four"
    client = MagicMock()
    client.getresponse.return_value = response
    destination = tmp_path / "postgres"
    with (
        patch.object(runner.http.client, "HTTPSConnection", return_value=client),
        patch.object(runner.zipfile, "ZipFile") as extract,
        pytest.raises(RuntimeError, match="checksum mismatch"),
    ):
        runner.install_binaries(destination)
    response.read.assert_called_once_with(4)
    extract.assert_not_called()
    assert not destination.exists()


@pytest.mark.parametrize("mode, expected", [("success", 0), ("failure", 3), ("timeout", 124)])
def test_supervisor_preserves_output_and_cleans_its_process_and_directory(
    runner, tmp_path, monkeypatch, capsys, mode, expected,
) -> None:
    """Actual child I/O continues during the deadline; inactivity is not the limit."""
    real_popen = subprocess.Popen
    real_terminate = runner._terminate_owned_tree
    children, directories, terminated = [], [], []
    source = (
        "import sys,time\nfrom pathlib import Path\n"
        "root=Path(sys.argv[1])\n(root/'data').mkdir()\n"
        "(root/'data'/'synthetic.dat').write_text('synthetic')\n"
        "(root/'postgres.log').write_text('synthetic PostgreSQL evidence\\n')\n"
        "print('synthetic stdout marker',flush=True)\n"
        "print('synthetic stderr marker',file=sys.stderr,flush=True)\n"
    )
    if mode == "timeout":
        source += "for _ in range(400):\n print('progress',flush=True)\n time.sleep(0.05)\n"
    else:
        source += f"sys.exit({expected})\n"

    def create_directory(*, prefix):
        directory = tempfile.mkdtemp(prefix=prefix, dir=tmp_path)
        directories.append(Path(directory))
        return directory

    def start(command, **kwargs):
        if "--worker" in command:
            process = real_popen([sys.executable, "-u", "-c", source, command[-1]], **kwargs)
            children.append(process)
            return process
        return real_popen(command, **kwargs)

    def terminate(process):
        terminated.append(process.pid)
        if sys.platform == "win32":
            return real_terminate(process)
        # Only the supervisor's real test child exists on the local POSIX executor.
        # The Windows CI run above exercises the actual scoped taskkill command.
        process.kill()
        process.wait(timeout=5)
        return True

    monkeypatch.setattr(runner, "mkdtemp", create_directory)
    monkeypatch.setattr(runner.subprocess, "Popen", start)
    monkeypatch.setattr(runner, "_terminate_owned_tree", terminate)
    destination = tmp_path / "artifacts"
    result = runner._supervise_worker(destination, timeout=2)
    assert result == expected
    assert len(children) == 1
    assert children[0].poll() is not None
    assert not directories[0].exists()
    output = (destination / runner.WORKER_LOG).read_text()
    assert "synthetic stdout marker" in output
    assert "synthetic stderr marker" in output
    assert (destination / runner.POSTGRES_LOG).read_text() == "synthetic PostgreSQL evidence\n"
    console = capsys.readouterr().out
    assert "synthetic stdout marker" in console
    if mode == "timeout":
        assert terminated == [children[0].pid]
        assert "progress" in output
        assert "exceeded its 2s deadline" in console
    else:
        assert terminated == []


def test_tree_cleanup_is_scoped_to_the_owned_live_pid(runner, monkeypatch) -> None:
    process = MagicMock(pid=45678)
    process.poll.return_value = None
    monkeypatch.setenv("SYSTEMROOT", r"C:\Windows")
    with patch.object(runner.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as stop:
        assert runner._terminate_owned_tree(process) is True
    expected = str(Path(os.environ["SYSTEMROOT"]) / "System32" / "taskkill.exe")
    assert stop.call_args.args[0] == [expected, "/PID", "45678", "/T", "/F"]
    assert stop.call_count == 1
    assert stop.call_args.kwargs["timeout"] == 10
    process.wait.assert_called_once_with(timeout=5)
    process.kill.assert_not_called()


def test_finished_pid_is_never_killed_again(runner) -> None:
    process = MagicMock(pid=45678)
    process.poll.return_value = 0
    with patch.object(runner.subprocess, "run") as stop:
        assert runner._terminate_owned_tree(process) is True
    stop.assert_not_called()


def test_tree_cleanup_timeout_is_reported_without_reusing_pid(runner) -> None:
    process = MagicMock(pid=45678)
    process.poll.return_value = None
    with patch.object(
        runner.subprocess, "run", side_effect=subprocess.TimeoutExpired("taskkill", 10),
    ) as stop:
        assert runner._terminate_owned_tree(process) is False
    assert stop.call_count == 1
    process.kill.assert_not_called()
    process.wait.assert_not_called()


@pytest.mark.parametrize("check", [False, True])
def test_native_timeout_stops_the_child_tree_and_remains_a_failure(runner, check) -> None:
    command = ["synthetic-native-process"]
    process = MagicMock()
    process.wait.side_effect = subprocess.TimeoutExpired(command, 60)
    with (
        patch.object(runner.subprocess, "Popen", return_value=process),
        patch.object(runner, "_terminate_owned_tree", return_value=True) as stop,
    ):
        if check:
            with pytest.raises(subprocess.CalledProcessError) as failure:
                runner._run_native(command, timeout=60)
            assert failure.value.returncode == 124
        else:
            assert runner._run_native(command, timeout=60, check=False) == 124
    stop.assert_called_once_with(process)


def test_detached_postgres_is_stopped_by_its_exact_data_directory(
    runner, tmp_path, monkeypatch,
) -> None:
    directory = tmp_path / "owned"
    data = directory / "data"
    data.mkdir(parents=True)
    (data / "postmaster.pid").write_text("synthetic pid\n")
    (directory / runner.POSTGRES_LOG).write_text("synthetic PostgreSQL log\n")
    output = tmp_path / runner.WORKER_LOG
    real_popen = subprocess.Popen
    commands = []

    def start(command, **kwargs):
        commands.append(command)
        if command[0].endswith("pg_ctl.exe"):
            return MagicMock(wait=MagicMock(return_value=0))
        return real_popen(command, **kwargs)

    monkeypatch.setattr(runner.subprocess, "Popen", start)
    assert runner._cleanup_directory(directory, output) is True
    control = directory / "postgres" / "bin" / "pg_ctl.exe"
    assert commands[0] == [str(control), "-D", str(data), "status"]
    assert commands[1] == [str(control), "-D", str(data), "-w", "-t", "10", "-m", "fast", "stop"]
    assert commands[2][-1] == str(directory)
    assert not directory.exists()


@pytest.mark.parametrize("status, cleaned", [(3, True), (4, False)])
def test_cleanup_accepts_only_confirmed_absent_postgres(
    runner, tmp_path, monkeypatch, status, cleaned,
) -> None:
    directory = tmp_path / "owned"
    data = directory / "data"
    data.mkdir(parents=True)
    (data / "postmaster.pid").write_text("stale synthetic pid\n")
    real_popen = subprocess.Popen
    commands = []

    def start(command, **kwargs):
        commands.append(command)
        if command[0].endswith("pg_ctl.exe"):
            return MagicMock(wait=MagicMock(return_value=status))
        return real_popen(command, **kwargs)

    monkeypatch.setattr(runner.subprocess, "Popen", start)
    assert runner._cleanup_directory(directory, tmp_path / runner.WORKER_LOG) is cleaned
    assert commands[0][-1] == "status"
    assert len(commands) == (2 if cleaned else 1)
    assert directory.exists() is not cleaned


def test_artifact_and_console_output_are_bounded(runner, tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(runner, "MAX_WORKER_LOG_BYTES", 64)
    monkeypatch.setattr(runner, "MAX_LOG_TAIL_BYTES", 16)
    source, destination = tmp_path / "source", tmp_path / "artifact"
    source.mkdir()
    destination.mkdir()
    (source / runner.WORKER_LOG).write_bytes(b"x" * 128 + b"worker-end\n")
    (source / runner.POSTGRES_LOG).write_bytes(b"x" * 128 + b"pg-end\n")
    runner._preserve_evidence(source, destination)
    assert (destination / runner.WORKER_LOG).stat().st_size == 64
    assert (destination / runner.POSTGRES_LOG).stat().st_size == 16
    capsys.readouterr()
    runner._emit_evidence(destination)
    console = capsys.readouterr().out
    assert "worker-end" in console
    assert "pg-end" in console
    assert "x" * 16 not in console
