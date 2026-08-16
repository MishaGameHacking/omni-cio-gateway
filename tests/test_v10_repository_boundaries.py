from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "check_v10_repository_boundaries.py"
)
SPEC = importlib.util.spec_from_file_location(
    "check_v10_repository_boundaries", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
boundaries = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(boundaries)


def test_current_repository_satisfies_v10_boundary_contract() -> None:
    failures: list[str] = []

    boundaries.validate_authority_files(failures)
    boundaries.validate_engineering_governance(failures)
    boundaries.validate_no_competing_roots(failures)
    boundaries.validate_single_execution_authority(failures)
    boundaries.validate_adapter_authority(failures)
    boundaries.validate_core_import_graph(failures)
    boundaries.validate_codeowners(failures)

    assert failures == []


def test_competing_top_level_application_root_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "frontend").mkdir()
    monkeypatch.setattr(boundaries, "ROOT", tmp_path)
    failures: list[str] = []

    boundaries.validate_no_competing_roots(failures)

    assert failures == [
        "competing top-level application/runtime root is forbidden by V10: frontend"
    ]


def test_future_web_adapter_cannot_import_direct_real_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    web = tmp_path / "apps" / "web"
    web.mkdir(parents=True)
    (web / "unsafe.py").write_text(
        "from omni_cio.real_trading import service_v1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(boundaries, "ROOT", tmp_path)
    failures: list[str] = []

    boundaries.validate_adapter_authority(failures)

    assert any("imports direct Real authority" in failure for failure in failures)


def test_future_ai_adapter_cannot_reference_trading_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ai_root = tmp_path / "ai"
    ai_root.mkdir()
    (ai_root / "unsafe.py").write_text(
        'secret_name = "TINVEST_TRADING_TOKEN"\n',  # pragma: allowlist secret
        encoding="utf-8",
    )
    monkeypatch.setattr(boundaries, "ROOT", tmp_path)
    failures: list[str] = []

    boundaries.validate_adapter_authority(failures)

    assert any("trading secret marker" in failure for failure in failures)


def test_package_cycle_detector_returns_closed_cycle() -> None:
    graph = {
        "risk": {"strategy"},
        "strategy": {"optimizer"},
        "optimizer": {"risk"},
    }

    cycle = boundaries._find_cycle(graph)

    assert cycle is not None
    assert cycle[0] == cycle[-1]
    assert set(cycle[:-1]) == {"risk", "strategy", "optimizer"}


def test_single_execution_authority_rejects_duplicate_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "omni_cio" / "real_trading").mkdir(parents=True)
    (tmp_path / "omni_cio" / "plan_execution").mkdir(parents=True)
    (tmp_path / "apps" / "real_trading").mkdir(parents=True)
    monkeypatch.setattr(boundaries, "ROOT", tmp_path)
    failures: list[str] = []

    boundaries.validate_single_execution_authority(failures)

    assert any(
        "Real execution authority must exist exactly once" in item for item in failures
    )


def test_codeowners_requires_explicit_v10_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github = tmp_path / ".github"
    github.mkdir()
    (github / "CODEOWNERS").write_text("* @owner\n/docs/ @owner\n", encoding="utf-8")
    monkeypatch.setattr(boundaries, "ROOT", tmp_path)
    failures: list[str] = []

    boundaries.validate_codeowners(failures)

    assert any(
        "CODEOWNERS is missing explicit V10 ownership patterns" in item
        for item in failures
    )


def test_engineering_governance_failure_blocks_repository_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = tmp_path / "scripts" / "check_v10_engineering_governance.py"
    script.parent.mkdir(parents=True)
    script.write_text("raise SystemExit(9)\n", encoding="utf-8")
    monkeypatch.setattr(boundaries, "ROOT", tmp_path)
    failures: list[str] = []

    boundaries.validate_engineering_governance(failures)

    assert failures
    assert failures[0].startswith("engineering governance contract failed")
