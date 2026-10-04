"""The CI database runner must never consume an inherited deployment DSN."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/test_with_postgres.py"


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

    def run(command: list[str], **kwargs: object) -> SimpleNamespace:
        if "pytest" in command and times_out:
            raise subprocess.TimeoutExpired(command, 600)
        return SimpleNamespace(returncode=0)

    process = MagicMock(side_effect=run)
    with (
        patch.dict("os.environ", {"OMNICIO_TEST_DATABASE_URL": "must-not-be-used"}),
        patch.object(runner, "available_port", return_value=54321),
        patch.object(runner.psycopg, "connect") as connect,
        patch.object(runner.subprocess, "run", process),
    ):
        if times_out:
            with pytest.raises(subprocess.TimeoutExpired):
                runner.run_suite(tmp_path / "bin", tmp_path)
        else:
            assert runner.run_suite(tmp_path / "bin", tmp_path) == 0

    assert connect.call_args.args == ("postgresql://postgres@127.0.0.1:54321/postgres",)
    invocation = next(call for call in process.call_args_list if "pytest" in call.args[0])
    assert invocation.kwargs["env"]["OMNICIO_TEST_DATABASE_URL"] == (
        "postgresql://postgres@127.0.0.1:54321/omnicio_test"
    )
    expected_binary = str((tmp_path / "bin").resolve())
    assert invocation.kwargs["env"]["OMNICIO_TEST_POSTGRES_BIN"] == expected_binary
    assert process.call_args.args[0][-3:] == ["-m", "fast", "stop"]
