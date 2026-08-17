from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
FULL_SHA = re.compile(r"[0-9a-f]{40}")
LIVE_WORKFLOW = ROOT / ".github" / "workflows" / "live-gateway-authority.yml"
LIVE_CONTRACT_WORKFLOW = (
    ROOT / ".github" / "workflows" / "v10-live-gateway-authority-contract.yml"
)


def _assert_external_actions_are_pinned(workflow: str) -> None:
    for raw_line in workflow.splitlines():
        if "uses:" not in raw_line:
            continue
        value = raw_line.split("uses:", maxsplit=1)[1].split("#", maxsplit=1)[0]
        reference = value.strip().strip("\"'").rsplit("@", maxsplit=1)[-1]
        assert FULL_SHA.fullmatch(reference), value


def _assert_headless_exact_sha_bootstrap(workflow: str) -> None:
    required = (
        "contents: read",
        "GITHUB_TOKEN: ${{ github.token }}",
        'GIT_TERMINAL_PROMPT: "0"',
        'GCM_INTERACTIVE: "0"',
        'git config --local credential.helper ""',
        "git config --local --add credential.helper",
        'git checkout --detach "$EXPECTED_HEAD"',
        "git config --local --unset-all credential.helper",
        'test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"',
        'test -z "$(git config --local --get-all credential.helper || true)"',
    )
    for marker in required:
        assert marker in workflow, marker
    assert "actions/checkout@" not in workflow


def test_live_authority_assets_are_tracked() -> None:
    required_paths = (
        ".github/workflows/live-gateway-authority.yml",
        ".github/workflows/v10-live-gateway-authority-contract.yml",
        "docs/operations/LIVE_GATEWAY_AUTHORITY_ACCEPTANCE.md",
        "omni_cio/release/live_authority_v1.py",
        "scripts/check_live_gateway_authority.py",
        "tests/test_live_gateway_authority_v1.py",
    )
    for relative_path in required_paths:
        assert (ROOT / relative_path).is_file(), relative_path

    retired_paths = (
        ".github/workflows/live-read-only-acceptance.yml",
        "docs/operations/LIVE_READ_ONLY_ACCEPTANCE.md",
    )
    for relative_path in retired_paths:
        assert not (ROOT / relative_path).exists(), relative_path


def test_actual_live_authority_workflow_is_manual_hosted_read_only_and_pinned() -> None:
    workflow = LIVE_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "pull_request:" not in workflow
    assert "runs-on: ubuntu-latest" in workflow
    assert "self-hosted" not in workflow
    assert "contents: read" in workflow
    assert "check_live_gateway_authority.py" in workflow
    assert "GATEWAY_API_KEY" not in workflow
    assert "TINVEST_TOKEN" not in workflow
    assert "continue-on-error: true" not in workflow
    assert "persist-credentials: false" in workflow
    _assert_external_actions_are_pinned(workflow)


def test_pr_live_authority_contract_executes_without_claiming_live_pass() -> None:
    workflow = LIVE_CONTRACT_WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "runs-on: [self-hosted, Windows, X64, omni-cio-ci]" in workflow
    assert "python scripts\\check_v10_ci_cost_control.py" in workflow
    assert "python tests\\test_live_acceptance_repository_assets.py" in workflow
    assert (
        "ACTUAL_V9_LIVE_AUTHORITY_EVIDENCE=DEFERRED_NO_TRUSTED_ZERO_COST_ROUTE"
        in workflow
    )
    assert "SUCCESS_DOES_NOT_CLAIM_DEPLOYED_LIVE_PASS" in workflow
    assert (
        "MANUAL_HOSTED_ACCEPTANCE_REMAINS_REQUIRED_FOR_V9_RUNTIME_AUTHORITY_RELEASE"
        in workflow
    )
    assert "python scripts/check_live_gateway_authority.py" not in workflow
    assert "GATEWAY_API_KEY" not in workflow
    assert "TINVEST_TOKEN" not in workflow
    assert "continue-on-error: true" not in workflow
    _assert_headless_exact_sha_bootstrap(workflow)
    _assert_external_actions_are_pinned(workflow)


def main() -> int:
    checks = (
        test_live_authority_assets_are_tracked,
        test_actual_live_authority_workflow_is_manual_hosted_read_only_and_pinned,
        test_pr_live_authority_contract_executes_without_claiming_live_pass,
    )
    for check in checks:
        check()
    print(f"Live authority repository asset checks passed: {len(checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
