from __future__ import annotations

import copy
from pathlib import Path

from scripts import check_v10_wp6_privilege_boundary as wp6


def test_current_wp6_privilege_boundary_passes() -> None:
    assert wp6.validate_repository() == []


def test_forbidden_production_secret_reference_is_rejected(
    tmp_path: Path, monkeypatch
) -> None:
    workflow_root = tmp_path / ".github" / "workflows"
    workflow_root.mkdir(parents=True)
    (workflow_root / "bad.yml").write_text(
        "env:\n  BAD: ${{ secrets.TINVEST_TRADING_TOKEN }}\n",
        encoding="utf-8",
    )
    contract = wp6.load_contract()
    failures: list[str] = []
    monkeypatch.setattr(wp6, "WORKFLOW_ROOT", workflow_root)

    wp6.validate_workflow_secret_boundary(contract, failures)

    assert any("TINVEST_TRADING_TOKEN" in item for item in failures)


def test_general_runtime_cannot_reference_broker_write_secret(
    tmp_path: Path, monkeypatch
) -> None:
    ai_root = tmp_path / "omni_cio" / "ai"
    ai_root.mkdir(parents=True)
    (ai_root / "agent.py").write_text(
        'TOKEN_NAME = "TINVEST_TRADING_TOKEN"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(wp6, "GENERAL_RUNTIME_ROOTS", (ai_root,))
    failures: list[str] = []

    wp6.validate_general_runtime_broker_boundary(failures)

    assert any("broker-write boundary" in item for item in failures)


def test_contract_rejects_arbitrary_pr_deployment_authority() -> None:
    contract = copy.deepcopy(wp6.load_contract())
    contract["deployment"]["arbitrary_pr_worktree_in_secret_context"] = True

    failures = wp6.validate_contract_shape(contract)

    assert any("arbitrary PR worktrees" in item for item in failures)


def test_contract_requires_runtime_and_execution_runner_root_deny() -> None:
    contract = copy.deepcopy(wp6.load_contract())
    contract["roles"]["runtime"]["runner_root_access"] = "ALLOW"
    contract["roles"]["execution"]["runner_root_access"] = "ALLOW"

    failures = wp6.validate_contract_shape(contract)

    assert any("ordinary runtime must be denied runner-root access" in item for item in failures)
    assert any("execution identity must be denied runner-root access" in item for item in failures)
