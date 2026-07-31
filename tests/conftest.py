from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from types import ModuleType

import pytest


_WINDOWS_PERMISSION_SIMULATIONS = {
    "test_unsafe_primary_permissions_and_invalid_time_fail_closed": (
        "omni_cio.paper.backup_v1",
    ),
    "test_manifest_rejects_unsafe_archive_permissions": (
        "omni_cio.paper.recovery_v1",
    ),
    "test_lock_diagnostic_marks_malformed_or_unsafe_lock_invalid": (
        "omni_cio.paper.recovery_v1",
    ),
}
_WINDOWS_POSIX_MODE_TEST = (
    "test_fresh_backup_drill_copies_encrypted_files_and_restores_latest"
)


@pytest.fixture(autouse=True)
def refresh_final_review_orchestration_clock(request: pytest.FixtureRequest) -> None:
    """Keep process-local TTL tests independent of the calendar date of the CI run."""

    module: ModuleType | None = getattr(request, "module", None)
    if module is not None and module.__name__.endswith(
        "test_final_decision_review_orchestration_v1"
    ):
        module.NOW = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def simulate_posix_permission_failure_on_windows(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep POSIX permission failure tests meaningful on Windows ACL hosts."""

    if os.name != "nt":
        return
    module_names = _WINDOWS_PERMISSION_SIMULATIONS.get(request.node.name, ())
    for module_name in module_names:
        module = __import__(module_name, fromlist=["permissions_are_owner_only"])
        monkeypatch.setattr(module, "permissions_are_owner_only", lambda _mode: False)


@pytest.fixture(autouse=True)
def simulate_posix_storage_modes_on_windows(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Represent owner-only storage modes in the one POSIX metadata assertion."""

    if os.name != "nt" or request.node.name != _WINDOWS_POSIX_MODE_TEST:
        return

    original_stat = Path.stat

    def stat_with_posix_mode(
        path: Path,
        *,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        result = original_stat(path, follow_symlinks=follow_symlinks)
        desired_mode: int | None = None
        if path.name == "backup":
            desired_mode = 0o700
        elif path.suffix in {".plae", ".plrm"}:
            desired_mode = 0o600
        if desired_mode is None:
            return result
        values = list(result)
        values[0] = (result.st_mode & ~0o777) | desired_mode
        return os.stat_result(values)

    monkeypatch.setattr(Path, "stat", stat_with_posix_mode)
