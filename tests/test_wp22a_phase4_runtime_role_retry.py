from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

from scripts import provision_v10_render_neon_preview as provisioner
from scripts import rehearse_v10_wp22a_phase4_runtime_role as rehearsal


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "v10-phase4-free-preview-deploy.yml"


class _Result:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class _RuntimeRoleConnection:
    def __init__(
        self,
        existing: tuple[object, ...] | None,
        *,
        membership_count: int = 0,
    ) -> None:
        self.existing = existing
        self.membership_count = membership_count
        self.mutations: list[Any] = []

    def execute(
        self,
        query: Any,
        params: tuple[object, ...] | None = None,
    ) -> _Result:
        del params
        if isinstance(query, str) and query.startswith("SELECT rolsuper"):
            return _Result(self.existing)
        if isinstance(query, str) and query.startswith("SELECT count(*)"):
            return _Result((self.membership_count,))
        self.mutations.append(query)
        return _Result(None)


def test_existing_safe_runtime_role_rotates_without_privileged_attribute_restate() -> None:
    connection = _RuntimeRoleConnection((False, False, False, False, False))

    provisioner._converge_runtime_role(connection, "test-runtime-password")

    assert len(connection.mutations) == 1
    source = inspect.getsource(provisioner._converge_runtime_role)
    assert 'sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}")' in source
    assert '"ALTER ROLE {} WITH LOGIN NOSUPERUSER' not in source
    assert '"ALTER ROLE {} WITH LOGIN NOCREATEDB' not in source
    assert '"ALTER ROLE {} WITH LOGIN NOREPLICATION' not in source
    assert '"ALTER ROLE {} WITH LOGIN NOBYPASSRLS' not in source


def test_existing_runtime_role_privileged_drift_stops_before_mutation() -> None:
    for position in range(5):
        state = [False, False, False, False, False]
        state[position] = True
        connection = _RuntimeRoleConnection(tuple(state))

        with pytest.raises(
            provisioner.ProvisioningStopped,
            match="HOSTED_RUNTIME_ROLE_ATTRIBUTE_DRIFT",
        ):
            provisioner._converge_runtime_role(connection, "test-runtime-password")

        assert connection.mutations == []


def test_runtime_role_membership_drift_stops_before_create_or_retry() -> None:
    connection = _RuntimeRoleConnection(
        (False, False, False, False, False),
        membership_count=1,
    )

    with pytest.raises(
        provisioner.ProvisioningStopped,
        match="HOSTED_RUNTIME_ROLE_MEMBERSHIP_PRESENT",
    ):
        provisioner._converge_runtime_role(connection, "test-runtime-password")

    assert connection.mutations == []


def test_postgres18_rehearsal_exercises_exact_create_and_retry_paths() -> None:
    bootstrap_source = inspect.getsource(rehearsal.rehearse_bootstrap)

    assert bootstrap_source.count("_converge_runtime_role(") == 2
    assert "first_password" in bootstrap_source
    assert "second_password" in bootstrap_source
    assert "PG18_HOSTED_RUNTIME_BOOTSTRAP=PASS" in bootstrap_source
    assert "PG18_HOSTED_RUNTIME_RETRY=PASS" in bootstrap_source
    assert bootstrap_source.count("_assert_creator_edge(bootstrap)") == 2
    assert bootstrap_source.count("bootstrap.execute(runtime_sql, prepare=False)") == 2


def test_retired_phase4_workflow_does_not_bind_runtime_retry_guard() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "LEGACY_RENDER_PHASE4_RETIRED_AMENDMENT_14" in workflow
    assert "tests/test_wp22a_phase4_runtime_role_retry.py" not in workflow
    assert "exit /b 78" in workflow
