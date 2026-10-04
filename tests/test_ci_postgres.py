"""The CI database runner must never consume an inherited deployment DSN."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/test_with_postgres.py"


@pytest.mark.parametrize("times_out", [False, True])
def test_ci_uses_own_database_and_always_stops_it(times_out: bool) -> None:
    spec = importlib.util.spec_from_file_location("ci_postgres_runner", SCRIPT)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    server = MagicMock()
    server.get_uri.side_effect = lambda database=None: (
        "postgresql://localhost/" + (database or "postgres")
    )
    factory = MagicMock(return_value=server)
    process = MagicMock(return_value=SimpleNamespace(returncode=0))
    if times_out:
        process.side_effect = subprocess.TimeoutExpired("pytest", 600)
    with (
        patch.object(runner, "sys", SimpleNamespace(platform="win32", executable="python")),
        patch.dict("sys.modules", {"pgserver": SimpleNamespace(get_server=factory)}),
        patch.dict("os.environ", {"OMNICIO_TEST_DATABASE_URL": "must-not-be-used"}),
        patch.object(runner.psycopg, "connect") as connect,
        patch.object(runner.subprocess, "run", process),
    ):
        if times_out:
            with pytest.raises(subprocess.TimeoutExpired):
                runner.main()
        else:
            assert runner.main() == 0

    assert connect.call_args.args == ("postgresql://localhost/postgres",)
    assert process.call_args.kwargs["env"]["OMNICIO_TEST_DATABASE_URL"] == (
        "postgresql://localhost/omnicio_test"
    )
    assert "omnicio-ci-postgres-" in str(factory.call_args.args[0])
    server.cleanup.assert_called_once_with()
